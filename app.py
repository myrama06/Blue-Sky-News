import argparse
import html
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")

DEFAULT_FEED = "https://feeds.bbci.co.uk/news/rss.xml"

FEEDS = [
    x.strip()
    for x in os.getenv("NEWS_FEEDS", DEFAULT_FEED).split(",")
    if x.strip()
]


def db():
    import psycopg

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg.connect(DATABASE_URL)


def init_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stories (
                id BIGSERIAL PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT DEFAULT '',
                story_url TEXT NOT NULL UNIQUE,
                published_at TEXT,
                discovered_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'developing'
            )
            """
        )
        conn.commit()


def clean(value):
    return " ".join(html.unescape(value or "").split())


def scan():
    init_db()

    new_stories = 0
    errors = []

    with db() as conn:
        for feed_url in FEEDS:
            try:
                response = requests.get(
                    feed_url,
                    timeout=20,
                    headers={
                        "User-Agent": "BlueSkyNews/2.0"
                    },
                )

                response.raise_for_status()

                root = ET.fromstring(response.content)

                host = (
                    urlparse(feed_url)
                    .netloc
                    .replace("www.", "")
                    .split(".")[0]
                    .upper()
                )

                for item in root.findall(".//item")[:50]:

                    def text(tag):
                        node = item.find(tag)
                        return clean(
                            node.text if node is not None else ""
                        )

                    title = text("title")
                    link = text("link")

                    if not title or not link:
                        continue

                    cursor = conn.execute(
                        """
                        INSERT INTO stories (
                            source_name,
                            source_url,
                            title,
                            summary,
                            story_url,
                            published_at,
                            discovered_at,
                            status
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        ON CONFLICT (story_url) DO NOTHING
                        """,
                        (
                            host,
                            feed_url,
                            title[:500],
                            text("description")[:2000],
                            link[:2000],
                            text("pubDate")[:100],
                            datetime.now(timezone.utc).isoformat(),
                            "developing",
                        ),
                    )

                    new_stories += cursor.rowcount

            except Exception as exc:
                errors.append(
                    {
                        "feed": feed_url,
                        "error": str(exc)[:300],
                    }
                )

        conn.commit()

    return {
        "new_stories": new_stories,
        "errors": errors,
    }


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "blue-sky-news-scanner",
        }
    )


@app.get("/api/stories")
def stories():
    init_db()

    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                source_name,
                title,
                summary,
                story_url,
                published_at,
                discovered_at,
                status
            FROM stories
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()

    keys = [
        "id",
        "source_name",
        "title",
        "summary",
        "story_url",
        "published_at",
        "discovered_at",
        "status",
    ]

    return jsonify(
        [dict(zip(keys, row)) for row in rows]
    )


@app.post("/api/scan")
def run_scan():
    return jsonify(scan())


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scan",
        action="store_true",
    )

    args = parser.parse_args()

    if args.scan:
        print(scan())
        return

    port = int(
        os.getenv("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
