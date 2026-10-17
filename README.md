# EduGuardian AI

Multi-tenant, multi-agent academic intelligence platform: upload marks → Data Quality Agent validates →
deterministic analytics finds students needing support → Intervention Agent drafts plans → teachers
approve → Reporting Agent produces PDF/Excel reports. Every step is audit-logged.

Spec: `EduGuardian_AI_Project_Idea.md` · Product definition: `INITIAL.md` · Blueprint: `PRPs/eduguardian-ai-prp.md`

## Run (Docker)

```bash
cp .env.example .env            # then set SECRET_KEY (32+ chars); optional OPENAI_API_KEY + LLM_ENABLED=true
docker compose up -d --build
docker compose exec backend python -m app.seed            # demo school (add --reset to start fresh)
```

- App: http://localhost:3000 — login `demo@eduguardian.test` / `Demo@12345` (teacher: `teacher@eduguardian.test`)
- API docs: http://localhost:8000/docs

Dev mode with hot reload: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` (Vite on :5173, Postgres on :5433).

## Demo script

1. **Import Marks** → upload `backend/app/seed/sample_marks_with_errors.csv` to see the Data Quality Agent block it;
   then `sample_marks_quarterly_10A.csv` → commit.
2. **Dashboard / Analytics** → Quarterly Exam: pass rates, weak subjects, at-risk students with evidence.
3. **AI Agents** → run on Quarterly Exam and watch the 5 agents complete.
4. **Interventions** → review, edit, approve or reject the drafted plans.
5. **Reports** → download the principal PDF/Excel; **Audit Log** shows every agent and human action.

With `LLM_ENABLED=false` (default) plans are drafted from deterministic templates at zero cost. With an OpenAI
key, plans are LLM-drafted from pseudonymous data only (no names/admission numbers — enforced and tested) under a
monthly budget cap (`LLM_MONTHLY_BUDGET_USD`).

## Tests

```bash
cd backend && pytest --cov=app        # needs Postgres; see tests/conftest.py (TEST_DATABASE_URL)
cd frontend && npm test && npm run type-check && npm run lint
```

## Known follow-ups (from the security review)

Upload row caps · per-account login rate limit with a shared store · global LLM spend cap · CSV-safe template
output · SQL-side report filtering · audit-log composite index (migration) · teacher read scope for analytics ·
httpOnly refresh cookie. Verify `LLM_INPUT/OUTPUT_PRICE_PER_MTOK` against current OpenAI pricing.
