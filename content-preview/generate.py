#!/usr/bin/env python3
"""Multi-tenant content-review site generator.
Reads clients/<slug>/config.json and writes clients/<slug>/index.html.
Also writes a root index.html that redirects to DEFAULT_CLIENT.
Run:  python3 generate.py
Add a client: create clients/<slug>/config.json (+ a stories/ folder) and re-run.
"""
import html, datetime, json, glob, os

DEFAULT_CLIENT = "deba"

def esc(s): return html.escape(s)

def render_feed(cfg):
    feed_time = cfg.get("feed_time","")
    out=""
    for d in cfg.get("feed",[]):
        chips="".join(f'<span class="chip">{esc(c)}</span>' for c in d.get("chips",[]))
        m=d["media"]
        if m["type"]=="video":
            media=f'<video controls preload="none" playsinline poster="{m["poster"]}" src="{m["src"]}"></video>'
        else:
            imgs=m["images"]
            media='<div class="gallery">'+"".join(f'<img loading="lazy" src="{u}">' for u in imgs)+'</div>'
            media+=f'<div class="count">🖼️ {len(imgs)}-photo carousel · swipe →</div>'
        caps="".join(f'<div class="cap"><h4>{esc(lbl)}</h4><p>{esc(t)}</p></div>' for lbl,t in d.get("caps",[]))
        t=d.get("time",feed_time)
        out+=f"""
  <section class="card">
    <div class="day">{esc(d['date'])}{(' · '+esc(t)) if t else ''}</div>
    {media}
    <h2 class="title">{esc(d['title'])}</h2>
    <div class="chips">{chips}</div>
    <details><summary>Captions per platform</summary><div class="caps">{caps}</div></details>
  </section>"""
    return out

def render_stories(cfg):
    st=cfg.get("stories")
    if not st: return "", "", ""
    items={int(i["day"]):i for i in st["items"]}
    y,mo=st["year"],st["month"]
    first=datetime.date(y,mo,1)
    ndays=(datetime.date(y+(mo==12),(mo%12)+1,1)-first).days
    lead=(first.weekday()+1)%7
    cells=""
    for _ in range(lead): cells+='<div class="ccell empty"></div>'
    for dn in range(1,ndays+1):
        if dn in items:
            cells+=f'<div class="ccell has" data-day="{dn}" role="button" tabindex="0">{dn}<span class="dot"></span></div>'
        else:
            cells+=f'<div class="ccell">{dn}</div>'
    dow="".join(f'<div class="cdow">{x}</div>' for x in ["S","M","T","W","T","F","S"])
    SJS=json.dumps({i["day"]:{"dow":i["dow"],"time":i["time"],"title":i["title"],"sticker":i["sticker"],"img":i["img"]} for i in st["items"]})
    block=f"""
  <section class="card">
    <div class="day">📱 Instagram Stories · {esc(st.get('channel',''))}</div>
    <div class="calhead">{esc(st.get('month_label',''))}</div>
    <div class="cal">{dow}{cells}</div>
    <p class="snote">Tap a highlighted day to see that day's story.</p>
  </section>"""
    modal="""
 <div id="smodal" class="modal" hidden><div class="mback"></div>
  <div class="msheet"><button class="mclose" aria-label="Close">✕</button>
   <div class="mday"></div><img class="mimg" alt=""><div class="mtitle"></div><div class="mchip"></div></div></div>"""
    script=f"""<script>
 var S={SJS}, MONTH={json.dumps(st.get('month_label','').split(' ')[0][:3])};
 var m=document.getElementById('smodal');
 function openS(d){{var s=S[d];if(!s)return;
   m.querySelector('.mday').textContent=s.dow+' · '+MONTH+' '+d+' · '+s.time;
   m.querySelector('.mimg').src=s.img;
   m.querySelector('.mtitle').textContent=s.title;
   m.querySelector('.mchip').textContent=s.sticker;
   m.hidden=false;document.body.style.overflow='hidden';}}
 function closeS(){{m.hidden=true;document.body.style.overflow='';}}
 document.querySelectorAll('.ccell.has').forEach(function(c){{
   c.addEventListener('click',function(){{openS(c.dataset.day);}});
   c.addEventListener('keydown',function(e){{if(e.key==='Enter'||e.key===' '){{e.preventDefault();openS(c.dataset.day);}}}});
 }});
 m.querySelector('.mback').addEventListener('click',closeS);
 m.querySelector('.mclose').addEventListener('click',closeS);
 document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeS();}});
</script>"""
    return block, modal, script

