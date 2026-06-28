"use strict";

const $ = (id) => document.getElementById(id);
const api = {
  async get(url) { const r = await fetch(url); return r.json(); },
  async post(url, body) {
    const r = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return r.json();
  },
};

// ---- app state ----
const state = {
  client: null,        // slug
  config: null,        // full config
  path: "",            // chosen local media path
  kind: "",            // reel | image
  transcript: "",      // video transcript / brief
  captions: {},        // {platform: text}
  ctaKeyword: "",      // ManyChat keyword for this post
};

// ---------------------------------------------------------------- clients

async function loadClients(selectSlug) {
  const clients = await api.get("/api/clients");
  const sel = $("clientSelect");
  sel.innerHTML = '<option value="">— select client —</option>' +
    clients.map((c) => `<option value="${c.slug}">${c.display_name}</option>`).join("");
  if (selectSlug) { sel.value = selectSlug; selectClient(selectSlug); }
}

async function selectClient(slug) {
  if (!slug) {
    state.client = null;
    $("workspace").classList.add("hidden");
    $("empty").classList.remove("hidden");
    return;
  }
  state.client = slug;
  state.config = await api.get(`/api/clients/${slug}`);
  $("empty").classList.add("hidden");
  $("workspace").classList.remove("hidden");
  resetFlow();
  // prefill the CTA keyword with the client's default (editable per post)
  const defKw = (state.config.cta && state.config.cta.default_keyword)
    || (state.config.brand && state.config.brand.cta_keyword) || "";
  $("ctaInput").value = defKw;
}

function resetFlow() {
  state.path = ""; state.kind = ""; state.transcript = ""; state.captions = {};
  $("chosen").classList.add("hidden");
  $("folderList").classList.add("hidden");
  $("contextInput").value = "";
  $("reqNote").textContent = "";
  $("transcriptBox").classList.add("hidden");
  $("captionsStep").classList.add("hidden");
  $("scheduleStep").classList.add("hidden");
  $("genStatus").textContent = "";
  $("pubStatus").textContent = "";
  $("reviseAllStatus").textContent = "";
  $("pubResults").innerHTML = "";
  $("pubBar").classList.add("hidden");
  $("generateBtn").disabled = true;
}

// ---------------------------------------------------------------- file choosing

function setChosen(path, kind) {
  state.path = path;
  state.kind = kind || "reel";
  $("chosenPath").textContent = path;
  $("chosenKind").textContent = state.kind === "image" ? "photo" : "video";
  $("chosen").classList.remove("hidden");
  // context field is always shown; only the "required" note depends on kind
  $("reqNote").textContent = state.kind === "image" ? "(required for photos)" : "(optional)";
  $("generateBtn").disabled = false;
}

$("browseFileBtn").onclick = async () => {
  const r = await api.post("/api/pick", { what: "file" });
  if (r.cancelled || !r.path) return;
  if (r.is_dir) { showFolder(r.path); } else { setChosen(r.path, r.kind); }
};

$("browseFolderBtn").onclick = async () => {
  const r = await api.post("/api/pick", { what: "folder" });
  if (r.cancelled || !r.path) return;
  showFolder(r.path);
};

async function showFolder(path) {
  const r = await api.get(`/api/folder?path=${encodeURIComponent(path)}`);
  const list = $("folderList");
  if (r.error || !r.files.length) {
    list.innerHTML = `<div class="folder-item">No media files found in this folder.</div>`;
  } else {
    list.innerHTML = r.files.map((f) =>
      `<div class="folder-item" data-path="${f.path}" data-kind="${f.kind}">
         <span>${f.name}</span><span class="pill">${f.kind === "image" ? "photo" : "video"}</span>
       </div>`).join("");
    list.querySelectorAll(".folder-item[data-path]").forEach((el) => {
      el.onclick = () => { setChosen(el.dataset.path, el.dataset.kind); list.classList.add("hidden"); };
    });
  }
  list.classList.remove("hidden");
}

// drag & drop upload
const dz = $("dropzone");
["dragenter", "dragover"].forEach((e) => dz.addEventListener(e, (ev) => {
  ev.preventDefault(); dz.classList.add("drag");
}));
["dragleave", "drop"].forEach((e) => dz.addEventListener(e, (ev) => {
  ev.preventDefault(); dz.classList.remove("drag");
}));
dz.addEventListener("drop", (ev) => { uploadFile(ev.dataTransfer.files[0]); });
$("fileInput").onchange = (ev) => uploadFile(ev.target.files[0]);

async function uploadFile(file) {
  if (!file) return;
  $("genStatus").textContent = "Uploading file…";
  const fd = new FormData();
  fd.append("file", file);
  const r = await (await fetch("/api/upload", { method: "POST", body: fd })).json();
  $("genStatus").textContent = "";
  if (r.error) { setStatus("genStatus", r.error, "err"); return; }
  setChosen(r.path, r.kind);
}

// ---------------------------------------------------------------- jobs

function setStatus(id, msg, cls) {
  const el = $(id);
  el.textContent = msg;
  el.className = "status" + (cls ? " " + cls : "");
}

