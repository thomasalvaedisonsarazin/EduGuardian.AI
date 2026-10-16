# EduGuardian AI

## Autonomous Multi-Agent Student Success and School Improvement Platform

**Proposed competition:** Dubai Create AI Agents Championship 2026  
**Proposed category:** Best Societal AI Agent  
**Product goal:** Production-ready, multi-school SaaS  
**Initial development budget:** ₹5,000  
**Developer availability:** 5 hours per day, 6 days per week  
**Estimated development duration:** 14–20 weeks (420–600 hours), subject to testing and readiness

> This document describes a proposed product, not a completed or validated system. Competition eligibility, licensing requirements, deadlines and judging rules must be verified with the organizers.

## 1. Executive Summary

EduGuardian AI is a multi-tenant, AI-powered academic intelligence platform designed to help schools identify students needing support, understand performance trends, create targeted interventions, and monitor progress. Instead of producing only marks tables and static dashboards, the platform coordinates specialized agents to validate data, analyze outcomes, draft recommendations, prepare reports, and request human approval before consequential actions.

## 2. Problem Statement

Schools routinely collect marks, examination results, attendance records, and teacher observations, but translating these into timely, personalized action is difficult. Students may struggle repeatedly in particular subjects without early intervention. Teachers and principals spend significant time preparing reports, comparing examinations, and deciding what support to provide.

## 3. Target Users

- School administrators and principals
- Class teachers and subject teachers
- Academic coordinators
- Students and parents, through carefully controlled, approved communications
- School groups operating multiple institutions

## 4. Key Product Capabilities

1. **Multi-school onboarding:** Each institution manages its own users, academic years, classes, sections, subjects, examinations and data.
2. **Marks import and validation:** Upload Excel/CSV files, map columns, detect missing or invalid values, and confirm before saving.
3. **Student performance analysis:** Track pass/fail status, subject weaknesses, exam-to-exam changes, and students needing support.
4. **Class and subject analysis:** Compare sections, subjects, and performance across assessment periods.
5. **Teacher-facing insights:** Generate class-teacher and subject-teacher reports, including separate and combined views for teachers handling multiple classes. Reports should support coaching rather than automatic punitive evaluation.
6. **Intervention planning:** Draft targeted remedial plans, practice activities, and reassessment schedules for teacher approval.
7. **Progress monitoring:** Track approved interventions and changes in subsequent assessments.
8. **Report generation:** Export PDF and Excel reports for teachers and principals.
9. **Auditability:** Show evidence, calculations, agent actions, approvals, and corrections.
10. **Role-based access:** Super Admin, School Admin, Principal, Academic Coordinator, Teacher, and other roles as needed.

## 5. Proposed AI Agent Team

| Agent | Responsibility |
|---|---|
| Orchestrator Agent | Break down tasks, coordinate agents, manage state and approvals |
| Data Quality Agent | Validate uploaded data, detect duplicates, missing marks and inconsistent configurations |
| Performance Analysis Agent | Compute academic trends using deterministic calculations and identify areas for review |
| Intervention Agent | Draft individualized learning support plans grounded in performance evidence |
| Teacher Support Agent | Prepare lesson suggestions and classroom support materials |
| Reporting Agent | Generate structured dashboards, PDF and Excel reports |
| Monitoring Agent | Track follow-up actions, reassessments and outcome changes |

**Human-in-the-loop:** Teachers or authorized administrators approve intervention plans and student/parent communications. AI must not autonomously make high-stakes judgments about students or staff.

## 6. Example End-to-End Workflow

**Principal request:** “Analyze Class 10 quarterly examination results, identify students requiring academic support, prepare remedial plans, and generate a report for class teachers.”

1. An authorized user uploads the marks file.
2. The Data Quality Agent validates the file and flags issues.
3. Verified records are stored under the correct school and academic year.
4. The Performance Analysis Agent calculates pass/fail patterns, subject-level results, and changes across exams.
5. The Intervention Agent drafts support plans for relevant students.
6. The Reporting Agent generates class, subject, and teacher reports.
7. Teachers review, modify, and approve proposed actions.
8. The Monitoring Agent tracks follow-up assessments and progress.

## 7. Architecture and Technology Stack

| Layer | Proposed technology |
|---|---|
| Production frontend | React + TypeScript |
| Rapid internal prototyping | Streamlit (optional) |
| Backend API | FastAPI (Python 3.12 recommended) |
| Agent orchestration | LangGraph |
| LLM services | OpenAI API, with cost controls |
| Primary database | PostgreSQL |
| Document retrieval | ChromaDB / RAG if curriculum retrieval is required |
| Data processing | pandas, openpyxl |
| Reports | PDF and Excel generation libraries |
| Deployment | Docker, existing Hostinger VPS where capacity permits |
| Security | Tenant isolation, RBAC, audit logs, encryption, backups and secure secrets management |

