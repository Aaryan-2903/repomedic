# Repomedic

> **Repomedic** is an agentic software debugging, repair, and verification platform. It autonomously reproduces bugs from issues or test fixtures, localizes faults, synthesizes candidate patches, and validates solutions inside containerized sandboxes.

---

## Project Structure

Repomedic is organized as a monorepo where the frontend and backend live in one Git repository but can be developed and tested independently:

```
repomedic/
├── frontend/             # React + TypeScript developer dashboard (Vite)
├── backend/              # FastAPI API, agent orchestration, and repository tools
├── fixtures/
│   └── bugs/             # Small, controlled repositories containing reproducible bugs
├── docs/
│   ├── architecture.md   # Architectural design decisions and system flow
│   └── api-contract.md   # REST and WebSocket specifications
├── scripts/              # Development and test helper scripts
├── .github/
│   └── ISSUE_TEMPLATE/   # Issue and contribution templates
├── .gitignore
├── .env.example          # Environment variable template
├── docker-compose.yml    # Monorepo container orchestration
└── README.md
```

### Directory Roles

| Directory | Purpose |
| :--- | :--- |
| `frontend/` | React + TypeScript developer dashboard for monitoring agent reasoning, inspecting diffs, and viewing sandbox verification in real time. |
| `backend/` | FastAPI service handling session orchestration, repository analysis tools, and Docker sandbox execution. |
| `fixtures/bugs/` | Isolated benchmark repositories containing reproducible bugs for testing agent performance. |
| `docs/` | System architecture documentation and API contracts. |
| `scripts/` | Cross-platform development and test helper scripts (`dev.ps1`, `dev.sh`). |
| `.github/` | Issue templates for bug reports, feature requests, and future CI workflows. |

---

## Quickstart

### 1. Prerequisites
- **Node.js**: v20+ or v24+
- **Python**: 3.12+
- **Docker**: (Optional, required for containerized sandbox verification in Step 4)

### 2. Frontend Development Dashboard
```bash
# Navigate to frontend and install dependencies
cd frontend
npm install

# Start the Vite development server
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 3. Backend API Service
```bash
cd backend
python -m venv .venv

# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Running Bug Fixtures
```bash
# Discover and run sample bug reproduction tests
python -m unittest discover -s fixtures/bugs/sample-calculator-bug -p "test_*.py"
```

---

## Documentation
- [Architecture Overview](docs/architecture.md)
- [API Contract & Schema](docs/api-contract.md)
- [Bug Fixtures Guide](fixtures/bugs/README.md)
- [Helper Scripts](scripts/README.md)

---

## Development Roadmap
- [x] **Step 1 & 2**: Git repository & branch foundation (`feat/project-foundation`)
- [x] **Step 3**: Monorepo directory structure, developer dashboard foundation & contracts
- [ ] **Step 4**: Docker execution sandbox & test runner integration
- [ ] **Step 5**: LLM agent orchestration loop & repository fault localization tools
- [ ] **Step 6**: Live WebSocket telemetry & automated patch verification