async function pollJob(jobId, onProgress) {
  while (true) {
    const j = await api.get(`/api/job/${jobId}`);
    if (j.progress && onProgress) onProgress(j.progress);
    if (j.status === "done") return j.result;
    if (j.status === "error") throw new Error(j.error || "job failed");
    await new Promise((res) => setTimeout(res, 800));
  }
}

// ---------------------------------------------------------------- generate captions

$("generateBtn").onclick = async () => {
  $("generateBtn").disabled = true;
  const context = $("contextInput").value.trim();
  state.ctaKeyword = $("ctaInput").value.trim();
  try {
    state.transcript = "";
    if (state.kind === "image") {
      if (!context) { setStatus("genStatus", "Add some context for photos.", "err"); $("generateBtn").disabled = false; return; }
    } else {
      // videos: always transcribe locally (free); context is supplementary
      setStatus("genStatus", "Transcribing…", "spinner");
      const t = await pollJob((await api.post("/api/transcribe", { path: state.path })).job_id,
        (p) => setStatus("genStatus", p, "spinner"));
      state.transcript = t.transcript;
      $("transcriptText").textContent = state.transcript;
      $("transcriptBox").classList.remove("hidden");
    }

    setStatus("genStatus", "Drafting captions…", "spinner");
    const res = await pollJob(
      (await api.post("/api/captions", {
        client: state.client, kind: state.kind, path: state.path,
        transcript: state.transcript, context, cta_keyword: state.ctaKeyword,
      })).job_id,
      (p) => setStatus("genStatus", p, "spinner"));
    state.captions = res.captions;
    renderCaptions();
    setStatus("genStatus", "Captions ready — review below.", "ok");
  } catch (e) {
    setStatus("genStatus", e.message, "err");
  }
  $("generateBtn").disabled = false;
};

// update ALL captions at once
$("reviseAllBtn").onclick = async () => {
  const fb = $("reviseAllInput").value.trim();
  if (!fb) return;
  $("reviseAllBtn").disabled = true;
  setStatus("reviseAllStatus", "Updating all captions…", "spinner");
  try {
    const r = await api.post("/api/revise_all", {
      client: state.client, captions: state.captions, feedback: fb,
      context: state.transcript, cta_keyword: state.ctaKeyword,
    });
    if (r.error) throw new Error(r.error);
    state.captions = r.captions;
    renderCaptions();
    $("reviseAllInput").value = "";
    setStatus("reviseAllStatus", "All captions updated.", "ok");
  } catch (e) {
    setStatus("reviseAllStatus", e.message, "err");
  }
  $("reviseAllBtn").disabled = false;
};

function renderCaptions() {
  const wrap = $("captionCards");
  wrap.innerHTML = Object.entries(state.captions).map(([p, text]) => `
    <div class="cap-card" data-p="${p}">
      <div class="cap-head">
        <span class="cap-platform">${p}</span>
        <span class="cap-count"><span class="cnt">${text.length}</span> chars</span>
      </div>
      <textarea data-platform="${p}">${escapeHtml(text)}</textarea>
      <div class="feedback-row">
        <input type="text" placeholder="Quick feedback — e.g. punchier, drop emojis" data-fb="${p}">
        <button class="ghost" data-revise="${p}">Revise with AI</button>
      </div>
    </div>`).join("");

  wrap.querySelectorAll("textarea").forEach((ta) => {
    ta.oninput = () => {
      state.captions[ta.dataset.platform] = ta.value;
      ta.closest(".cap-card").querySelector(".cnt").textContent = ta.value.length;
    };
  });
  wrap.querySelectorAll("[data-revise]").forEach((btn) => {
    btn.onclick = () => reviseCaption(btn.dataset.revise, btn);
  });

  $("captionsStep").classList.remove("hidden");
  $("scheduleStep").classList.remove("hidden");
  if (!$("dtInput").value) $("dtInput").value = defaultDateTime();
}

async function reviseCaption(platform, btn) {
  const card = btn.closest(".cap-card");
  const fb = card.querySelector(`[data-fb="${platform}"]`).value.trim();
  if (!fb) return;
  btn.disabled = true; btn.textContent = "Revising…";
  try {
    const r = await api.post("/api/revise", {
      client: state.client, platform, text: state.captions[platform],
      feedback: fb, context: state.transcript, cta_keyword: state.ctaKeyword,
    });
    if (r.error) throw new Error(r.error);
    state.captions[platform] = r.text;
    const ta = card.querySelector("textarea");
    ta.value = r.text;
    card.querySelector(".cnt").textContent = r.text.length;
    card.querySelector(`[data-fb="${platform}"]`).value = "";
  } catch (e) {
    alert("Revise failed: " + e.message);
  }
  btn.disabled = false; btn.textContent = "Revise with AI";
}

// ---------------------------------------------------------------- publish

