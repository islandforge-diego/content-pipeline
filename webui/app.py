#!/usr/bin/env python3
"""app.py — local web UI for the content pipeline.

Run:  python webui/app.py
Opens http://127.0.0.1:5000 in your browser. Everything runs on your machine,
so it can reach ffmpeg, S3, Buffer and the Anthropic API.
"""
import json
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "config" / "clients"
PREVIEW_DIR = ROOT / "content-preview"
SCRATCH = ROOT / "webui" / ".uploads"
SCRATCH.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")

# Make the pipeline modules importable
sys.path.insert(0, str(ROOT / "pipeline"))
from transcribe import transcribe                       # noqa: E402
from caption_gen import generate_captions, revise_caption, revise_all  # noqa: E402
from publish import publish, target_channels, upload_to_s3  # noqa: E402
from frames import extract_frames, probe_video           # noqa: E402
import buffer_api                                        # noqa: E402
import preview_sync                                      # noqa: E402
from story_gen import generate_story                     # noqa: E402
from story_render import render_story                     # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs              # noqa: E402
import native_dialog     # noqa: E402

app = Flask(__name__, static_folder="static", template_folder="templates")

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}
MEDIA_EXTS = VIDEO_EXTS | IMAGE_EXTS


def kind_for(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in VIDEO_EXTS:
        return "reel"
    if ext in IMAGE_EXTS:
        return "image"
    return ""


# ---------------------------------------------------------------- pages

@app.get("/")
def index():
    return send_from_directory("templates", "index.html")


# ---------------------------------------------------------------- clients

@app.get("/api/clients")
def list_clients():
    out = []
    for cf in sorted(CLIENTS_DIR.glob("*.json")):
        if cf.stem.startswith("_"):
            continue
        cfg = json.loads(cf.read_text())
        out.append({"slug": cfg.get("slug", cf.stem), "display_name": cfg.get("display_name", cf.stem)})
    return jsonify(out)


@app.get("/api/clients/<slug>")
def get_client(slug):
    cf = CLIENTS_DIR / f"{secure_filename(slug)}.json"
    if not cf.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(cf.read_text()))


@app.post("/api/clients")
def create_client():
    """Onboard a new client by filling the template with form values."""
    body = request.get_json(force=True)
    slug = secure_filename(body.get("slug", "").strip().lower())
    if not slug:
        return jsonify({"error": "slug required"}), 400
    cf = CLIENTS_DIR / f"{slug}.json"
    if cf.exists():
        return jsonify({"error": f"client '{slug}' already exists"}), 409

    cfg = json.loads((CLIENTS_DIR / "_template.json").read_text())
    cfg["slug"] = slug
    cfg["display_name"] = body.get("display_name", slug)

    brand = cfg["brand"]
    for k in ("name", "tagline", "voice", "cta_keyword", "link_in_bio"):
        if body.get(k):
            brand[k] = body[k]

    # Channel ids: {platform: {id, name/handle}} mapped in the UI from Buffer
    for platform, info in (body.get("channels") or {}).items():
        if platform in cfg["buffer"]["channels"] and info.get("id"):
            cfg["buffer"]["channels"][platform]["id"] = info["id"]
            if info.get("name"):
                cfg["buffer"]["channels"][platform]["name"] = info["name"]
            if info.get("handle"):
                cfg["buffer"]["channels"][platform]["handle"] = info["handle"]

    if body.get("bucket"):
        cfg["s3"]["bucket"] = body["bucket"]
    if body.get("region"):
        cfg["s3"]["region"] = body["region"]

    cfg["preview"]["data_file"] = f"content-preview/clients/{slug}/config.json"

    cf.write_text(json.dumps(cfg, indent=2))
    return jsonify({"slug": slug, "display_name": cfg["display_name"]}), 201


