# TalentFlow ATS

A modern Applicant Tracking System built with Python and FastAPI, designed to streamline the recruitment process from job posting to candidate hiring.

## Features

- **Job Management** — Create, update, and manage job postings with detailed descriptions, requirements, and status tracking
- **Candidate Tracking** — Track candidates through customizable hiring pipelines with stage-based workflows
- **Application Processing** — Receive and manage applications with resume parsing and automated screening
- **Interview Scheduling** — Schedule and coordinate interviews with calendar integration and automated notifications
- **Interview Feedback** — Collect structured feedback from interviewers with scoring and recommendation tracking
- **Role-Based Access Control** — Granular permissions for Admins, Hiring Managers, Recruiters, and Interviewers
- **Audit Logging** — Comprehensive activity tracking for compliance and accountability
- **Dashboard & Analytics** — Real-time metrics on hiring pipeline, time-to-hire, and recruiter performance
- **RESTful API** — Fully documented API with OpenAPI/Swagger specification

## Tech Stack

- **Backend:** Python 3.11+, FastAPI
- **Database:** SQLite (development) / PostgreSQL (production) via SQLAlchemy 2.0 (async)
- **Authentication:** JWT (python-jose) with bcrypt password hashing
- **Validation:** Pydantic v2 with email-validator
- **Templating:** Jinja2 with Tailwind CSS
- **Testing:** pytest, pytest-asyncio, httpx

## Folder Structure

```
talentflow-ats/
├── app/
│   ├── core/
│   │   ├── config.py          # Application settings (BaseSettings)
│   │   ├── database.py        # Async SQLAlchemy engine & session
│   │   ├── security.py        # JWT token creation & password hashing
│   │   └── __init__.py
│   ├── models/
│   │   ├── user.py            # User model
│   │   ├── job.py             # Job model
│   │   ├── candidate.py       # Candidate model (+ candidate_skills table)
│   │   ├── application.py     # Application model
│   │   ├── interview.py       # InterviewAssignment & InterviewFeedback
│   │   ├── audit_log.py       # AuditLog model
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── user.py            # User request/response schemas
│   │   ├── job.py             # Job request/response schemas
│   │   ├── candidate.py       # Candidate request/response schemas
│   │   ├── application.py     # Application request/response schemas
│   │   ├── interview.py       # Interview request/response schemas
│   │   ├── audit_log.py       # AuditLog response schemas
│   │   └── __init__.py
│   ├── services/
│   │   ├── user.py            # User CRUD & authentication logic
│   │   ├── job.py             # Job CRUD & search logic
│   │   ├── candidate.py       # Candidate CRUD logic
│   │   ├── application.py     # Application processing logic
│   │   ├── interview.py       # Interview scheduling & feedback logic
│   │   ├── audit_log.py       # Audit logging service
│   │   └── __init__.py
│   ├── routers/
│   │   ├── auth.py            # Authentication routes (login, register)
│   │   ├── users.py           # User management routes
│   │   ├── jobs.py            # Job posting routes
│   │   ├── candidates.py      # Candidate routes
│   │   ├── applications.py    # Application routes
│   │   ├── interviews.py      # Interview routes
│   │   ├── dashboard.py       # Dashboard & analytics routes
│   │   └── __init__.py
│   ├── dependencies/
│   │   ├── auth.py            # get_current_user, role-based guards
│   │   └── __init__.py
│   ├── templates/
│   │   ├── base.html          # Base layout with Tailwind CSS
│   │   ├── dashboard.html     # Dashboard page
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── jobs/
│   │   │   ├── list.html
│   │   │   ├── detail.html
│   │   │   └── form.html
│   │   ├── candidates/
│   │   │   ├── list.html
│   │   │   └── detail.html
│   │   └── applications/
│   │       ├── list.html
│   │       └── detail.html
│   ├── main.py                # FastAPI app entry point
│   └── __init__.py
├── tests/
│   ├── test_auth.py
│   ├── test_jobs.py
│   ├── test_candidates.py
│   ├── test_applications.py
│   └── conftest.py
├── requirements.txt
├── .env.example
├── README.md
└── LICENSE
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/talentflow-ats.git
   cd talentflow-ats
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your settings:

   ```env
   SECRET_KEY=your-secret-key-change-in-production
   DATABASE_URL=sqlite+aiosqlite:///./talentflow.db
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   ENVIRONMENT=development
   ```

5. **Run database migrations (tables auto-created on startup):**

   The application automatically creates all database tables on startup via SQLAlchemy's `create_all`. No manual migration step is required for initial setup.

6. **Start the development server:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access the application:**

   - Web UI: [http://localhost:8000](http://localhost:8000)
   - API Docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)
   - API Docs (ReDoc): [http://localhost:8000/redoc](http://localhost:8000/redoc)

## API Routes Reference

### Authentication

| Method | Path               | Description              | Auth Required |
|--------|--------------------|--------------------------|---------------|
| POST   | `/api/auth/register` | Register a new user      | No            |
| POST   | `/api/auth/login`    | Login and receive JWT    | No            |
| GET    | `/api/auth/me`       | Get current user profile | Yes           |

### Users

| Method | Path              | Description         | Auth Required | Roles         |
|--------|-------------------|---------------------|---------------|---------------|
| GET    | `/api/users`      | List all users      | Yes           | Admin         |
| GET    | `/api/users/{id}` | Get user by ID      | Yes           | Admin         |
| PUT    | `/api/users/{id}` | Update user         | Yes           | Admin         |
| DELETE | `/api/users/{id}` | Deactivate user     | Yes           | Admin         |

### Jobs

| Method | Path             | Description          | Auth Required | Roles                      |
|--------|------------------|----------------------|---------------|-----------------------------|
| GET    | `/api/jobs`      | List all jobs        | Yes           | All                         |
| POST   | `/api/jobs`      | Create a new job     | Yes           | Admin, Hiring Manager       |
| GET    | `/api/jobs/{id}` | Get job details      | Yes           | All                         |
| PUT    | `/api/jobs/{id}` | Update a job         | Yes           | Admin, Hiring Manager       |
| DELETE | `/api/jobs/{id}` | Archive a job        | Yes           | Admin                       |

### Candidates

| Method | Path                   | Description            | Auth Required | Roles                          |
|--------|------------------------|------------------------|---------------|--------------------------------|
| GET    | `/api/candidates`      | List all candidates    | Yes           | All                            |
| POST   | `/api/candidates`      | Create a candidate     | Yes           | Admin, Recruiter               |
| GET    | `/api/candidates/{id}` | Get candidate details  | Yes           | All                            |
| PUT    | `/api/candidates/{id}` | Update a candidate     | Yes           | Admin, Recruiter               |
| DELETE | `/api/candidates/{id}` | Remove a candidate     | Yes           | Admin                          |

### Applications

| Method | Path                              | Description                | Auth Required | Roles                          |
|--------|-----------------------------------|----------------------------|---------------|--------------------------------|
| GET    | `/api/applications`               | List all applications      | Yes           | All                            |
| POST   | `/api/applications`               | Submit an application      | Yes           | Admin, Recruiter               |
| GET    | `/api/applications/{id}`          | Get application details    | Yes           | All                            |
| PUT    | `/api/applications/{id}`          | Update application         | Yes           | Admin, Recruiter, Hiring Mgr   |
| PUT    | `/api/applications/{id}/stage`    | Move to next stage         | Yes           | Admin, Recruiter, Hiring Mgr   |

### Interviews

| Method | Path                              | Description                  | Auth Required | Roles                          |
|--------|-----------------------------------|------------------------------|---------------|--------------------------------|
| GET    | `/api/interviews`                 | List interviews              | Yes           | All                            |
| POST   | `/api/interviews`                 | Schedule an interview        | Yes           | Admin, Recruiter, Hiring Mgr   |
| GET    | `/api/interviews/{id}`            | Get interview details        | Yes           | All                            |
| PUT    | `/api/interviews/{id}`            | Update interview             | Yes           | Admin, Recruiter               |
| POST   | `/api/interviews/{id}/feedback`   | Submit interview feedback    | Yes           | Interviewer                    |

### Dashboard

| Method | Path                    | Description              | Auth Required | Roles |
|--------|-------------------------|--------------------------|---------------|-------|
| GET    | `/api/dashboard/stats`  | Get pipeline statistics  | Yes           | All   |

## Roles & Permissions

| Role             | Description                                                                 |
|------------------|-----------------------------------------------------------------------------|
| **Admin**        | Full system access. Manage users, jobs, candidates, applications, settings. |
| **Hiring Manager** | Create and manage jobs. Review applications and make hiring decisions.    |
| **Recruiter**    | Manage candidates and applications. Schedule interviews. Move pipeline.     |
| **Interviewer**  | View assigned interviews. Submit structured feedback and scores.            |

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_auth.py

# Run with coverage report
pytest --cov=app --cov-report=term-missing
```

