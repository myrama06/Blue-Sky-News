import os, html
from datetime import datetime, timezone
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests
from flask import Flask, jsonify
app=Flask(__name__)
DATABASE_URL=os.getenv('DATABASE_URL','')
FEEDS=[x.strip() for x in os.getenv('NEWS_FEEDS','https://feeds.bbci.co.uk/news/rss.xml').split(',') if x.strip()]
def db():
 import psycopg; return psycopg.connect(DATABASE_URL)
def init_db():
 if not DATABASE_URL: raise RuntimeError('DATABASE_URL is not configured')
 with db() as c:
  c.execute('''CREATE TABLE IF NOT EXISTS stories(id BIGSERIAL PRIMARY KEY,source_name TEXT NOT NULL,source_url TEXT NOT NULL,title TEXT NOT NULL,summary TEXT DEFAULT '',story_url TEXT NOT NULL UNIQUE,published_at TEXT,discovered_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'developing')'''); c.commit()
def clean(v): return ' '.join(html.unescape(v or '').split())
def scan():
 init_db(); new=0; errors=[]
 with db() as c:
  for feed in FEEDS:
   try:
    r=requests.get(feed,timeout=20,headers={'User-Agent':'BlueSkyNews/2.0'}); r.raise_for_status(); root=ET.fromstring(r.content); host=urlparse(feed).netloc.replace('www.','').split('.')[0].upper()
    for item in root.findall('.//item')[:50]:
     def t(tag):
      n=item.find(tag); return clean(n.text if n is not None else '')
     title,link=t('title'),t('link')
     if not title or not link: continue
     c.execute('''INSERT INTO stories(source_name,source_url,title,summary,story_url,published_at,discovered_at) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(story_url) DO NOTHING''',(host,feed,title[:500],t('description')[:2000],link[:2000],t('pubDate')[:100],datetime.now(timezone.utc).isoformat())); new+=c.rowcount
   except Exception as e: errors.append({'feed':feed,'error':str(e)[:300]})
  c.commit()
 return {'new_stories':new,'errors':errors}
@app.get('/health')
def health(): return jsonify({'status':'ok','service':'blue-sky-news-scanner'})
@app.get('/api/stories')
def stories():
 init_db()
 with db() as c: rows=c.execute('SELECT id,source_name,title,summary,story_url,published_at,discovered_at,status FROM stories ORDER BY id DESC LIMIT 50').fetchall()
 keys=['id','source_name','title','summary','story_url','published_at','discovered_at','status']; return jsonify([dict(zip(keys,r)) for r in rows])
@app.post('/api/scan')
def run_scan(): return jsonify(scan())
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
