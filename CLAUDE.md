# CLAUDE.md - Project Rules

> Rules Claude follows in every conversation.

---

## Tech Stack

- **Backend:** FastAPI + Python 3.11+
- **Frontend:** React + TypeScript + Vite
- **Database:** PostgreSQL + SQLAlchemy
- **Auth:** JWT + Google OAuth
- **UI:** Chakra UI or Tailwind + Framer Motion

---

## Project Structure

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, database.py
│   │   ├── models/, schemas/, routers/, services/, auth/
│   ├── alembic/
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/, pages/, hooks/, services/, context/, types/
├── skills/           # 5 skill files
├── agents/           # Agent definitions
└── .claude/commands/ # /generate-prp, /execute-prp
```

---

## Code Standards

### Python
```python
# Type hints required
def get_user(db: Session, user_id: int) -> User:
    pass

# Async endpoints
@router.get("/users/{id}")
async def get_user(id: int, db: Session = Depends(get_db)):
    pass
```

### TypeScript
```typescript
// Interfaces required - NO any types
interface User { id: number; email: string; }

const fetchUser = async (id: number): Promise<User> => { ... };
```

---

## Forbidden

- `print()` → use `logging`
- Plain passwords → use bcrypt
- Hardcoded secrets → use env vars
- `any` type in TypeScript
- `console.log` in production
- Inline styles → use UI framework

---

## Workflow

```
1. Edit INITIAL.md (define product)
2. /generate-prp INITIAL.md
3. /execute-prp PRPs/[name]-prp.md
```

---

## Skills

| Task | Skill |
|------|-------|
| API + Auth | `skills/BACKEND.md` |
| React + UI | `skills/FRONTEND.md` |
| Models | `skills/DATABASE.md` |
| Tests | `skills/TESTING.md` |
| Docker | `skills/DEPLOYMENT.md` |

---

## Agents

| Agent | Role |
|-------|------|
| DATABASE-AGENT | Models + migrations |
| BACKEND-AGENT | API + auth |
| FRONTEND-AGENT | UI + pages |
| DEVOPS-AGENT | Docker + CI/CD |

---

## Validation

```bash
ruff check backend/ && pytest
npm run lint && npm run type-check
docker-compose build
```

---

## Environment Variables

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/db
SECRET_KEY=your-secret-key
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx
VITE_API_URL=http://localhost:8000
```
