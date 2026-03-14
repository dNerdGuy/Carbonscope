# Contributing to CarbonScope

Thank you for your interest in contributing to CarbonScope! This document covers the development workflow, code style, testing practices, and pull request process.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Style](#code-style)
- [Git Workflow](#git-workflow)
- [Testing](#testing)
- [Database Migrations](#database-migrations)
- [Adding API Endpoints](#adding-api-endpoints)
- [Adding Frontend Pages](#adding-frontend-pages)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

---

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone <your-fork-url> && cd carbonscope`
3. Set up the development environment (see below)
4. Create a feature branch: `git checkout -b feature/your-feature`
5. Make your changes, add tests, and push
6. Open a pull request

---

## Development Setup

### Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Or use pinned deps
pip install -r requirements.txt

# Start the backend (SQLite — auto-creates on startup)
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # → http://localhost:3000
```

### Environment

Copy the example `.env` or use defaults. No configuration is required for development — SQLite and local estimation mode are used by default.

---

## Project Structure

```
carbonscope/
├── api/                     # FastAPI backend
│   ├── main.py              #   App entry point
│   ├── config.py            #   Environment configuration
│   ├── models.py            #   SQLAlchemy models (19 models)
│   ├── schemas.py           #   Pydantic request/response schemas
│   ├── auth.py              #   JWT + bcrypt authentication
│   ├── deps.py              #   Dependency injection (auth, plan gates, credits)
│   ├── middleware.py         #   Request ID, logging, security headers
│   ├── routes/              #   18 route modules
│   └── services/            #   19 service modules
├── carbonscope/             # Bittensor subnet core
│   ├── protocol.py          #   CarbonSynapse definition
│   ├── scoring.py           #   5-axis composite scorer
│   └── emission_factors/    #   Scope 1/2/3 calculation engines
├── neurons/                 # Bittensor miner & validator
├── frontend/                # Next.js 15 dashboard
│   └── src/
│       ├── app/             #   App Router pages (22 routes)
│       ├── components/      #   Reusable UI components
│       └── lib/             #   API client, auth context
├── alembic/                 # Database migrations
├── tests/                   # Backend tests (647+)
└── data/                    # Emission factor JSON datasets
```

---

## Code Style

### Python (Backend)

- **Formatter:** Ruff (`ruff format`)
- **Linter:** Ruff with rules `E`, `F`, `W` (ignoring `E501`)
- **Line length:** 120 characters
- **Type hints:** Use type annotations for function signatures
- **Python version:** 3.10+ features allowed
- **Async:** All database operations use `async`/`await`

```bash
# Format
ruff format api/ tests/

# Lint
ruff check api/ tests/

# Lint (matching CI config)
ruff check . --select E,F,W --ignore E501

# Fix auto-fixable issues
ruff check --fix api/ tests/
```

### TypeScript (Frontend)

- **Strict mode:** Enabled in `tsconfig.json`
- **Linter:** ESLint with Next.js config
- **Framework:** React 19 with Next.js 15 App Router

```bash
cd frontend
npm run lint
```

### General Conventions

- Use meaningful variable and function names
- Keep functions focused — one function, one responsibility
- Prefer composition over inheritance
- Write tests for new code
- Don't add comments explaining what code does — write self-documenting code instead. Add comments for **why** when the logic isn't obvious

---

## Git Workflow

### Branch Naming

- `feature/short-description` — New features
- `fix/short-description` — Bug fixes
- `refactor/short-description` — Code restructuring
- `docs/short-description` — Documentation changes

### Commit Messages

Use clear, imperative-mood messages:

```
Add supply chain Scope 3 aggregation endpoint
Fix JWT refresh token rotation race condition
Update emission factor datasets for 2024
```

### Keeping Your Fork Updated

```bash
git remote add upstream <original-repo-url>
git fetch upstream
git rebase upstream/main
```

---

## Testing

### Backend Tests (pytest)

```bash
# Run full suite (729 tests)
pytest tests/ -v

# Specific file
pytest tests/test_carbon_api.py -v

# Pattern matching
pytest tests/ -k "test_auth" -v

# With coverage
pytest tests/ --cov=api --cov-report=term-missing

# Parallel execution
pytest tests/ -n auto
```

**Test configuration:**

- Tests use in-memory SQLite (`sqlite+aiosqlite:///:memory:`)
- Rate limiting is disabled during tests
- Each test gets a fresh database (tables created/dropped per test)
- An `auth_client` fixture provides a pre-authenticated HTTP client

### Frontend Tests (Vitest)

```bash
cd frontend

# Run full suite (142 tests)
npm test

# Watch mode
npm run test:watch
```

**Test configuration:**

- Environment: jsdom
- Setup file: `src/__tests__/setup.ts`
- Includes: `src/**/*.test.{ts,tsx}`
- Libraries: Testing Library (React + user-event)

### Writing Tests

**Backend test example:**

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_company(auth_client: AsyncClient):
    """Test company creation via authenticated request."""
    response = await auth_client.get("/api/v1/company")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
```

**Frontend test example:**

```typescript
import { render, screen } from "@testing-library/react";
import { Skeleton } from "@/components/Skeleton";

test("renders skeleton with correct class", () => {
  render(<Skeleton className="h-10 w-full" />);
  const el = screen.getByRole("status");
  expect(el).toHaveClass("animate-pulse");
});
```

---

## Database Migrations

When modifying SQLAlchemy models in `api/models.py`:

1. Make your model changes
2. Generate a migration:
   ```bash
   alembic revision --autogenerate -m "Add field_name to model_name"
   ```
3. Review the generated migration in `alembic/versions/`
4. Apply:
   ```bash
   alembic upgrade head
   ```
5. Test the migration (both upgrade and downgrade):
   ```bash
   alembic downgrade -1
   alembic upgrade head
   ```

**Guidelines:**

- Always review auto-generated migrations — they may miss some operations
- Add `CHECK` constraints and indexes explicitly if needed
- Include both `upgrade()` and `downgrade()` functions
- Test migrations against a clean database

---

## Adding API Endpoints

### 1. Define Schema (`api/schemas.py`)

```python
class MyFeatureCreate(BaseModel):
    name: str
    description: str | None = None

class MyFeatureOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True
```

### 2. Create Route Module (`api/routes/my_feature_routes.py`)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.deps import get_current_user
from api.models import User

router = APIRouter(prefix="/my-feature", tags=["My Feature"])

@router.post("/", status_code=201)
async def create_feature(
    data: MyFeatureCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ...
```

### 3. Register Router (`api/main.py`)

```python
from api.routes.my_feature_routes import router as my_feature_router
app.include_router(my_feature_router, prefix="/api/v1")
```

### 4. Add Tests (`tests/test_my_feature.py`)

### 5. Update API.md

---

## Adding Frontend Pages

### 1. Create Page (`frontend/src/app/my-feature/page.tsx`)

```tsx
"use client";
import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";

export default function MyFeaturePage() {
  return (
    <>
      <Navbar />
      <main className="container mx-auto p-6">
        <h1 className="text-2xl font-bold">My Feature</h1>
      </main>
    </>
  );
}
```

### 2. Add API Functions (`frontend/src/lib/api.ts`)

### 3. Add Navigation Link (`frontend/src/components/Navbar.tsx`)

### 4. Add Tests (`frontend/src/__tests__/`)

---

## Pull Request Process

1. **Branch from `main`** — Create a feature branch
2. **Write code + tests** — All new features need tests
3. **Run tests locally** — `pytest tests/ -v` and `cd frontend && npm test`
4. **Lint and format** — `ruff check --fix api/` and `npm run lint`
5. **Update documentation** — Update API.md, README, etc. if applicable
6. **Open PR** with a clear description:
   - What changes were made
   - Why (link to issue if applicable)
   - How to test
7. **Address review feedback** — Push additional commits to the PR branch
8. **Merge** — Squash-merge after approval

### PR Checklist

- [ ] Tests pass locally (`pytest` + `npm test`)
- [ ] Linting passes (`ruff check` + `npm run lint`)
- [ ] New endpoints are documented in API.md
- [ ] Database migrations are included (if models changed)
- [ ] No secrets or credentials are committed
- [ ] CHANGELOG.md is updated (for user-facing changes)

### CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci.yml`) runs automatically on pushes to `main` and all PRs:

| Job          | What it checks                                             |
| :----------- | :--------------------------------------------------------- |
| **test**     | Backend tests on Python 3.11 + 3.12 (`pytest`)             |
| **lint**     | Ruff linting (`ruff check . --select E,F,W --ignore E501`) |
| **frontend** | Frontend test suite (`vitest`)                             |
| **security** | `pip-audit` + `bandit` security scans                      |
| **docker**   | Docker image build verification                            |

---

## Issue Reporting

### Bug Reports

Include:

- Steps to reproduce
- Expected vs. actual behavior
- Environment details (Python version, OS, browser)
- Relevant log output (include `X-Request-ID` if available)

### Feature Requests

Include:

- Use case description
- Proposed behavior
- Any alternative approaches considered

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