@app.get("/api/buffer/channels")
def buffer_channels():
    """List the org's Buffer channels so onboarding can map them with clicks."""
    token = os.environ.get("BUFFER_TOKEN", "")
    if not token:
        return jsonify({"error": "BUFFER_TOKEN not set in .env"}), 400
    org_id = request.args.get("org_id")
    if not org_id:  # default to the studio org from the template
        tmpl = json.loads((CLIENTS_DIR / "_template.json").read_text())
        org_id = tmpl.get("buffer", {}).get("org_id")
    try:
        return jsonify(buffer_api.list_channels(token, org_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------- file selection

@app.post("/api/pick")
def pick():
    """Open the native OS file or folder dialog (server-side, no upload)."""
    what = (request.get_json(silent=True) or {}).get("what", "file")
    path = native_dialog.pick_folder() if what == "folder" else native_dialog.pick_file()
    if not path:
        return jsonify({"path": "", "cancelled": True})
    return jsonify({"path": path, "kind": kind_for(path), "is_dir": os.path.isdir(path)})


@app.get("/api/folder")
def folder():
    """List media files inside a folder so the user can choose one."""
    path = request.args.get("path", "")
    p = Path(path)
    if not p.is_dir():
        return jsonify({"error": "not a folder"}), 400
    files = [
        {"path": str(f), "name": f.name, "kind": kind_for(str(f))}
        for f in sorted(p.iterdir())
        if f.is_file() and f.suffix.lower() in MEDIA_EXTS
    ]
    return jsonify({"folder": str(p), "files": files})


@app.post("/api/upload")
def upload():
    """Drag-and-drop upload → save to scratch dir → return local path."""
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    name = secure_filename(f.filename or "upload")
    dest = SCRATCH / name
    f.save(dest)
    return jsonify({"path": str(dest), "name": name, "kind": kind_for(str(dest))})


# ---------------------------------------------------------------- pipeline jobs

@app.post("/api/transcribe")
def api_transcribe():
    path = request.get_json(force=True).get("path", "")
    if not Path(path).exists():
        return jsonify({"error": "file not found"}), 400

    def work(progress):
        progress("Transcribing… (first run downloads the Whisper model)")
        return {"transcript": transcribe(path)}

    return jsonify({"job_id": jobs.start(work)})


@app.post("/api/captions")
def api_captions():
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    kind = body.get("kind") or "reel"
    transcript = body.get("transcript") or ""
    extra_context = body.get("context") or ""
    cta_keyword = body.get("cta_keyword") or ""
    path = body.get("path") or ""
    platforms = target_channels(cfg, kind)

    def work(progress):
        frames = []
        if kind == "reel" and path and Path(path).exists():
            progress("Grabbing frames for visual context…")
            frames = extract_frames(path, count=3)
        progress(f"Drafting captions for {len(platforms)} platforms…")
        caps = generate_captions(cfg, transcript, kind, platforms,
                                 frames=frames, extra_context=extra_context,
                                 cta_keyword=cta_keyword)
        result = {"captions": caps}
        if kind == "reel" and path and Path(path).exists():
            result["video"] = probe_video(path)
        return result

    return jsonify({"job_id": jobs.start(work)})


@app.post("/api/revise")
def api_revise():
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    try:
        text = revise_caption(
            cfg, body["platform"], body["text"], body["feedback"],
            body.get("context", ""), body.get("cta_keyword", "")
        )
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/revise_all")
def api_revise_all():
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    try:
        captions = revise_all(cfg, body["captions"], body["feedback"],
                              body.get("context", ""), body.get("cta_keyword", ""))
        return jsonify({"captions": captions})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/check_conflicts")
def api_check_conflicts():
    """Warn if any selected platform already has a post scheduled at that time."""
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    when = body["datetime"]
    platforms = body.get("platforms") or []
    token = os.environ.get("BUFFER_TOKEN", "")
    if not token:
        return jsonify({"conflicts": []})  # can't check without a token; don't block
    channels = cfg["buffer"]["channels"]
    org_id = cfg["buffer"]["org_id"]
    id_to_platform = {channels[p]["id"]: p for p in platforms if p in channels}
    try:
        existing = buffer_api.posts_at(token, org_id, list(id_to_platform), when)
        conflicts = sorted({id_to_platform[p["channelId"]] for p in existing
                            if p.get("channelId") in id_to_platform})
        return jsonify({"conflicts": conflicts})
    except Exception as e:
        return jsonify({"conflicts": [], "warning": str(e)})


@app.post("/api/publish")
def api_publish():
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    path = body["path"]
    captions = body["captions"]
    when = body["datetime"]
    kind = body.get("kind") or kind_for(path)
    dry_run = bool(body.get("dry_run"))
    token = os.environ.get("BUFFER_TOKEN", "")
    if not token and not dry_run:
        return jsonify({"error": "BUFFER_TOKEN not set in .env"}), 400

    def work(progress):
        def on_event(ev, p):
            if ev == "upload_progress":
                progress(f"Uploading to S3… {p}%")
            elif ev == "upload":
                progress("Upload complete. Scheduling to Buffer…")
            elif ev == "post":
                where = p.get("platform", "")
                progress(f"{'✓' if p.get('ok') else '✗'} {where}")
        progress("Uploading to S3… 0%")
        result = publish(
            path, cfg, captions, when, kind, token, dry_run=dry_run,
            on_event=on_event,
        )
        if not dry_run and token:
            progress("Refreshing preview from Buffer…")
            try:
                preview_sync.sync_preview(cfg, token)
            except Exception as e:
                progress(f"(preview refresh skipped: {e})")
        return result

    return jsonify({"job_id": jobs.start(work)})


@app.get("/api/job/<job_id>")
def api_job(job_id):
    return jsonify(jobs.get(job_id))


# ---------------------------------------------------------------- stories

@app.post("/api/story/generate")
def api_story_generate():
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    try:
        return jsonify(generate_story(cfg, body.get("theme", ""), body.get("brief", "")))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/story/render")
def api_story_render():
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    font_name = cfg.get("brand", {}).get("fonts", {}).get("display")
    path = body.get("path", "")
    overlay = body.get("overlay", "")
    kind = body.get("kind") or kind_for(path)
    if not Path(path).exists():
        return jsonify({"error": "media not found"}), 400
    ext = ".jpg" if kind == "image" else ".mp4"
    out = SCRATCH / f"story_{Path(path).stem}{ext}"

    def work(progress):
        progress("Rendering story overlay…")
        render_story(path, overlay, str(out), kind, font_name=font_name)
        return {"rendered": str(out), "preview_url": f"/rendered/{out.name}", "kind": kind}

    return jsonify({"job_id": jobs.start(work)})


@app.post("/api/story/publish")
def api_story_publish():
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    rendered = body["rendered"]
    sticker = body.get("sticker", "")
    when = body["datetime"]
    kind = body.get("kind") or kind_for(rendered)
    dry_run = bool(body.get("dry_run"))
    token = os.environ.get("BUFFER_TOKEN", "")
    if not token and not dry_run:
        return jsonify({"error": "BUFFER_TOKEN not set in .env"}), 400
    ig = cfg["buffer"]["channels"].get("instagram", {}).get("id")
    if not ig:
        return jsonify({"error": "no Instagram channel configured"}), 400

    def work(progress):
        progress("Uploading story to S3… 0%")
        url = upload_to_s3(rendered, cfg, dry_run,
                           on_progress=lambda pct: progress(f"Uploading story to S3… {pct}%"))
        if dry_run:
            return {"ok": True, "media_url": url, "dry_run": True}
        progress("Scheduling story reminder…")
        post = buffer_api.create_story_reminder(ig, url, when, sticker, kind, token)
        return {"ok": True, "id": post.get("id", "?"), "media_url": url}

    return jsonify({"job_id": jobs.start(work)})


@app.get("/rendered/<path:name>")
def serve_rendered(name):
    return send_from_directory(str(SCRATCH), name)


# ---------------------------------------------------------------- preview

@app.post("/api/preview/sync")
def api_preview_sync():
    """Rebuild a client's preview page from Buffer's actual scheduled posts."""
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    token = os.environ.get("BUFFER_TOKEN", "")
    if not token:
        return jsonify({"error": "BUFFER_TOKEN not set in .env"}), 400
    try:
        feed_n, story_n = preview_sync.sync_preview(cfg, token)
        return jsonify({"feed": feed_n, "stories": story_n, "url": f"/preview/clients/{slug}/"})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/preview/publish")
def api_preview_publish():
    """Re-sync from Buffer and push the live (public) preview site for a client."""
    body = request.get_json(force=True)
    slug = secure_filename(body.get("client", ""))
    cfg = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    token = os.environ.get("BUFFER_TOKEN", "")
    if not token:
        return jsonify({"error": "BUFFER_TOKEN not set in .env"}), 400
    repo = cfg.get("preview", {}).get("pages_repo")
    url = cfg.get("preview", {}).get("pages_url")
    if not repo:
        return jsonify({"error": "no preview.pages_repo configured for this client"}), 400

    def work(progress):
        progress("Syncing from Buffer…")
        preview_sync.sync_preview(cfg, token)
        progress("Publishing to the web…")
        env = dict(os.environ, PREVIEW_REPO=repo)
        r = subprocess.run(["bash", "deploy.sh"], cwd=str(PREVIEW_DIR),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout)[-300:] or "deploy failed")
        return {"url": url}

    return jsonify({"job_id": jobs.start(work)})


@app.get("/preview/<path:subpath>")
def serve_preview(subpath):
    """Serve the generated preview pages so you can view them from this app."""
    if (PREVIEW_DIR / subpath).is_dir():
        subpath = subpath.rstrip("/") + "/index.html"
    return send_from_directory(str(PREVIEW_DIR), subpath)


# ---------------------------------------------------------------- launch

# Port 5000 is taken by AirPlay Receiver (Control Center) on macOS, so default
# to 5050. Override with PORT=... if you like.
PORT = int(os.environ.get("PORT", "5050"))


def _open_browser():
    webbrowser.open(f"http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.0, _open_browser).start()
    app.run(host="127.0.0.1", port=PORT, debug=True)
