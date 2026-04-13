# TalentFlow ATS — Deployment Guide

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Variables](#environment-variables)
4. [Vercel Configuration](#vercel-configuration)
5. [Build & Output Settings](#build--output-settings)
6. [Database Considerations for Serverless](#database-considerations-for-serverless)
7. [Production Security Settings](#production-security-settings)
8. [CI/CD Notes](#cicd-notes)
9. [Troubleshooting](#troubleshooting)

---

## Overview

TalentFlow ATS is a Python + FastAPI application designed to be deployed on Vercel as a serverless function. This guide covers the full deployment process including environment configuration, database strategy, and production hardening.

---

## Prerequisites

- A [Vercel](https://vercel.com) account linked to your Git provider (GitHub, GitLab, or Bitbucket)
- Python 3.11+ (Vercel's Python runtime)
- The [Vercel CLI](https://vercel.com/docs/cli) installed locally (optional, for manual deploys):
  ```bash
  npm install -g vercel
  ```

---

## Environment Variables

All configuration is managed through environment variables. Set these in the Vercel dashboard under **Project → Settings → Environment Variables**.

### Required Variables

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | JWT signing key. Must be a strong random string (min 32 chars). | `openssl rand -hex 32` |
| `DATABASE_URL` | Database connection string. See [Database Considerations](#database-considerations-for-serverless). | `postgresql+asyncpg://user:pass@host:5432/talentflow` |
| `ENVIRONMENT` | Deployment environment identifier. | `production` |

### Optional Variables

| Variable | Description | Default |
|---|---|---|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token lifetime in minutes. | `30` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins. | `https://yourdomain.com` |
| `LOG_LEVEL` | Python logging level. | `INFO` |
| `COOKIE_SECURE` | Set cookies with `Secure` flag. Must be `true` in production. | `true` |
| `COOKIE_HTTPONLY` | Set cookies with `HttpOnly` flag. | `true` |
| `COOKIE_SAMESITE` | SameSite cookie attribute. | `lax` |

### Setting Variables via Vercel CLI

```bash
vercel env add SECRET_KEY production
vercel env add DATABASE_URL production
vercel env add ENVIRONMENT production
```

### Generating a Secure SECRET_KEY

```bash
# Option 1: OpenSSL
openssl rand -hex 32

# Option 2: Python
python -c "import secrets; print(secrets.token_hex(32))"
```

> **CRITICAL:** Never commit secrets to version control. Never reuse the development SECRET_KEY in production.

---

## Vercel Configuration

Create a `vercel.json` file in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/app/static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ],
  "env": {
    "ENVIRONMENT": "production"
  }
}
```

### Key Points

- **`@vercel/python`** — Vercel's Python runtime automatically installs dependencies from `requirements.txt`.
- **Routes** — All requests are routed to the FastAPI entry point (`app/main.py`), except static file requests which are served directly.
- **The `app` variable** — Vercel expects the ASGI application to be exposed as `app` in the entry point module. Ensure `app/main.py` has a top-level `app = FastAPI(...)` assignment.

---

## Build & Output Settings

### Vercel Dashboard Settings

Navigate to **Project → Settings → General**:

| Setting | Value |
|---|---|
| **Framework Preset** | Other |
| **Build Command** | _(leave empty — Vercel handles Python builds)_ |
| **Output Directory** | _(leave empty)_ |
| **Install Command** | `pip install -r requirements.txt` |
| **Root Directory** | `.` (project root) |

### Python Version

Vercel uses Python 3.12 by default. To pin a specific version, add a `runtime.txt` file in the project root:

```
python-3.11
```

### Dependency Installation

Vercel reads `requirements.txt` from the project root. Ensure all production dependencies are listed:

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
python-multipart>=0.0.6
python-jose[cryptography]>=3.3.0
bcrypt==4.0.1
jinja2>=3.1.0
httpx>=0.26.0
email-validator>=2.1.0
```

> **Note:** Do not include `pytest`, `pytest-asyncio`, or other test-only dependencies in the production `requirements.txt`. If you need separate dev dependencies, use a `requirements-dev.txt` file locally.

---

## Database Considerations for Serverless

### SQLite Limitations on Vercel

**SQLite is NOT suitable for production on Vercel.** Vercel serverless functions run in ephemeral, read-only file systems. This means:

1. **No persistent writes** — Any SQLite database file created at runtime is lost when the function instance is recycled (typically within seconds to minutes).
2. **No shared state** — Multiple concurrent function invocations each get their own isolated file system. There is no shared SQLite file between them.
3. **Read-only `/var/task`** — The deployment bundle directory is read-only. Writing to it raises `OperationalError: attempt to write a readonly database`.

### SQLite for Development Only

SQLite with `aiosqlite` works well for local development and testing:

```
# .env (local development)
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db
```

### Recommended Production Databases

For production on Vercel, use a managed PostgreSQL or MySQL service:

| Provider | Connection String Format |
|---|---|
| **Vercel Postgres** | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| **Neon** | `postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require` |
| **Supabase** | `postgresql+asyncpg://postgres:pass@db.xxx.supabase.co:5432/postgres` |
| **PlanetScale** (MySQL) | `mysql+aiomysql://user:pass@host:3306/dbname?ssl=true` |
| **Railway** | `postgresql+asyncpg://postgres:pass@host.railway.app:5432/railway` |

### Migration Strategy

When switching from SQLite to PostgreSQL:

1. Update `DATABASE_URL` in your Vercel environment variables.
2. Add the async driver to `requirements.txt`:
   ```
   asyncpg>=0.29.0
   ```
3. Run database migrations against the production database before deploying:
   ```bash
   # If using Alembic
   alembic upgrade head
   ```
4. Remove `aiosqlite` from production requirements if no longer needed.

### Connection Pooling

Serverless functions open and close database connections frequently. Configure connection pooling to avoid exhausting database connections:

```python
# app/core/database.py — production pool settings
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=300,  # Recycle connections every 5 minutes
    pool_pre_ping=True,  # Verify connections before use
)
```

> **Tip:** For Neon and Vercel Postgres, enable connection pooling on the provider side as well (PgBouncer mode).

---

## Production Security Settings

### Secure Cookies

All cookie-based sessions and tokens MUST use secure attributes in production:

```python
# Enforced when ENVIRONMENT=production
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,      # Prevents JavaScript access (XSS protection)
    secure=True,        # Cookies sent only over HTTPS
    samesite="lax",     # CSRF protection
    max_age=1800,       # 30 minutes
)
```

Vercel automatically provisions HTTPS for all deployments (both `*.vercel.app` and custom domains), so `secure=True` works out of the box.

### CORS Configuration

In production, restrict CORS to your actual domain(s). Never use `allow_origins=["*"]`:

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),  # e.g., "https://talentflow.example.com"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)
```

Set the `ALLOWED_ORIGINS` environment variable in Vercel:

```
ALLOWED_ORIGINS=https://talentflow.example.com,https://www.talentflow.example.com
```

### HTTPS Enforcement

Vercel handles TLS termination automatically. All traffic to `*.vercel.app` domains and custom domains with Vercel DNS is served over HTTPS. No additional configuration is needed.

If you use a custom domain with external DNS, ensure your DNS provider supports HTTPS and that Vercel's SSL certificate is provisioned (check **Project → Settings → Domains**).

### Security Headers

Add security headers via middleware or `vercel.json`:

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

### Secret Rotation

Periodically rotate the `SECRET_KEY`. When rotating:

1. Set the new key in Vercel environment variables.
2. Redeploy the application.
3. All existing JWT tokens signed with the old key will be invalidated — users will need to re-authenticate.

---

## CI/CD Notes

### Automatic Deployments

Vercel automatically deploys on every push to the connected Git repository:

| Branch | Deployment Type | URL |
|---|---|---|
| `main` / `master` | **Production** | `https://your-project.vercel.app` |
| Feature branches | **Preview** | `https://your-project-<hash>.vercel.app` |
| Pull requests | **Preview** | Linked in the PR as a comment |

### Running Tests Before Deploy

Add a GitHub Actions workflow (`.github/workflows/test.yml`) to run tests before Vercel deploys:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest tests/ -v --tb=short
        env:
          SECRET_KEY: test-secret-key-for-ci-only
          DATABASE_URL: sqlite+aiosqlite:///./test.db
          ENVIRONMENT: testing
```

### Preview Environment Variables

For preview deployments (feature branches, PRs), set separate environment variables scoped to the **Preview** environment in Vercel. This allows you to use a separate test database and non-production secrets for previews.

### Protecting Production Deployments

In the Vercel dashboard under **Project → Settings → Git**:

- Enable **"Require approval for deployments"** for the production branch.
- Enable **"Skip deployments for specific paths"** to avoid redeploying on documentation-only changes (e.g., `docs/**`, `*.md`).

### Build Caching

Vercel caches Python dependencies between builds. If you encounter stale dependency issues:

```bash
# Force a clean build via Vercel CLI
vercel --force

# Or in the dashboard: Deployments → Redeploy → check "Clear Build Cache"
```

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` at runtime | Missing dependency in `requirements.txt` | Add the package to `requirements.txt` and redeploy |
| `500 Internal Server Error` with no logs | Unhandled exception during startup | Check Vercel Function Logs under **Project → Deployments → Functions** |
| `OperationalError: readonly database` | SQLite write on Vercel's read-only filesystem | Switch to a managed PostgreSQL database |
| `ValidationError: extra fields not permitted` | Vercel injects extra env vars (e.g., `VERCEL`, `VERCEL_ENV`) | Ensure Pydantic Settings uses `extra="ignore"` in `model_config` |
| Cookies not being set | Missing `secure=True` on HTTPS or wrong `samesite` | Verify cookie attributes match the production checklist above |
| CORS errors in browser | `ALLOWED_ORIGINS` doesn't include the frontend URL | Update the environment variable with the correct origin(s) |
| `MissingGreenlet` error | Lazy-loaded SQLAlchemy relationship in async context | Add `lazy="selectin"` to all `relationship()` declarations |
| Cold start timeouts | Large dependency bundle or slow DB connection | Enable connection pooling; minimize dependency size |

### Viewing Logs

```bash
# Via Vercel CLI
vercel logs your-project-url --follow

# Or in the dashboard
# Project → Deployments → (select deployment) → Functions → (select function) → Logs
```

### Local Production Simulation

Test the production configuration locally before deploying:

```bash
# Set production-like environment
export ENVIRONMENT=production
export SECRET_KEY=$(openssl rand -hex 32)
export DATABASE_URL=sqlite+aiosqlite:///./local_prod_test.db

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Quick Deploy Checklist

- [ ] `SECRET_KEY` is set to a unique, strong random value (not the dev default)
- [ ] `DATABASE_URL` points to a managed PostgreSQL instance (not SQLite)
- [ ] `ENVIRONMENT` is set to `production`
- [ ] `ALLOWED_ORIGINS` lists only your actual domain(s)
- [ ] `vercel.json` is present in the project root
- [ ] `requirements.txt` contains all production dependencies
- [ ] All tests pass in CI before deploy
- [ ] Database migrations have been applied to the production database
- [ ] Cookie security attributes are enforced (`secure`, `httponly`, `samesite`)
- [ ] Pydantic Settings uses `extra="ignore"` to handle Vercel's injected env vars