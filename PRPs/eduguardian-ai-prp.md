# PRP: EduGuardian AI

> Implementation blueprint for parallel agent execution. Detailed models/endpoints live in `INITIAL.md`;
> this file fixes build order, ownership and validation gates.

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | EduGuardian AI |
| **Type** | Multi-tenant SaaS |
| **Version** | 1.0 (MVP / competition demo) |
| **Created** | 2026-10-16 |
| **Complexity** | High (multi-tenancy + LLM agent workflow + reports) |

---

## PRODUCT OVERVIEW

**Description:** Upload marks → validate → deterministic analytics → LLM-drafted intervention plans →
teacher approval → PDF/Excel reports, with every step audit-logged and tenant-isolated.

**Value Proposition:** Turns hours of manual mark analysis and report writing into a supervised,
traceable minutes-long workflow; identifies students needing support early.

**MVP Scope:**
- [ ] Auth + school tenancy + RBAC
- [ ] Academic setup + synthetic seed data
- [ ] Marks import with Data Quality validation
- [ ] Deterministic analytics + at-risk detection
- [ ] LangGraph agent run with live step timeline
- [ ] Intervention approval queue
- [ ] PDF/XLSX reports + audit log

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.12 | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite | skills/FRONTEND.md |
| Database | PostgreSQL 16 + SQLAlchemy 2 + Alembic | skills/DATABASE.md |
| Auth | JWT + bcrypt | skills/BACKEND.md |
| UI | Tailwind + Framer Motion | skills/FRONTEND.md |
| Agents | LangGraph + OpenAI SDK | — |
| Data/Reports | pandas, openpyxl, reportlab | — |
| Testing | pytest + Vitest/RTL | skills/TESTING.md |
| Deployment | Docker Compose + GitHub Actions | skills/DEPLOYMENT.md |

---

## DATABASE MODELS

20 tables, see `INITIAL.md` for fields:

- **Tenancy:** School, User, Membership, RefreshToken
- **Academic:** AcademicYear, ClassSection, Subject, Teacher, TeachingAssignment, Student, Exam, ExamSubjectConfig
- **Marks:** Mark, ImportBatch
- **Agents:** AgentRun, AgentStep, InterventionPlan, AuditLog
- **Reports:** Report

Rules: every school-owned model inherits `TenantMixin` (`school_id` FK, indexed, non-null).
Composite indexes on `(school_id, exam_id)` for Mark and `(school_id, status)` for InterventionPlan.

---

## MODULES

| # | Module | Backend | Frontend | Pages |
|---|--------|---------|----------|-------|
| 1 | Auth & Tenancy | auth router, `get_tenant_context` dep, role guard | AuthContext, school switcher | /login, /register |
| 2 | Academic Setup | 7 CRUD routers + student CSV import + seed script | Tabbed setup page | /setup |
| 3 | Marks Import | `agents/data_quality.py` (pure checks), imports router | Upload wizard | /imports/new |
| 4 | Analytics | `analytics/*.py` pure functions, analytics router | Charts (recharts) | /dashboard, /analytics/exams/:id, /students/:id |
| 5 | Agents & Interventions | `agents/graph.py` (LangGraph), `llm/client.py` (cost cap, PII guard), runs/interventions/audit routers | Run timeline, review queue | /agents, /interventions, /audit |
| 6 | Reports | `reports/pdf.py`, `reports/xlsx.py`, reports router | Report list + download | /reports |

Endpoint count: ~45. Page count: 11.

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- DATABASE-AGENT: all 20 models, TenantMixin, database.py, Alembic initial migration
- BACKEND-AGENT: main.py (+ `/health`), config.py, exceptions, dependencies stubs, requirements.txt
- FRONTEND-AGENT: Vite + Tailwind + Router, api.ts with `X-School-Id` interceptor, base UI kit
- DEVOPS-AGENT: Dockerfiles, docker-compose (db, backend, frontend), .env.example, .gitignore, CI

**Gate 1:** `docker compose up -d db backend` → `alembic upgrade head` → `curl /health` 200; `npm install`

**Phase 2: Modules (backend+frontend pairs; 1→2→3 sequential deps, then 4/5/6 in parallel)**
- Wave A: Module 1 (auth/tenancy) — everything else depends on it
- Wave B: Module 2 (setup + seed) and Module 3 (imports) in parallel
- Wave C: Modules 4, 5, 6 in parallel (5 and 6 consume analytics function signatures agreed up front)

**Gate 2:** `ruff check`, `mypy`, `npm run lint`, `npm run type-check`

**Phase 3: Quality (parallel)**
- TEST-AGENT: tenant-isolation test per router, analytics fixtures, import validation cases, PII-leak test, approval flow
- REVIEW-AGENT: OWASP + tenancy audit

**Final:** `pytest --cov-fail-under=80`, `docker compose up`, run seeded end-to-end demo with `LLM_ENABLED=false` then `true`

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `docker compose up -d db`, `alembic upgrade head`, `npm install`, `docker compose config` |
| 2 | `ruff check backend/`, `mypy backend/app`, `npm run type-check` |
| 3 | `pytest --cov=app --cov-fail-under=80`, `npm test` |
| Final | `docker compose up -d`, `curl localhost:8000/health`, demo script `scripts/demo.py` |

---

## ENVIRONMENT VARIABLES

```env
DATABASE_URL=postgresql+psycopg://edu:edu@localhost:5432/eduguardian
SECRET_KEY=change-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
LLM_ENABLED=false
LLM_MONTHLY_BUDGET_USD=15
REPORTS_DIR=/data/reports
VITE_API_URL=http://localhost:8000
```

---

## NEXT STEP

```
/execute-prp PRPs/eduguardian-ai-prp.md
```
