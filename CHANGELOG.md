# Changelog

All notable changes to the TalentFlow ATS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### Added

#### Authentication & Session Management
- User registration with email and password
- Secure login with session cookie-based authentication
- Password hashing using bcrypt for secure credential storage
- Session expiration and logout functionality
- Protected routes requiring authenticated access

#### Role-Based Access Control (RBAC)
- Four distinct user roles: Admin, Hiring Manager, Recruiter, and Interviewer
- Role-based route protection enforcing least-privilege access
- Granular permission checks on all management endpoints
- Role assignment and management by Admin users

#### Job Posting Management
- Full CRUD operations for job postings (create, read, update, delete)
- Job status lifecycle: Draft, Open, Closed, On Hold
- Department and location assignment for job postings
- Rich text job descriptions with requirements and responsibilities
- Filtering and search across job listings

#### Candidate Management
- Candidate profile creation and editing with contact details
- Resume and document upload support
- Skill tagging system with many-to-many candidate-skill associations
- Candidate search and filtering by skills, experience, and status
- Candidate profile detail view with application history

#### Application Pipeline
- Application submission linking candidates to job postings
- Configurable pipeline stages: Applied, Screening, Interview, Offer, Hired, Rejected
- Kanban board view for visual pipeline management
- Drag-and-drop stage transitions on the Kanban board
- Application status tracking with timestamp history
- Bulk actions for moving multiple applications between stages

#### Interview Scheduling & Feedback
- Interview creation with date, time, and location details
- Interviewer assignment to scheduled interviews
- Interview feedback submission with structured rating criteria
- Feedback review and aggregation per candidate application
- Calendar-based interview schedule overview

#### Role-Based Dashboards
- Admin dashboard with system-wide metrics and user management
- Hiring Manager dashboard with job posting and pipeline summaries
- Recruiter dashboard with candidate sourcing and application metrics
- Interviewer dashboard with upcoming interviews and pending feedback
- Key performance indicators displayed per role context

#### Audit Trail
- Comprehensive audit logging for all create, update, and delete operations
- Actor tracking recording which user performed each action
- Timestamped log entries with before and after state capture
- Audit log viewing interface for Admin users
- Filterable audit history by entity type, action, and date range

#### Technical Foundation
- FastAPI backend with async request handling
- SQLAlchemy 2.0 async ORM with SQLite (aiosqlite) database
- Pydantic v2 schemas for request validation and response serialization
- Jinja2 server-side rendered templates with Tailwind CSS styling
- Modular project structure with routers, services, models, and schemas
- CORS middleware configuration for cross-origin support
- Structured logging throughout the application