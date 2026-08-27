# Blue Sky News — Phase 2 Automatic News Scanner

Discovery/ingestion backend. It reads configured RSS feeds, detects new items, stores headline/short summary/source URL, and deduplicates by story URL. New items are `developing`.

It does NOT claim truth, invent facts, or publish to Facebook. Verification comes in Phase 3.

Render Web Service:
Build: `pip install -r backend/requirements.txt`
Start: `gunicorn --chdir backend app:app`
Health: `/health`

Required environment variables:
- `DATABASE_URL` = Render Postgres connection string
- `SCANNER_TOKEN` = strong secret
- `NEWS_FEEDS` = comma-separated RSS URLs

Default feeds are BBC News RSS and Al Jazeera RSS. Add sources only where automated use is permitted by their terms/licensing.

For reliable scheduling, use a scheduled job/cron to run a scan rather than an in-process timer.