## Deployment

### Vercel Deployment

1. **Install the Vercel CLI:**

   ```bash
   npm install -g vercel
   ```

2. **Create a `vercel.json` in the project root:**

   ```json
   {
     "builds": [
       {
         "src": "app/main.py",
         "use": "@vercel/python"
       }
     ],
     "routes": [
       {
         "src": "/(.*)",
         "dest": "app/main.py"
       }
     ]
   }
   ```

3. **Set environment variables in Vercel dashboard:**

   - `SECRET_KEY` — A strong random string (use `openssl rand -hex 32`)
   - `DATABASE_URL` — Your production PostgreSQL connection string (async driver, e.g., `postgresql+asyncpg://...`)
   - `ACCESS_TOKEN_EXPIRE_MINUTES` — Token expiry (e.g., `30`)
   - `ENVIRONMENT` — Set to `production`

4. **Deploy:**

   ```bash
   vercel --prod
   ```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t talentflow-ats .
docker run -p 8000:8000 --env-file .env talentflow-ats
```

### Production Considerations

- Use PostgreSQL with `asyncpg` driver for production workloads
- Set a strong, unique `SECRET_KEY` (minimum 32 characters)
- Configure CORS `allow_origins` to your specific frontend domain(s)
- Enable HTTPS via a reverse proxy (nginx, Caddy) or platform-managed TLS
- Set `ENVIRONMENT=production` to disable debug features
- Use connection pooling for database connections
- Set up log aggregation and monitoring

## Environment Variables

| Variable                      | Description                        | Default                                  |
|-------------------------------|------------------------------------|------------------------------------------|
| `SECRET_KEY`                  | JWT signing secret                 | `change-me-in-production`                |
| `DATABASE_URL`                | Async database connection string   | `sqlite+aiosqlite:///./talentflow.db`    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token expiry in minutes        | `30`                                     |
| `ENVIRONMENT`                 | Runtime environment                | `development`                            |

## License

Private — All rights reserved.