# INITIAL.md - EduGuardian AI Product Definition

> Multi-tenant, multi-agent academic intelligence platform that turns school marks data into
> validated analytics, teacher-approved intervention plans, and principal-ready reports.

Source spec: `EduGuardian_AI_Project_Idea.md`

---

## PRODUCT

**Name:** EduGuardian AI

**Description:** Schools upload exam marks (CSV/Excel). A team of AI agents validates the data,
computes deterministic performance analytics, drafts targeted intervention plans for students
needing support, and produces PDF/Excel reports. Teachers approve every plan before it takes
effect. Every agent step, calculation and approval is audit-logged.

**Target users:** School admins, principals, academic coordinators, teachers (multi-school groups later).

**Type:** Multi-tenant SaaS

---

## TECH STACK

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Python 3.12 (run in Docker; local 3.12 install is broken) |
| Frontend | React + TypeScript + Vite |
| Database | PostgreSQL 16 + SQLAlchemy 2 + Alembic |
| Auth | JWT (email/password). Google OAuth: post-MVP |
| UI | Tailwind + Framer Motion |
| Agents | LangGraph state graph (Orchestrator → Data Quality → Analysis → Intervention → Reporting) |
| LLM | OpenAI API (`gpt-4o-mini`-class model), hard monthly cost cap via env var |
| Data processing | pandas + openpyxl |
| Reports | reportlab (PDF) + openpyxl (Excel) |
| Payments | None (post-MVP) |

### Non-negotiable architecture rules

1. **Deterministic code computes every number.** LLMs only interpret computed findings and draft text.
2. **Tenant isolation server-side.** Every school-owned table has `school_id`; every query filters
   by the caller's active school via a shared dependency. Cross-tenant access returns 404.
3. **No raw PII to the LLM.** Send pseudonymous student IDs (e.g. `S-0042`) + marks only; names are
   re-joined server-side after the LLM responds.
4. **Human-in-the-loop.** Intervention plans are `draft` until a teacher/admin approves.
5. **Synthetic data only** during development (`backend/app/seed/` generates it).

---

## MODULES

### Module 1: Authentication & Tenancy

**Models:**
```
School:      id, name, code (unique), created_at
User:        id, email (unique), hashed_password, full_name, is_active, is_superadmin, created_at
Membership:  id, user_id FK, school_id FK, role enum(school_admin, principal, coordinator, teacher), unique(user_id, school_id)
RefreshToken: id, user_id FK, token_hash, expires_at, revoked
```

**Endpoints:**
```
POST /api/v1/auth/register        - Create user + new school (caller becomes school_admin)
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me              - User + memberships
POST /api/v1/schools/{id}/members - Invite/add member with role (school_admin only)
```
Active school sent as `X-School-Id` header; dependency `get_tenant_context()` verifies membership + role.

**Pages:** /login, /register, school switcher in navbar

---

### Module 2: Academic Setup

**Models (all have school_id FK):**
```
AcademicYear:  id, school_id, label ("2026-27"), is_current
ClassSection:  id, school_id, academic_year_id, grade (int), section (str)
Subject:       id, school_id, name, code
Teacher:       id, school_id, user_id FK nullable, full_name
TeachingAssignment: id, school_id, teacher_id, class_section_id, subject_id, is_class_teacher
Student:       id, school_id, class_section_id, admission_no, full_name, pseudo_id (S-xxxx)
Exam:          id, school_id, academic_year_id, name, sequence (int, for ordering), held_on
ExamSubjectConfig: id, school_id, exam_id, subject_id, max_marks, pass_marks
```

**Endpoints:** CRUD under `/api/v1/{academic-years|classes|subjects|teachers|students|exams}`,
plus `POST /api/v1/exams/{id}/subjects` for configs. Bulk student import via CSV.

**Pages:** /setup (tabbed: Years, Classes, Subjects, Teachers, Students, Exams)

---

### Module 3: Marks Import & Validation (Data Quality Agent)

**Models:**
```
Mark:          id, school_id, exam_id, student_id, subject_id, marks_obtained (nullable), is_absent, unique(exam_id, student_id, subject_id)
ImportBatch:   id, school_id, exam_id, filename, status enum(uploaded, validated, committed, rejected), column_map JSON, issues JSON, uploaded_by, created_at
```

**Flow:** upload file → auto-detect column mapping (admission_no + one column per subject)
→ Data Quality checks → show issues → user confirms → commit marks.

**Deterministic checks:** unknown admission numbers, duplicate rows, marks > max, negative,
non-numeric, missing subject columns, students missing from file, `AB`/`ABS` → absent.
LLM step (optional): plain-English summary of the issue list.

**Endpoints:**
```
POST /api/v1/imports            - Upload file for an exam (multipart)
GET  /api/v1/imports/{id}       - Preview rows, mapping, issues
PUT  /api/v1/imports/{id}/mapping
POST /api/v1/imports/{id}/commit
```

