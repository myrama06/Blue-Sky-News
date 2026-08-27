import os, html
from datetime import datetime, timezone
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests
from flask import Flask, jsonify, request, render_template_string

app=Flask(__name__)
DATABASE_URL=os.getenv("DATABASE_URL","").strip()
FEEDS=[x.strip() for x in os.getenv("NEWS_FEEDS","https://feeds.bbci.co.uk/news/rss.xml,https://www.aljazeera.com/xml/rss/all.xml").split(",") if x.strip()]
UA="BlueSkyNews/2.0 news-scanner"

def conn():
    import psycopg
    return psycopg.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL: raise RuntimeError("DATABASE_URL is required")
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS stories(
        id BIGSERIAL PRIMARY KEY, source_name TEXT NOT NULL, source_url TEXT NOT NULL,
        title TEXT NOT NULL, summary TEXT DEFAULT '', story_url TEXT NOT NULL UNIQUE,
        published_at TEXT, discovered_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'developing')""")
        c.commit()

def clean(x): return " ".join(html.unescape(x or "").split())

def parse(feed):
    r=requests.get(feed,timeout=20,headers={"User-Agent":UA}); r.raise_for_status()
    root=ET.fromstring(r.content); out=[]
    host=urlparse(feed).netloc.lower().replace("www.","")
    name=host.split(".")[0].upper()
    for item in root.findall(".//item")[:50]:
        def t(tag):
            n=item.find(tag); return clean(n.text if n is not None else "")
        title,link=t("title"),t("link")
        if title and link: out.append((name,feed,title[:500],t("description")[:2000],link[:2000],t("pubDate")[:100]))
    return out

def scan_once():
    init_db(); new=0; errors=[]
    with conn() as c:
        for feed in FEEDS:
            try:
                for row in parse(feed):
                    c.execute("""INSERT INTO stories
                    (source_name,source_url,title,summary,story_url,published_at,discovered_at,status)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,'developing')
                    ON CONFLICT(story_url) DO NOTHING""",
                    (*row,datetime.now(timezone.utc).isoformat()))
                    new+=c.rowcount
            except Exception as e: errors.append({"feed":feed,"error":str(e)[:300]})
        c.commit()
    return {"new_stories":new,"errors":errors,"feeds":len(FEEDS)}

@app.get("/health")
def health(): return jsonify({"status":"ok","service":"blue-sky-news-scanner","feeds":len(FEEDS)})

@app.get("/api/stories")
def stories():
    init_db(); limit=min(max(int(request.args.get("limit","30")),1),100)
    with conn() as c:
        rows=c.execute("""SELECT id,source_name,title,summary,story_url,published_at,discovered_at,status
        FROM stories ORDER BY id DESC LIMIT %s""",(limit,)).fetchall()
    keys=["id","source_name","title","summary","story_url","published_at","discovered_at","status"]
    return jsonify([dict(zip(keys,r)) for r in rows])

@app.post("/api/scan")
def scan():
    token=os.getenv("SCANNER_TOKEN","")
    if token and request.headers.get("X-Scanner-Token")!=token: return jsonify({"error":"unauthorized"}),401
    return jsonify(scan_once())

@app.get("/")
def dashboard():
    return render_template_string("""<!doctype html><html><meta name=viewport content="width=device-width,initial-scale=1">
    <title>Blue Sky News Scanner</title><style>
    body{font-family:Arial;margin:0;background:#f4f7fb;color:#10233f}.top{background:#071a33;color:white;padding:20px}
    main{max-width:950px;margin:auto;padding:20px}.card{background:white;padding:18px;margin:12px 0;border-radius:12px}
    .badge{padding:5px 8px;background:#fff0c7;border-radius:12px;font-size:11px;font-weight:bold}a{color:#075fc8}.muted{color:#68758a}
    </style><div class=top><b>☁️ BLUE SKY NEWS — PHASE 2 SCANNER</b></div><main>
    <h1>Automatic News Scanner</h1><p>Discovery only: source URL, headline and feed summary are collected. New items start as DEVELOPING.</p>
    <div id=f>Loading…</div></main><script>
    async function load(){let d=await (await fetch('/api/stories')).json();document.getElementById('f').innerHTML=d.map(x=>
    `<article class=card><span class=badge>${x.status.toUpperCase()}</span><h2>${e(x.title)}</h2>
    <p class=muted>${e(x.source_name)} • ${e(x.published_at||x.discovered_at)}</p><p>${e(x.summary)}</p>
    <a href="${e(x.story_url)}" target=_blank rel=noopener>Open original source →</a></article>`).join('')||'<p>No stories scanned yet.</p>'}
    function e(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]) )}load();setInterval(load,30000)</script>""")

if __name__=="__main__":
    init_db(); app.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")))
