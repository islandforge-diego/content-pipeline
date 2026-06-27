#!/usr/bin/env python3
"""Multi-tenant content-review site generator — unified calendar.

One minimal page per client. A month calendar; tapping a day shows BOTH that
day's Instagram Story and any feed posts scheduled that day.

Data (clients/<slug>/config.json):
  {
    "slug": "deba", "title": "...", "theme": {...},
    "banner": "...", "footer": "...",
    "feed":    [ {"iso_date":"2026-06-27","time":"15:00","title":"...","chips":[...],
                  "media":{...},"caps":[["instagram","..."]]} ],
    "stories": [ {"iso_date":"2026-06-27","time":"07:00","title":"...",
                  "sticker":"...","img":"stories/..."} ]
  }

Legacy support: an old-style {"stories":{"year","month","items":[{"day",...}]}}
block is converted to dated story items; old feed items with a "date" string but
no "iso_date" are shown in an "Other posts" list so nothing is lost.

Run:  python3 generate.py
Add a client: create clients/<slug>/config.json (+ stories/ images) and re-run.
"""
import calendar
import datetime
import glob
import html
import json


DEFAULT_CLIENT = "deba"


def esc(s):
    return html.escape(str(s))


def normalize(cfg):
    """Return (by_date, undated_posts).

    by_date: { "YYYY-MM-DD": {"stories": [...], "posts": [...]} }
    undated_posts: legacy feed items lacking an iso_date.
    """
    by_date = {}

    def slot(d):
        return by_date.setdefault(d, {"stories": [], "posts": []})

    # Stories — new flat list
    stories = cfg.get("stories")
    if isinstance(stories, list):
        for s in stories:
            if s.get("iso_date"):
                slot(s["iso_date"])["stories"].append(s)
    # Stories — legacy {year, month, items:[{day,...}]}
    elif isinstance(stories, dict) and stories.get("items"):
        y, mo = stories.get("year"), stories.get("month")
        for it in stories["items"]:
            if y and mo and it.get("day"):
                d = f"{y:04d}-{mo:02d}-{int(it['day']):02d}"
                slot(d)["stories"].append(it)

    # Feed posts
    undated = []
    for p in cfg.get("feed", []):
        if p.get("iso_date"):
            slot(p["iso_date"])["posts"].append(p)
        else:
            undated.append(p)

    return by_date, undated


def render_media(m):
    if not m:
        return ""
    if m.get("type") == "video":
        poster = f' poster="{esc(m.get("poster",""))}"' if m.get("poster") else ""
        return f'<video controls preload="none" playsinline{poster} src="{esc(m["src"])}"></video>'
    imgs = m.get("images", [])
    g = '<div class="gallery">' + "".join(f'<img loading="lazy" src="{esc(u)}">' for u in imgs) + "</div>"
    if len(imgs) > 1:
        g += f'<div class="count">🖼️ {len(imgs)}-photo carousel</div>'
    return g


def render_post_block(p):
    chips = "".join(f'<span class="chip">{esc(c)}</span>' for c in p.get("chips", []))
    caps = "".join(
        f'<div class="cap"><h4>{esc(lbl)}</h4><p>{esc(t)}</p></div>'
        for lbl, t in p.get("caps", [])
    )
    return f"""
    <div class="post">
      {render_media(p.get("media"))}
      <div class="ptitle">{esc(p.get("title",""))}{(' · '+esc(p["time"])) if p.get("time") else ''}</div>
      <div class="chips">{chips}</div>
      <details><summary>Captions per platform</summary><div class="caps">{caps}</div></details>
    </div>"""


def render_story_block(s):
    return f"""
    <div class="story">
      <img class="simg" loading="lazy" src="{esc(s.get('img',''))}" alt="">
      <div class="stitle">📱 {esc(s.get('title',''))}{(' · '+esc(s['time'])) if s.get('time') else ''}</div>
      <div class="schip">{esc(s.get('sticker',''))}</div>
    </div>"""


