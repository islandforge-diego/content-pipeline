#!/usr/bin/env python3
"""Multi-tenant content-review site generator — two month-navigable calendars.

One page per client with a Posts calendar and a Stories calendar. Each shows a
single month with prev/next arrows; tap a day to see that day's cards. Data comes
from clients/<slug>/config.json (feed[] and stories[], each item carrying iso_date),
produced by pipeline/preview_sync.py from Buffer.

Run:  python3 generate.py
"""
import base64
import calendar
import datetime
import glob
import html
import json
import os

DEFAULT_CLIENT = "deba"

# Island Forge wordmark (white, for the dark report header). Inlined as a base64
# data URI at build time so the static page never depends on an asset path.
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "islandforge-wordmark-white.png")


def _logo_data_uri():
    try:
        with open(_LOGO_PATH, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""


def esc(s):
    return html.escape(str(s))


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
    cta = p.get("cta") or {}
    if cta.get("type") == "comment":
        cta_html = f'<span class="cta">💬 Comment “{esc(cta.get("keyword",""))}”</span>'
    elif cta.get("type") == "link":
        cta_html = '<span class="cta">🔗 Link in bio</span>'
    else:
        cta_html = ""
    meta = "".join(filter(None, [
        f'<span class="ptime">{esc(p["time"])}</span>' if p.get("time") else "",
        cta_html,
    ]))
    title = f'<div class="ptitle">{esc(p["title"])}</div>' if p.get("title") else ""
    return f"""<div class="post">
      {render_media(p.get("media"))}
      <div class="pmeta">{meta}</div>
      {title}
      <div class="chips">{chips}</div>
      <details><summary>Captions per platform</summary><div class="caps">{caps}</div></details>
    </div>"""


def render_story_block(s):
    sticker = f'<div class="schip">{esc(s.get("sticker",""))}</div>' if s.get("sticker") else ""
    time = f'<span class="ptime">{esc(s["time"])}</span>' if s.get("time") else ""
    return f"""<div class="post">
      {render_media(s.get("media"))}
      <div class="pmeta">{time}<span class="cta">📱 Story</span></div>
      {sticker}
    </div>"""


def _topslide(c):
    """One top-post card: platform + reach + the present stat chips (likes/comments/…)."""
    m = c.get("m", {})
    chips = [f'<span class="ptime">{esc(c.get("platform",""))}</span>']
    for key, label in (("views", "views"), ("likes", "likes"), ("comments", "comments"),
                       ("shares", "shares"), ("saves", "saves")):
        if m.get(key):
            chips.append(f'<span class="cta">{m[key]:,} {label}</span>')
    if m.get("watch_min"):
        chips.append(f'<span class="cta">{m["watch_min"]:g} min watched</span>')
    return (f'<div class="tslide">{render_media(c.get("media"))}'
            f'<div class="pmeta">{"".join(chips)}</div>'
            f'<div class="ptitle">{esc(c.get("title",""))}</div></div>')


def render_performance(cfg):
    """Server-render the Performance panel from cfg['kpis'] (hidden until its tab)."""
    k = cfg.get("kpis")
    if not k:
        return '<section class="card" id="perf" hidden><p class="snote">Performance data will appear once metrics sync.</p></section>'

    def fmt(n):
        return f"{n:,}" if isinstance(n, (int, float)) else "—"

    bookings = k.get("bookings")
    rate = k.get("engagement_rate_total")
    win = k.get("window_days", 30)
    cards = [
        ("Bookings", (str(bookings) if bookings is not None else "—"),
         "Calendly" if bookings is not None else "connect Calendly"),
        ("Total views", fmt(k.get("views", 0)), f"all platforms · {win} days"),
        ("Engagement", fmt(k.get("engagement", 0)),
         (f"{rate}% of views" if rate else "")),
    ]
    if k.get("followers"):
        cards.append(("Followers", fmt(k.get("followers", 0)), "all platforms"))
    else:
        cards.append(("Impressions", fmt(k.get("impressions", 0)), ""))
    kpi_cards = "".join(
        f'<div class="kpi"><div class="kval">{esc(v)}</div><div class="klabel">{esc(lbl)}</div>'
        f'{(chr(60)+"div class=ksub"+chr(62)+esc(sub)+chr(60)+"/div"+chr(62)) if sub else ""}</div>'
        for lbl, v, sub in cards)
    top = k.get("top_posts", [])
    slides = "".join(_topslide(c) for c in top)
    carousel = (
        f'<div class="calhead" style="margin-top:16px">Top posts</div>'
        f'<div class="topcar">{slides}</div>'
        f'<p class="snote">swipe to see the top {len(top)} →</p>'
    ) if top else '<p class="snote">No posts with metrics yet.</p>'
    # Merged platforms (facebook = page + personal), sorted by views.
    rows = sorted(k.get("by_platform", {}).items(),
                  key=lambda kv: kv[1].get("views", 0), reverse=True)
    plat = "".join(
        f'<tr><td>{esc(p)}</td><td>{v.get("views",0):,}</td>'
        f'<td>{v.get("engagement",0):,}</td><td>{_rate(v.get("engagement",0), v.get("views",0))}</td></tr>'
        for p, v in rows)
    fb_drill = render_fb_drilldown(k)
    top_by_platform = k.get("top_by_platform", {})
    buffer_drills = "".join(
        render_buffer_platform_drilldown(p, top_by_platform[p], k.get("by_platform", {}).get(p, {}))
        for p, _ in rows if p in top_by_platform)
    return f"""<section class="card" id="perf" hidden>
      <div class="kpis">{kpi_cards}</div>
      {carousel}
      <details><summary>By platform</summary>
        <table class="ptable"><tr><th>Platform</th><th>Views</th><th>Eng</th><th>Rate</th></tr>{plat}</table>
      </details>
      {buffer_drills}
      {fb_drill}
      <p class="snote">Updated {esc(k.get('updated',''))}</p>
    </section>"""


_PLAT_NAMES = {"instagram": "Instagram", "facebook": "Facebook",
               "tiktok": "TikTok", "linkedin": "LinkedIn", "youtube": "YouTube"}


def _rate(eng, views):
    """Engagement rate as a percent string (engagement over views); — when no views."""
    return f"{round(eng / views * 100, 1)}%" if views else "—"


def render_buffer_platform_drilldown(platform, plat_posts, totals=None):
    """Drill-down for a Buffer-tracked platform: per-platform summary + views-by-type
    bars + top posts with links. `totals` is the by_platform entry (views/engagement)."""
    if not plat_posts:
        return ""
    label = _PLAT_NAMES.get(platform, platform.title())
    totals = totals or {}
    pv, pe = totals.get("views", 0), totals.get("engagement", 0)
    summary_line = (f'<p class="snote" style="text-align:left;margin:6px 0 2px">'
                    f'{pv:,} views · {pe:,} engagement · {_rate(pe, pv)} rate</p>'
                    if (pv or pe) else "")
    by_type = {}
    for c in plat_posts:
        t = c.get("asset_type", "Image")
        by_type[t] = by_type.get(t, 0) + c["m"].get("views", 0)
    total = sum(by_type.values()) or 1
    type_bars = "".join(
        f'<div class="bar"><span class="blabel">{esc(t)}</span>'
        f'<span class="btrack"><span class="bfill" style="width:{round(v*100/total)}%"></span></span>'
        f'<span class="bpct">{round(v*100/total)}%</span></div>'
        for t, v in sorted(by_type.items(), key=lambda x: x[1], reverse=True))

    def tp(c):
        m = c.get("m", {})
        parts = []
        if m.get("likes"): parts.append(f'{m["likes"]:,} likes')
        if m.get("comments"): parts.append(f'{m["comments"]:,} comments')
        if m.get("shares"): parts.append(f'{m["shares"]:,} shares')
        if m.get("saves"): parts.append(f'{m["saves"]:,} saves')
        if m.get("watch_min"): parts.append(f'{m["watch_min"]:g} min watched')
        stats = " · ".join(parts)
        date_chip = f'<span class="cta">{esc(c.get("date",""))}</span>' if c.get("date") else ""
        link = (f'<a class="tp-link" href="{esc(c["externalLink"])}" target="_blank" rel="noopener">View post →</a>'
                if c.get("externalLink") else "")
        return (f'<div class="toppost"><div class="pmeta">'
                f'<span class="ptime">{m.get("views",0):,} views</span>'
                f'<span class="cta">{esc(c.get("asset_type",""))}</span>{date_chip}</div>'
                f'<div class="ptitle">{esc(c.get("title",""))}</div>'
                f'<div class="tp-stats">{esc(stats)}</div>{link}</div>')

    tops = "".join(tp(c) for c in plat_posts)
    type_section = (f'<div class="subhead">Views by content type</div>{type_bars}'
                    if len(by_type) > 1 else "")
    return f"""<details>
      <summary>{esc(label)} — top posts by views</summary>
      {summary_line}
      {type_section}
      <div class="subhead">Top posts</div>
      {tops}
    </details>"""


def render_fb_drilldown(k):
    """Drill into what drives the Facebook personal-profile reach."""
    fb = k.get("facebook_personal_detail")
    if not fb:
        return ""
    bars = "".join(
        f'<div class="bar"><span class="blabel">{esc(t)}</span>'
        f'<span class="btrack"><span class="bfill" style="width:{pct}%"></span></span>'
        f'<span class="bpct">{pct}%</span></div>'
        for t, pct in fb.get("views_by_type", []))
    def tp(p):
        if not isinstance(p, dict):   # backward-compat with the old [title, views] shape
            return f'<div class="toppost"><div class="tp-stats">{esc(str(p))}</div></div>'
        stats = " · ".join(filter(None, [
            f'{p.get("reactions",0):,} reactions', f'{p.get("comments",0):,} comments',
            f'{p.get("shares",0):,} shares', (f'{p["saves"]:,} saves' if p.get("saves") else ""),
        ]))
        date_chip = f'<span class="cta">{esc(p.get("date",""))}</span>' if p.get("date") else ""
        link = (f'<a class="tp-link" href="{esc(p["permalink"])}" target="_blank" rel="noopener">View post →</a>'
                if p.get("permalink") else "")
        return ('<div class="toppost"><div class="pmeta">'
                f'<span class="ptime">{p.get("views",0):,} views</span>'
                f'<span class="cta">{esc(p.get("type",""))}</span>{date_chip}</div>'
                f'<div class="ptitle">{esc(p.get("title",""))}</div>'
                f'<div class="tp-stats">{esc(stats)}</div>{link}</div>')
    tops = "".join(tp(p) for p in fb.get("top_posts", []))
    split = " · ".join(f"{esc(s)} {p}%" for s, p in fb.get("followers_split", []))
    return f"""<details>
      <summary>Facebook reach breakdown ({esc(fb.get('window',''))})</summary>
      <div class="subhead">Views by content type</div>{bars}
      {f'<div class="subhead">Audience</div><p class="snote" style="text-align:left;margin:2px 0">{split}</p>' if split else ''}
      <div class="subhead">Top Facebook posts (by views)</div>
      {tops}
    </details>"""


def _by_date(items, render):
    out = {}
    for it in items:
        d = it.get("iso_date")
        if not d:
            continue
        out.setdefault(d, []).append(render(it))
    return out


def page(cfg):
    th = cfg.get("theme", {})
    accent = th.get("accent", "#1f6f54"); soft = th.get("soft", "#e8f1ec")
    sborder = th.get("soft_border", "#cfe2d8"); atext = th.get("accent_text", "#16503c")
    sbg = th.get("story_bg", "#0d5f6e")

    posts_by = _by_date(cfg.get("feed", []), render_post_block)
    stories_by = _by_date(cfg.get("stories", []), render_story_block)
    perf_html = render_performance(cfg)
    logo = _logo_data_uri()
    client_name = cfg.get("name", "")
    ifbar = (f'<div class="ifbar">'
             f'{f"""<img src="{logo}" alt="Island Forge Studio">""" if logo else "<span></span>"}'
             f'<span class="rep">{esc(client_name)}</span></div>') if (logo or client_name) else ""

    updated = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=-5))
    ).strftime("%b %-d, %-I:%M %p CT")

    data_json = json.dumps({"posts": posts_by, "stories": stories_by})

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(cfg.get('title','Content Preview'))}</title>
<style>
 :root{{--ink:#1c1c1a;--muted:#6b6760;--line:#e7e3db;--bg:#f6f3ee;--card:#fff;--accent:{accent};--soft:{soft};--chip:#f0ece4}}
 *{{box-sizing:border-box;-webkit-text-size-adjust:100%}}
 body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
 .wrap{{max-width:540px;margin:0 auto;padding:16px 14px calc(40px + env(safe-area-inset-bottom))}}
 .ifbar{{display:flex;align-items:center;justify-content:space-between;background:#2B2B26;margin:-16px -14px 0;padding:11px 16px}}
 .ifbar img{{height:22px;width:auto;display:block}}
 .ifbar .rep{{color:#FBF5EE;font-size:12.5px;font-weight:600;opacity:.85}}
 .top{{position:sticky;top:0;background:rgba(246,243,238,.92);backdrop-filter:blur(8px);margin:0 -14px 14px;padding:14px;border-bottom:1px solid var(--line);z-index:5}}
 h1{{font-size:20px;margin:0;letter-spacing:-.01em}} .meta{{color:var(--muted);font-size:13px;margin-top:2px}}
 .banner{{background:var(--soft);border:1px solid {sborder};color:{atext};border-radius:12px;padding:11px 13px;font-size:13.5px;margin:0 0 16px}}
 .tabs{{display:flex;gap:0;border:1px solid var(--line);border-radius:999px;padding:3px;margin:0 0 14px;background:var(--card)}}
 .tab{{flex:1;border:none;background:transparent;color:var(--muted);font:inherit;font-weight:600;padding:8px 0;border-radius:999px;cursor:pointer}}
 .tab.on{{background:var(--accent);color:#fff}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:16px;box-shadow:0 1px 2px rgba(0,0,0,.03)}}
 .calnav{{display:flex;align-items:center;justify-content:space-between;margin:0 0 10px}}
 .calnav button{{border:1px solid var(--line);background:var(--card);width:34px;height:34px;border-radius:50%;font-size:16px;cursor:pointer;color:var(--ink)}}
 .calnav .calhead{{font-weight:700;font-size:15px}}
 .cal{{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}}
 .cdow{{text-align:center;font-size:11px;font-weight:700;color:var(--muted);padding:2px 0}}
 .ccell{{aspect-ratio:1/1;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:13px;color:#9a958c;border-radius:10px;position:relative}}
 .ccell.empty{{visibility:hidden}}
 .ccell.has{{background:var(--soft);color:var(--accent);font-weight:700;cursor:pointer;border:1px solid {sborder}}}
 .dot{{width:6px;height:6px;border-radius:50%;background:var(--accent);margin-top:3px}}
 .snote{{font-size:12.5px;color:var(--muted);margin:10px 0 0;text-align:center}}
 .kpis{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:10px}}
 .kpi{{background:var(--soft);border:1px solid {sborder};border-radius:12px;padding:14px}}
 .kval{{font-size:24px;font-weight:700;color:{atext}}}
 .klabel{{font-size:13px;color:var(--muted);margin-top:2px}}
 .ksub{{font-size:11.5px;color:var(--muted);margin-top:2px}}
 .topcar{{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding-bottom:6px}}
 .tslide{{flex:0 0 100%;scroll-snap-align:center}}
 .ptable{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}
 .ptable th,.ptable td{{text-align:left;padding:5px 6px;border-bottom:1px solid var(--line)}}
 .ptable td:not(:first-child),.ptable th:not(:first-child){{text-align:right}}
 .subhead{{font-weight:600;font-size:13px;margin:12px 0 4px}}
 .bar{{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:13px}}
 .blabel{{width:88px;color:var(--muted)}}
 .btrack{{flex:1;height:8px;background:var(--line);border-radius:999px;overflow:hidden}}
 .bfill{{display:block;height:100%;background:var(--accent)}}
 .bpct{{width:44px;text-align:right;color:var(--muted)}}
 .toppost{{border-top:1px solid var(--line);padding:10px 0}}
 .tp-stats{{font-size:12.5px;color:var(--muted);margin:2px 0 4px}}
 .tp-link{{font-size:13px;font-weight:600;color:var(--accent);text-decoration:none}}
 video,.gallery img{{width:100%;max-width:320px;display:block;margin:0 auto 10px;border-radius:14px;background:#000;aspect-ratio:9/16;object-fit:cover}}
 .gallery{{display:flex;gap:8px;overflow-x:auto}} .gallery img{{height:300px;width:auto}}
 .count{{font-size:12.5px;color:var(--muted);margin-bottom:6px}}
 .post{{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}} .post:first-child{{border-top:none;margin-top:0;padding-top:0}}
 .pmeta{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 6px}}
 .ptime{{background:var(--accent);color:#fff;font-weight:600;font-size:12.5px;padding:3px 10px;border-radius:999px}}
 .cta{{background:var(--soft);color:{atext};border:1px solid {sborder};font-weight:600;font-size:12.5px;padding:3px 10px;border-radius:999px}}
 .ptitle{{font-size:15px;font-weight:600;margin:0 0 8px;line-height:1.3;color:var(--muted)}}
 .schip{{font-size:13.5px;color:var(--ink);margin-top:4px}}
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
 {ifbar}
 <div class="top"><h1>{esc(cfg.get('title','Content Preview'))}</h1><div class="meta">updated {updated}</div></div>
 <div class="tabs">
   <button class="tab on" data-tab="posts">Posts</button>
   <button class="tab" data-tab="stories">Stories</button>
   <button class="tab" data-tab="performance">Performance</button>
 </div>
 <section class="card" id="calcard">
   <div class="calnav"><button id="prev" aria-label="Previous month">‹</button>
     <div class="calhead" id="calhead"></div>
     <button id="next" aria-label="Next month">›</button></div>
   <div class="cal" id="cal"></div>
   <p class="snote" id="snote"></p>
 </section>
 {perf_html}
 <footer>{esc(cfg.get('footer',''))}</footer>
</div>
<div id="dmodal" class="modal" hidden><div class="mback"></div>
 <div class="msheet"><button class="mclose" aria-label="Close">✕</button>
  <div class="mday"></div><div class="mbody"></div></div></div>
<script>
 var DATA={data_json};
 var DOW=["S","M","T","W","T","F","S"], MON=["January","February","March","April","May","June","July","August","September","October","November","December"];
 var tab="posts", cur=startMonth();
 function startMonth(){{
   var d=new Date();  // always open on today's month
   return {{y:d.getFullYear(), m:d.getMonth()}};
 }}
 function fmtDay(iso){{var p=iso.split("-");var dt=new Date(p[0],p[1]-1,p[2]);
   return dt.toLocaleDateString(undefined,{{weekday:'long',month:'long',day:'numeric'}});}}
 function render(){{
   var set=DATA[tab]||{{}};
   document.getElementById('calhead').textContent=MON[cur.m]+" "+cur.y;
   var first=new Date(cur.y,cur.m,1), lead=(first.getDay()), ndays=new Date(cur.y,cur.m+1,0).getDate();
   var html=DOW.map(function(x){{return '<div class="cdow">'+x+'</div>';}}).join('');
   for(var i=0;i<lead;i++) html+='<div class="ccell empty"></div>';
   for(var dn=1;dn<=ndays;dn++){{
     var iso=cur.y+"-"+String(cur.m+1).padStart(2,'0')+"-"+String(dn).padStart(2,'0');
     if(set[iso]&&set[iso].length){{html+='<div class="ccell has" data-date="'+iso+'" role="button" tabindex="0">'+dn+'<span class="dot"></span></div>';}}
     else{{html+='<div class="ccell">'+dn+'</div>';}}
   }}
   document.getElementById('cal').innerHTML=html;
   var n=Object.keys(set).length;
   document.getElementById('snote').textContent=n?('Tap a highlighted day to see the '+tab+'.'):('No '+tab+' scheduled.');
   document.querySelectorAll('.ccell.has').forEach(function(c){{
     c.addEventListener('click',function(){{openDay(c.dataset.date);}});
     c.addEventListener('keydown',function(e){{if(e.key==='Enter'||e.key===' '){{e.preventDefault();openDay(c.dataset.date);}}}});
   }});
 }}
 var m=document.getElementById('dmodal');
 function openDay(d){{var x=(DATA[tab]||{{}})[d];if(!x)return;
   m.querySelector('.mday').textContent=fmtDay(d);
   m.querySelector('.mbody').innerHTML=x.join('');
   m.hidden=false;document.body.style.overflow='hidden';}}
 function closeD(){{m.querySelectorAll('video').forEach(function(v){{try{{v.pause();}}catch(e){{}}}});m.hidden=true;document.body.style.overflow='';}}
 m.querySelector('.mback').addEventListener('click',closeD);
 m.querySelector('.mclose').addEventListener('click',closeD);
 document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeD();}});
 document.getElementById('prev').addEventListener('click',function(){{cur.m--;if(cur.m<0){{cur.m=11;cur.y--;}}render();}});
 document.getElementById('next').addEventListener('click',function(){{cur.m++;if(cur.m>11){{cur.m=0;cur.y++;}}render();}});
 var perf=document.getElementById('perf'), calcard=document.getElementById('calcard');
 document.querySelectorAll('.tab').forEach(function(t){{t.addEventListener('click',function(){{
   document.querySelectorAll('video').forEach(function(v){{try{{v.pause();}}catch(e){{}}}});
   document.querySelectorAll('.tab').forEach(function(x){{x.classList.remove('on');}});
   t.classList.add('on');
   if(t.dataset.tab==='performance'){{ if(perf) perf.hidden=false; calcard.hidden=true; return; }}
   if(perf) perf.hidden=true; calcard.hidden=false;
   tab=t.dataset.tab; cur=startMonth(); render();
 }});}});
 render();
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
