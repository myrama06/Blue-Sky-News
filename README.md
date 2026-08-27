# Blue Sky News Phase 2
Automatic news discovery backend.

Render: Root Directory `backend`; Build `pip install -r requirements.txt`; Start `gunicorn app:app`; Health `/health`.
Environment: `DATABASE_URL`, `NEWS_FEEDS`.
Phase 2 discovers and stores source metadata only. It does not automatically declare stories true or publish to Facebook.