def render_calendar(year, month, by_date):
    first = datetime.date(year, month, 1)
    ndays = calendar.monthrange(year, month)[1]
    lead = (first.weekday() + 1) % 7  # Sunday-first
    dow = "".join(f'<div class="cdow">{x}</div>' for x in ["S", "M", "T", "W", "T", "F", "S"])
    cells = '<div class="ccell empty"></div>' * lead
    for dn in range(1, ndays + 1):
        iso = f"{year:04d}-{month:02d}-{dn:02d}"
        slot = by_date.get(iso)
        if slot and (slot["stories"] or slot["posts"]):
            dots = ""
            if slot["stories"]:
                dots += '<span class="dot story"></span>'
            if slot["posts"]:
                dots += '<span class="dot post"></span>'
            cells += f'<div class="ccell has" data-date="{iso}" role="button" tabindex="0">{dn}<span class="dots">{dots}</span></div>'
        else:
            cells += f'<div class="ccell">{dn}</div>'
    label = first.strftime("%B %Y")
    return f"""
  <section class="card">
    <div class="calhead">{esc(label)}</div>
    <div class="cal">{dow}{cells}</div>
    <p class="legend"><span class="dot story"></span> story &nbsp; <span class="dot post"></span> post</p>
    <p class="snote">Tap a highlighted day to see that day's story and posts.</p>
  </section>"""


