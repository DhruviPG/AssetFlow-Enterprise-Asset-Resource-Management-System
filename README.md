# AssetFlow

Enterprise Asset & Resource Management System built with Flask, SQLAlchemy, Flask-Login, Bootstrap 5, and PostgreSQL-compatible database support.

## What runs locally

By default, the development configuration uses SQLite so the project runs immediately without PostgreSQL credentials. For production, set `DATABASE_URL` to a PostgreSQL connection string.

## Local setup on Windows

```powershell
cd D:\assetflow
.\.venv\Scripts\Activate.ps1
python bootstrap.py
python app.py
```

Open `http://127.0.0.1:5000/` in your browser.

## Optional PostgreSQL setup

If you want PostgreSQL locally or in production, set environment variables before bootstrapping:

```powershell
$env:FLASK_ENV="production"
$env:DATABASE_URL="postgresql+psycopg2://assetflow:assetflow@localhost:5432/assetflow"
$env:ASSETFLOW_SECRET_KEY="change-this-secret"
$env:ASSETFLOW_ADMIN_EMAIL="admin@assetflow.local"
$env:ASSETFLOW_ADMIN_PASSWORD="ChangeMe123!"
python bootstrap.py
python app.py
```

## Deployment

Use the WSGI entrypoint with Gunicorn:

```bash
gunicorn wsgi:app
```

## Current modules

- Authentication: login, signup, logout, and admin promotion
- Dashboard: executive KPIs and operational overview
- Asset management: register assets and browse inventory
- Maintenance: request and review maintenance tickets
- Bookings: schedule and validate reservations
- Database bootstrap: create schema and seed roles/admin user

## Notes

- Signup creates employee accounts only.
- Admin promotion is restricted to administrators.
- The schema is normalized and ready for further ERP-style workflow modules.