def page(cfg):
    th=cfg.get("theme",{})
    accent=th.get("accent","#1f6f54"); soft=th.get("soft","#e8f1ec")
    sborder=th.get("soft_border","#cfe2d8"); atext=th.get("accent_text","#16503c")
    sbg=th.get("story_bg","#0d5f6e")
    feed=render_feed(cfg)
    sblock,smodal,sscript=render_stories(cfg)
    updated=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime("%b %-d, %-I:%M %p CT")
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(cfg['title'])}</title>
<style>
 :root{{--ink:#1c1c1a;--muted:#6b6760;--line:#e7e3db;--bg:#f6f3ee;--card:#fff;--accent:{accent};--soft:{soft};--chip:#f0ece4}}
 *{{box-sizing:border-box;-webkit-text-size-adjust:100%}}
 body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
 .wrap{{max-width:540px;margin:0 auto;padding:16px 14px calc(40px + env(safe-area-inset-bottom))}}
 .top{{position:sticky;top:0;background:rgba(246,243,238,.92);backdrop-filter:blur(8px);margin:-16px -14px 14px;padding:14px;border-bottom:1px solid var(--line);z-index:5}}
 h1{{font-size:20px;margin:0;letter-spacing:-.01em}} .meta{{color:var(--muted);font-size:13px;margin-top:2px}}
 .banner{{background:var(--soft);border:1px solid {sborder};color:{atext};border-radius:12px;padding:11px 13px;font-size:13.5px;margin:0 0 18px}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:16px;box-shadow:0 1px 2px rgba(0,0,0,.03)}}
 .day{{display:inline-block;background:var(--accent);color:#fff;font-weight:600;font-size:12.5px;padding:4px 11px;border-radius:999px;margin-bottom:12px}}
 video{{width:100%;max-width:320px;display:block;margin:0 auto 12px;border-radius:14px;background:#000;aspect-ratio:9/16;object-fit:cover}}
 .gallery{{display:flex;gap:8px;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding-bottom:6px;margin-bottom:6px}}
 .gallery img{{height:300px;border-radius:12px;scroll-snap-align:center;flex:0 0 auto;background:#eee}}
 .count{{font-size:12.5px;color:var(--muted);margin-bottom:6px}}
 .calhead{{font-weight:700;font-size:14px;text-align:center;margin:2px 0 8px}}
 .cal{{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}}
 .cdow{{text-align:center;font-size:11px;font-weight:700;color:var(--muted);padding:2px 0}}
 .ccell{{aspect-ratio:1/1;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:13px;color:#9a958c;border-radius:10px}}
 .ccell.empty{{visibility:hidden}}
 .ccell.has{{background:var(--soft);color:var(--accent);font-weight:700;cursor:pointer;border:1px solid {sborder};position:relative}}
 .dot{{width:6px;height:6px;border-radius:50%;background:var(--accent);margin-top:3px}}
 .snote{{font-size:12.5px;color:var(--muted);margin:10px 0 0;text-align:center}}
 .modal{{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;padding:18px}}
 .modal[hidden]{{display:none}}
 .mback{{position:absolute;inset:0;background:rgba(20,20,18,.62);backdrop-filter:blur(2px)}}
 .msheet{{position:relative;background:var(--card);border-radius:18px;padding:14px;max-width:330px;width:100%;max-height:92vh;overflow:auto;box-shadow:0 12px 40px rgba(0,0,0,.3)}}
 .mclose{{position:absolute;top:8px;right:8px;border:none;background:#0000000d;width:30px;height:30px;border-radius:50%;font-size:15px;cursor:pointer;color:var(--ink)}}
 .mday{{font-size:12px;font-weight:600;color:var(--accent);margin:2px 0 8px}}
 .mimg{{width:100%;border-radius:12px;display:block;background:{sbg};aspect-ratio:9/16;object-fit:cover}}
 .mtitle{{font-size:16px;font-weight:650;margin-top:10px;line-height:1.3}}
 .mchip{{font-size:13px;color:var(--muted);margin-top:5px;line-height:1.4}}
 .title{{font-size:17px;font-weight:650;margin:0 0 10px;line-height:1.3}}
 .chips{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:4px}}
 .chip{{background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:4px 11px;font-size:12.5px;color:#4a463f}}
 details{{margin-top:10px;border-top:1px solid var(--line)}}
 summary{{cursor:pointer;list-style:none;padding:12px 2px 4px;font-size:14px;font-weight:600;color:var(--accent)}}
 summary::-webkit-details-marker{{display:none}} summary:after{{content:" ▾";color:var(--muted)}}
 .cap{{border-top:1px dashed var(--line);padding:11px 0}} .cap:first-child{{border-top:none}}
 .cap h4{{margin:0 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}
 .cap p{{margin:0;white-space:pre-wrap;font-size:14px}}
 footer{{color:var(--muted);font-size:12.5px;text-align:center;margin-top:22px}}
</style></head><body><div class="wrap">
 <div class="top"><h1>{esc(cfg['title'])}</h1><div class="meta">{esc(cfg.get('range_label',''))} · updated {updated}</div></div>
 <div class="banner">{cfg.get('banner','')}</div>
 {sblock}
 {feed}
 <footer>{esc(cfg.get('footer',''))}</footer>
</div>{smodal}{sscript}</body></html>"""

def main():
    built=[]
    for cf in sorted(glob.glob("clients/*/config.json")):
        cfg=json.load(open(cf))
        slug=cfg["slug"]
        outp=f"clients/{slug}/index.html"
        open(outp,"w").write(page(cfg))
        built.append((slug,outp))
        print("built",outp)
    # root redirect to default client
    redirect=f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=clients/{DEFAULT_CLIENT}/"><link rel="canonical" href="clients/{DEFAULT_CLIENT}/"><title>Redirecting…</title><a href="clients/{DEFAULT_CLIENT}/">Continue →</a>'
    open("index.html","w").write(redirect)
    print("built index.html -> clients/%s/"%DEFAULT_CLIENT)
    print("clients:",[b[0] for b in built])

if __name__=="__main__":
    main()
