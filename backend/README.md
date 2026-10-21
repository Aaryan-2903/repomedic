# Repomedic Backend

FastAPI service powering Repomedic's agent orchestration, repository inspection tools, and sandbox verification interface.

## Prerequisites
- Python 3.12+
- `pip` or `uv`

## Local Setup

```bash
# From the repository root
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

## API Documentation
Once running, access interactive OpenAPI docs at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
