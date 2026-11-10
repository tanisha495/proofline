# ProofLine

> **Proof before publish.**

ProofLine is a pre-publication brand-governance platform that checks content against a company's approved guidelines and facts, surfaces cited findings, and runs a human review and approval workflow.

## Tech Stack

| Layer      | Technology                                                    |
|------------|---------------------------------------------------------------|
| Frontend   | Next.js 15 (App Router), TypeScript, Tailwind CSS, Recharts  |
| Backend    | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x            |
| Database   | PostgreSQL 16 with pgvector                                   |
| Migrations | Alembic                                                       |
| Auth       | JWT (python-jose), passlib[bcrypt]                             |
| Document parsing | python-docx, PyMuPDF                                    |
| NLP        | spaCy                                                         |
| Diffing    | diff-match-patch                                              |
| Infra      | Docker, Docker Compose                                        |

## Prerequisites

- Docker and Docker Compose (v2)
- Node.js 20+ and npm (for local frontend development)
- Python 3.11+ (for local backend development)

## Quick Start with Docker Compose

```bash
cd proofline

# Copy environment variables
cp .env.example .env

# Start all services
docker compose up --build

# The services will be available at:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Health: http://localhost:8000/health
```

## Running Without Docker

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies (including dev extras)
pip install -e ".[dev]"

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

## Running Tests

### Backend Tests

```bash
cd backend
pytest tests/ -v
```

### Frontend Lint & Build

```bash
cd frontend
npm run lint
npm run build
```

## Project Structure

```
proofline/
├── README.md
├── DISCLOSURE.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── .github/workflows/ci.yml
├── docs/
│   ├── api-contract.md
│   └── architecture.md
├── sample-data/
│   ├── guidelines.json
│   ├── facts.json
│   ├── terminology.json
│   └── seeded-drafts/
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   │   ├── parsing/
│   │   │   ├── review/
│   │   │   └── workflow/
│   │   └── core/
│   └── tests/
└── frontend/
    ├── package.json
    ├── Dockerfile
    ├── next.config.js
    ├── tailwind.config.ts
    ├── tsconfig.json
    └── src/
        ├── app/
        ├── components/
        ├── lib/
        │   ├── api.ts
        │   └── mock/
        └── types/
```

## License

Proprietary – all rights reserved.