$("publishBtn").onclick = async () => {
  const when = $("dtInput").value;
  if (!when) { setStatus("pubStatus", "Pick a post time.", "err"); return; }
  $("publishBtn").disabled = true;
  const dryRun = $("dryRun").checked;
  $("pubResults").innerHTML = "";
  $("pubBar").classList.remove("hidden");
  setBar(0);
  try {
    setStatus("pubStatus", dryRun ? "Previewing…" : "Publishing…", "spinner");
    const res = await pollJob(
      (await api.post("/api/publish", {
        client: state.client, path: state.path, kind: state.kind,
        captions: state.captions, datetime: toISO(when), dry_run: dryRun,
      })).job_id,
      onPublishProgress);
    setBar(100);
    renderPubResults(res, dryRun);
  } catch (e) {
    setStatus("pubStatus", e.message, "err");
  }
  $("publishBtn").disabled = false;
};

function setBar(pct) { $("pubBarFill").style.width = pct + "%"; }

function onPublishProgress(msg) {
  const m = msg.match(/(\d+)%/);
  if (m) setBar(parseInt(m[1], 10));
  setStatus("pubStatus", msg, "spinner");
}

function renderPubResults(res, dryRun) {
  const posts = res.posts || [];
  const ok = posts.filter((p) => p.ok).length;
  const draftNote = res.as_draft && !dryRun ? " as drafts (review/approve in Buffer)" : "";
  setStatus("pubStatus",
    `${dryRun ? "Preview" : "Done"}: ${ok}/${posts.length} channels${dryRun ? " — uncheck 'Preview only' to post for real" : draftNote}.`,
    ok === posts.length ? "ok" : "err");
  $("pubResults").innerHTML = posts.map((p) =>
    p.ok
      ? `<div class="pub-result ok">✓ ${p.platform}${p.id && p.id !== "(dry-run)" ? " — " + p.id : ""}</div>`
      : `<div class="pub-result err">✗ ${p.platform}: ${escapeHtml(p.error || "failed")}</div>`
  ).join("");
}

// ---------------------------------------------------------------- onboarding

$("addClientBtn").onclick = () => { $("onboardModal").classList.remove("hidden"); renderChannelMap([]); };
$("onboardClose").onclick = () => $("onboardModal").classList.add("hidden");

let fetchedChannels = [];
$("fetchChannels").onclick = async () => {
  $("onboardStatus").textContent = "Fetching channels…";
  const r = await api.get("/api/buffer/channels");
  if (r.error) { setStatus("onboardStatus", r.error, "err"); return; }
  fetchedChannels = r;
  renderChannelMap(r);
  setStatus("onboardStatus", `Found ${r.length} channels.`, "ok");
};

const PLATFORMS = ["facebook", "instagram", "tiktok", "linkedin", "youtube"];
function renderChannelMap(channels) {
  $("channelMap").innerHTML = PLATFORMS.map((p) => {
    const opts = ['<option value="">— none —</option>'].concat(
      channels
        .filter((c) => (c.service || "").toLowerCase().includes(p) || !channels.length)
        .map((c) => `<option value="${c.id}" data-name="${c.name || c.serviceUsername || ""}">${c.name || c.serviceUsername || c.id} (${c.service})</option>`)
    );
    // if no fetch yet, allow manual id entry
    const control = channels.length
      ? `<select data-platform="${p}">${opts.join("")}</select>`
      : `<input data-platform="${p}" placeholder="channel id (or Fetch from Buffer)">`;
    return `<div class="channel-row"><span>${p}</span>${control}</div>`;
  }).join("");
}

$("onboardSave").onclick = async () => {
  const channels = {};
  document.querySelectorAll("#channelMap [data-platform]").forEach((el) => {
    const id = el.value.trim();
    if (!id) return;
    const opt = el.tagName === "SELECT" ? el.selectedOptions[0] : null;
    channels[el.dataset.platform] = { id, name: opt ? opt.dataset.name : "" };
  });
  const body = {
    slug: $("ob_slug").value, display_name: $("ob_name").value,
    name: $("ob_brand").value, tagline: $("ob_tagline").value,
    voice: $("ob_voice").value, cta_keyword: $("ob_cta").value,
    link_in_bio: $("ob_link").value, bucket: $("ob_bucket").value,
    region: $("ob_region").value, channels,
  };
  setStatus("onboardStatus", "Creating…", "spinner");
  const r = await api.post("/api/clients", body);
  if (r.error) { setStatus("onboardStatus", r.error, "err"); return; }
  $("onboardModal").classList.add("hidden");
  await loadClients(r.slug);
};

// ---------------------------------------------------------------- helpers

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function defaultDateTime() {
  const t = state.config?.schedule?.feed?.default_time || "15:00";
  const [h, m] = t.split(":").map(Number);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  if (d <= new Date()) d.setDate(d.getDate() + 1);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function toISO(localValue) {
  // datetime-local has no tz; attach the browser's local offset
  const d = new Date(localValue);
  const pad = (n) => String(n).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const oh = pad(Math.floor(Math.abs(off) / 60)), om = pad(Math.abs(off) % 60);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00${sign}${oh}:${om}`;
}

// ---- init ----
$("clientSelect").onchange = (e) => selectClient(e.target.value);
loadClients();