**Pages:** /imports/new (upload + mapping + issue table + confirm)

---

### Module 4: Performance Analytics (Analysis Agent — deterministic)

Pure functions in `backend/app/analytics/` with unit tests against hand-computed fixtures.

- Student: total, %, pass/fail per subject, failed-subject count, rank in section, change vs previous exam
- Class/section: pass %, mean, median, distribution bands (0-35, 35-50, 50-75, 75-90, 90+)
- Subject: pass % per section, weakest sections, mean change across exams
- Teacher: aggregate of their teaching assignments (coaching view, never a ranking/score of the teacher)
- **At-risk rule:** failed ≥1 subject OR dropped ≥15 percentage points vs previous exam OR below 40% overall

**Endpoints:**
```
GET /api/v1/analytics/exams/{id}/summary
GET /api/v1/analytics/exams/{id}/classes/{class_id}
GET /api/v1/analytics/exams/{id}/subjects/{subject_id}
GET /api/v1/analytics/exams/{id}/at-risk
GET /api/v1/analytics/students/{id}/trend
GET /api/v1/analytics/teachers/{id}?exam_id=
```

**Pages:** /dashboard (school overview), /analytics/exams/:id, /students/:id

---

### Module 5: Agent Runs & Interventions (Orchestrator + Intervention Agent)

**Models:**
```
AgentRun:   id, school_id, kind enum(full_analysis, intervention_draft, report), status enum(queued, running, awaiting_approval, done, failed), requested_by, input JSON, created_at, finished_at, token_usage int, cost_usd numeric
AgentStep:  id, run_id, agent_name, status, started_at, finished_at, input_summary JSON, output_summary JSON, error text
InterventionPlan: id, school_id, run_id, student_id, subject_id nullable, status enum(draft, approved, rejected, in_progress, completed), evidence JSON, plan_text, activities JSON, reassess_on date, approved_by, approved_at
AuditLog:   id, school_id, user_id nullable, actor ("user"|agent name), action, entity_type, entity_id, detail JSON, created_at
```

**Orchestrated workflow (LangGraph):**
`DataQuality → PerformanceAnalysis → InterventionDrafting (LLM, per at-risk student, batched) → Reporting → END (status=awaiting_approval)`

Runs execute as FastAPI BackgroundTasks (no Celery in MVP). Each node writes an AgentStep row so the
UI can show live progress by polling.

**Endpoints:**
```
POST /api/v1/agent-runs                 - Start run {exam_id, class_section_ids?}
GET  /api/v1/agent-runs/{id}            - Run + steps (poll)
GET  /api/v1/interventions?status=&class_id=
PUT  /api/v1/interventions/{id}         - Edit draft
POST /api/v1/interventions/{id}/approve
POST /api/v1/interventions/{id}/reject
GET  /api/v1/audit-logs
```

**Pages:** /agents (start run, live step timeline), /interventions (review queue with evidence + approve/edit/reject), /audit

---

### Module 6: Reports (Reporting Agent)

**Models:** `Report: id, school_id, run_id nullable, kind enum(principal, class_teacher, subject_teacher), format enum(pdf, xlsx), file_path, created_by, created_at`

**Endpoints:** `POST /api/v1/reports`, `GET /api/v1/reports`, `GET /api/v1/reports/{id}/download`

**Pages:** /reports

---

## MVP SCOPE (competition demo flow)

Must Have:
- [x] Register/login, one school, role-based access
- [ ] Academic setup + seed script producing a synthetic school (2 sections × 40 students × 5 subjects × 2 exams)
- [ ] Marks CSV/XLSX upload → validation issues → commit
- [ ] Deterministic analytics + at-risk list
- [ ] Agent run with visible step timeline
- [ ] LLM-drafted intervention plans → teacher approve/edit/reject
- [ ] Principal PDF + Excel report
- [ ] Audit log of every agent step and approval

Post-MVP (later phases of the roadmap):
- Monitoring Agent (follow-up reassessment tracking), Teacher Support Agent (lesson material)
- Google OAuth, parent/student communications, RAG over curriculum (ChromaDB)
- Subscriptions/billing, backups/restore drills, VPS deployment hardening, pilot with a real school

---

## ACCEPTANCE CRITERIA

- [ ] User in School A gets 404 for every School B resource (tested per router)
- [ ] Analytics match hand-computed fixtures exactly
- [ ] Bad marks file produces the expected issue list and nothing is committed until confirmed
- [ ] Agent run with LLM disabled (`LLM_ENABLED=false`) completes using template-based plans
- [ ] No student names in any LLM request payload (tested)
- [ ] Plans stay `draft` until approved; approval writes an AuditLog row
- [ ] PDF and XLSX reports download and open
- [ ] Backend test coverage ≥ 80%
- [ ] `docker compose up` brings up db + backend + frontend; `/health` returns 200

---

## RUN

```bash
/generate-prp INITIAL.md
/execute-prp PRPs/eduguardian-ai-prp.md
```