def page(cfg):
    th = cfg.get("theme", {})
    accent = th.get("accent", "#1f6f54")
    soft = th.get("soft", "#e8f1ec")
    sborder = th.get("soft_border", "#cfe2d8")
    atext = th.get("accent_text", "#16503c")
    sbg = th.get("story_bg", "#0d5f6e")

    by_date, undated = normalize(cfg)

    # Which months to render: those with content, else current month
    months = sorted({tuple(int(x) for x in d.split("-")[:2]) for d in by_date})
    if not months:
        today = datetime.date.today()
        months = [(today.year, today.month)]
    cal_html = "".join(render_calendar(y, m, by_date) for y, m in months)

    # Day data for the modal (JS)
    day_json = {}
    for d, slot in by_date.items():
        day_json[d] = {
            "stories": [render_story_block(s) for s in slot["stories"]],
            "posts": [render_post_block(p) for p in slot["posts"]],
        }

    undated_html = ""
    if undated:
        undated_html = '<section class="card"><div class="calhead">Other posts</div>' + \
            "".join(render_post_block(p) for p in undated) + "</section>"

    updated = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=-5))
    ).strftime("%b %-d, %-I:%M %p CT")

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(cfg.get('title','Content Preview'))}</title>
<style>
 :root{{--ink:#1c1c1a;--muted:#6b6760;--line:#e7e3db;--bg:#f6f3ee;--card:#fff;--accent:{accent};--soft:{soft};--chip:#f0ece4}}
 *{{box-sizing:border-box;-webkit-text-size-adjust:100%}}
 body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
 .wrap{{max-width:540px;margin:0 auto;padding:16px 14px calc(40px + env(safe-area-inset-bottom))}}
 .top{{position:sticky;top:0;background:rgba(246,243,238,.92);backdrop-filter:blur(8px);margin:-16px -14px 14px;padding:14px;border-bottom:1px solid var(--line);z-index:5}}
 h1{{font-size:20px;margin:0;letter-spacing:-.01em}} .meta{{color:var(--muted);font-size:13px;margin-top:2px}}
 .banner{{background:var(--soft);border:1px solid {sborder};color:{atext};border-radius:12px;padding:11px 13px;font-size:13.5px;margin:0 0 18px}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:16px;box-shadow:0 1px 2px rgba(0,0,0,.03)}}
 .calhead{{font-weight:700;font-size:15px;text-align:center;margin:2px 0 10px}}
 .cal{{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}}
 .cdow{{text-align:center;font-size:11px;font-weight:700;color:var(--muted);padding:2px 0}}
 .ccell{{aspect-ratio:1/1;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:13px;color:#9a958c;border-radius:10px;position:relative}}
 .ccell.empty{{visibility:hidden}}
 .ccell.has{{background:var(--soft);color:var(--accent);font-weight:700;cursor:pointer;border:1px solid {sborder}}}
 .dots{{display:flex;gap:3px;margin-top:3px}}
 .dot{{width:6px;height:6px;border-radius:50%;display:inline-block}}
 .dot.story{{background:{sbg}}} .dot.post{{background:var(--accent)}}
 .legend{{font-size:11.5px;color:var(--muted);text-align:center;margin:10px 0 0;display:flex;gap:6px;align-items:center;justify-content:center}}
 .legend .dot{{margin:0 2px}}
 .snote{{font-size:12.5px;color:var(--muted);margin:6px 0 0;text-align:center}}
 video{{width:100%;max-width:320px;display:block;margin:0 auto 10px;border-radius:14px;background:#000;aspect-ratio:9/16;object-fit:cover}}
 .gallery{{display:flex;gap:8px;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding-bottom:6px;margin-bottom:6px}}
 .gallery img{{height:300px;border-radius:12px;scroll-snap-align:center;flex:0 0 auto;background:#eee}}
 .count{{font-size:12.5px;color:var(--muted);margin-bottom:6px}}
 .post{{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}} .post:first-child{{border-top:none;margin-top:0;padding-top:0}}
 .ptitle{{font-size:16px;font-weight:650;margin:0 0 8px;line-height:1.3}}
 .story{{margin-bottom:14px}}
 .simg{{width:100%;max-width:300px;display:block;margin:0 auto 8px;border-radius:14px;background:{sbg};aspect-ratio:9/16;object-fit:cover}}
 .stitle{{font-size:15px;font-weight:650;text-align:center}}
 .schip{{font-size:13px;color:var(--muted);text-align:center;margin-top:3px}}
 .chips{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:4px}}
 .chip{{background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:4px 11px;font-size:12.5px;color:#4a463f}}
 details{{margin-top:10px;border-top:1px solid var(--line)}}
 summary{{cursor:pointer;list-style:none;padding:12px 2px 4px;font-size:14px;font-weight:600;color:var(--accent)}}
 summary::-webkit-details-marker{{display:none}} summary:after{{content:" ▾";color:var(--muted)}}
 .cap{{border-top:1px dashed var(--line);padding:11px 0}} .cap:first-child{{border-top:none}}
 .cap h4{{margin:0 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}
 .cap p{{margin:0;white-space:pre-wrap;font-size:14px}}
 .modal{{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;padding:18px}}
 .modal[hidden]{{display:none}}
 .mback{{position:absolute;inset:0;background:rgba(20,20,18,.62);backdrop-filter:blur(2px)}}
 .msheet{{position:relative;background:var(--card);border-radius:18px;padding:16px;max-width:360px;width:100%;max-height:92vh;overflow:auto;box-shadow:0 12px 40px rgba(0,0,0,.3)}}
 .mclose{{position:absolute;top:8px;right:8px;border:none;background:#0000000d;width:30px;height:30px;border-radius:50%;font-size:15px;cursor:pointer;color:var(--ink)}}
 .mday{{font-size:13px;font-weight:700;color:var(--accent);margin:2px 0 10px}}
 footer{{color:var(--muted);font-size:12.5px;text-align:center;margin-top:22px}}
</style></head><body><div class="wrap">
 <div class="top"><h1>{esc(cfg.get('title','Content Preview'))}</h1><div class="meta">updated {updated}</div></div>
 <div class="banner">{cfg.get('banner','')}</div>
 {cal_html}
 {undated_html}
 <footer>{esc(cfg.get('footer',''))}</footer>
</div>
<div id="dmodal" class="modal" hidden><div class="mback"></div>
 <div class="msheet"><button class="mclose" aria-label="Close">✕</button>
  <div class="mday"></div><div class="mbody"></div></div></div>
<script>
 var D={json.dumps(day_json)};
 var m=document.getElementById('dmodal');
 function fmt(d){{var p=d.split('-');var dt=new Date(p[0],p[1]-1,p[2]);
   return dt.toLocaleDateString(undefined,{{weekday:'long',month:'long',day:'numeric'}});}}
 function openD(d){{var x=D[d];if(!x)return;
   m.querySelector('.mday').textContent=fmt(d);
   m.querySelector('.mbody').innerHTML=x.stories.join('')+x.posts.join('');
   m.hidden=false;document.body.style.overflow='hidden';}}
 function closeD(){{m.hidden=true;document.body.style.overflow='';}}
 document.querySelectorAll('.ccell.has').forEach(function(c){{
   c.addEventListener('click',function(){{openD(c.dataset.date);}});
   c.addEventListener('keydown',function(e){{if(e.key==='Enter'||e.key===' '){{e.preventDefault();openD(c.dataset.date);}}}});
 }});
 m.querySelector('.mback').addEventListener('click',closeD);
 m.querySelector('.mclose').addEventListener('click',closeD);
 document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeD();}});
</script>
</body></html>"""


def main():
    built = []
    for cf in sorted(glob.glob("clients/*/config.json")):
        cfg = json.load(open(cf))
        slug = cfg["slug"]
        outp = f"clients/{slug}/index.html"
        open(outp, "w").write(page(cfg))
        built.append(slug)
        print("built", outp)
    redirect = (
        f'<!doctype html><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url=clients/{DEFAULT_CLIENT}/">'
        f'<link rel="canonical" href="clients/{DEFAULT_CLIENT}/">'
        f'<title>Redirecting…</title><a href="clients/{DEFAULT_CLIENT}/">Continue →</a>'
    )
    open("index.html", "w").write(redirect)
    print("built index.html -> clients/%s/" % DEFAULT_CLIENT)
    print("clients:", built)


if __name__ == "__main__":
    main()
