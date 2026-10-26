# Enterprise RAG System with Role-Based Access Control

A local FastAPI demo that indexes PDF, DOCX, TXT, and Markdown documents, retrieves only chunks permitted by the signed-in user's role/department/clearance, and uses a local Ollama model to generate grounded answers.

## Important data safety note

This repository should contain source code and sample documents, not runtime databases or vector indexes. The project defaults to `DATA_DIR=./data_nomic`, which creates a fresh SQLite database and ChromaDB index. Do not point it at a Chroma index created using a different embedding model. If you change embedding models, use a fresh data directory and re-index the documents.

## Prerequisites

- Python 3.10+
- Ollama installed and running
- The following models already pulled, or pull them with Ollama:
  - `nomic-embed-text:latest` (document/query embeddings)
  - `qwen2.5:7b` (answer generation)

## Windows PowerShell setup

Run these commands from the folder containing `seed.py`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

In `.env`, replace `JWT_SECRET` with a long random secret. Keep these settings for the local model setup:

```env
EMBEDDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text:latest
OLLAMA_MODEL=qwen2.5:7b
DATA_DIR=./data_nomic
```

Check Ollama models:

```powershell
ollama list
ollama run nomic-embed-text "Enterprise document security"
ollama run qwen2.5:7b "Explain role-based access control in three sentences."
```

Initialize the clean demo database and index:

```powershell
python seed.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`; API docs are at `http://127.0.0.1:8000/docs`.

If PowerShell blocks virtual-environment activation, open Command Prompt and use `.venv\Scripts\activate.bat`. Do not disable Windows application-control policies.

## Demo accounts

| Username | Password | Role | Department |
|---|---|---|---|
| admin | Admin@12345 | admin | it |
| eng_mgr | Manager@12345 | manager | engineering |
| eng_emp | Employee@12345 | employee | engineering |
| hr_mgr | Manager@12345 | manager | hr |
| hr_emp | Employee@12345 | employee | hr |

These are demo credentials only. Do not use them for real data or deployment.

## Access rule

A chunk is readable only if all are true:
1. The user's role is in the document's `allowed_roles`.
2. The document's sensitivity is within that role's clearance.
3. The document belongs to the user's department or is company-wide (`all`), except admins can access across departments.

The RBAC filter is applied in the Chroma query. The LLM receives only the authorized hits returned by that query.

## Tests

```powershell
python -m pytest -q
```

The test suite uses the lightweight `hash` embedder and a deliberately unreachable Ollama endpoint, so tests do not require a local LLM. Automated tests must still be run on the target machine after installing dependencies.

## Known limitations

- Scanned PDFs may not yield text; OCR is not implemented.
- Retrieval relevance thresholds need evaluation against representative documents/questions before production use.
- The login throttle is in-memory and is intended only for a single-process demo.
- SQLite is used for local development; production deployment requires stronger operational controls, secret management, HTTPS, monitoring, and a reviewed authorization design.
- Prompt-injection resistance is defense-in-depth, not a guarantee. Do not treat model-generated answers as a substitute for security review.