**Architecture principle:** Deterministic code performs calculations; LLMs interpret findings and draft recommendations. Every query and data operation must enforce tenant isolation server-side.

## 8. Proposed Data Model

Core entities: `schools`, `users`, `memberships`, `roles`, `academic_years`, `classes`, `sections`, `subjects`, `teachers`, `students`, `exams`, `exam_subject_config`, `marks`, `agent_tasks`, `agent_runs`, `intervention_plans`, `approvals`, `reports`, and `audit_logs`.

All school-owned records should be linked to a school/tenant ID and protected by access-control checks. Sensitive student data should be minimized, retained only as needed, and never sent to an LLM without an approved data-handling policy.

## 9. Phased Development Plan

| Phase | Weeks | Deliverables |
|---|---|---|
| 1. Foundation | 1–2 | Repository, Python environment, FastAPI, frontend skeleton, PostgreSQL, tenant architecture |
| 2. Academic management | 3–5 | School setup, students, teachers, classes, exams, marks upload and validation |
| 3. Analytics | 6–8 | Student, class, subject, teacher and exam-comparison reports; PDF/Excel exports |
| 4. AI agents | 9–11 | Orchestrator, data-quality, analysis, intervention and reporting workflows |
| 5. Production controls | 12–14 | RBAC, approval workflow, audit logs, backups, tests and monitoring |
| 6. Pilot | 15–17 | VPS deployment, supervised school pilot, usability and reliability testing |
| 7. Commercial readiness | 18–20 | Multi-school onboarding tests, subscription foundations, documentation and championship demo |

**Estimated effort:** 420–600 hours at 5 hours/day and 6 days/week. A production release is contingent on passing privacy, security, performance, and recovery checks; 20 weeks is a target, not a guarantee.

## 10. Initial ₹5,000 Budget

| Item | Allocation |
|---|---:|
| OpenAI API testing | ₹1,500 |
| Hosting reserve | ₹1,000 |
| Backup and storage | ₹500 |
| Domain/deployment expenses | ₹500 |
| Testing and contingency | ₹1,500 |
| **Total** | **₹5,000** |

The budget assumes self-development, open-source tools, and possible reuse of an existing VPS. It excludes developer labor, larger-scale hosting, formal compliance expenses, commercial support, Dubai licensing and travel. Production operations will require an ongoing budget.

## 11. Validation and Success Metrics

- **Calculation accuracy:** Match independent reference calculations on validated datasets.
- **Time saved:** Measure manual versus agent-assisted report preparation.
- **Reliability:** Track successful tasks, retries, failures, and corrections.
- **Intervention quality:** Obtain structured teacher review of recommendations.
- **Student outcomes:** Monitor changes across assessments without automatically attributing improvement to the AI.
- **Security:** Test cross-tenant access denial, permissions, backups, and restoration.
- **Commercial potential:** Measure school onboarding effort, usage, retention, and willingness to pay.

Use synthetic or properly anonymized data during development. Obtain school authorization and appropriate privacy safeguards before processing real student records.

## 12. Competition Demonstration

Show a complete task: upload marks → validate data → analyze results → draft support plans → obtain teacher approval → generate principal-ready PDF/Excel reports → track follow-up. Demonstrate visible agent activity, error handling, and traceable calculations.

The presentation should explain the problem, measurable benefit, differentiation from a chatbot, technical feasibility, privacy controls, multi-school scalability, and potential business model.

## 13. Day 1 / Step 1 — Local Setup

**Local project path:** `F:\EDUGUARDIAN-AI`

### Progress so far

- Project folder created successfully.
- A virtual environment was created and activated using Python 3.14.7.
- The registered Python 3.12 executable path was broken, so `py -3.12 -m venv venv` failed.

### Next action

Install or repair Python 3.12 from the official Python Windows downloads page, then verify:

```bat
py -0p
py -3.12 --version
```

After confirming 3.12 is available, recreate the virtual environment **from the project directory**:

```bat
F:
cd \EDUGUARDIAN-AI
rmdir /s /q venv
py -3.12 -m venv venv
venv\Scripts\activate
python --version
```

Then proceed to the backend folder structure, FastAPI installation, `/health` endpoint, Git initialization, and repository setup. Do not commit `.env` files, secrets, student records, or private school datasets.

## 14. Future Commercial Model

Potential subscription tiers for individual schools and school groups, based on number of students, enabled modules, and report volume. Pricing should be validated through pilot interviews and measured operating costs before launch.

## 15. Immediate Priorities

1. Repair the Python 3.12 environment.
2. Establish the project repository and FastAPI health endpoint.
3. Design school/tenant boundaries and authorization before adding student data.
4. Build a deterministic academic analytics engine.
5. Add supervised AI agents after the core calculations are tested.

---

*Prepared as an initial project specification and development roadmap for EduGuardian AI, 16 October 2026.*
