# Code audit notes

This build was reviewed from the uploaded project ZIP.

## Changes applied
- Config now loads `.env` and resolves relative `DATA_DIR` from the project root.
- Default setup uses Ollama embeddings (`nomic-embed-text:latest`) and answer generation (`qwen3:8b`).
- Updated `.env.example`, README, and `.gitignore` to match the Ollama setup.
- LLM system instructions are passed using Ollama's separate `system` field.
- If Ollama generation fails, the app returns an explicit unavailable message rather than pretending the top passage is a generated answer.
- Audit-only blocked-candidate queries request metadata/distances, not document text.
- Failed document indexing attempts also try to remove partially added vectors and the stored upload.
- Removed bundled runtime database/vector-index files and Python bytecode from this source ZIP.

## Validation performed
- All Python source files passed Python syntax compilation.
- Frontend JavaScript passed `node --check`.
- The pytest suite could not execute in the audit environment because `chromadb` is not installed there. Run `pip install -r requirements.txt` and `python -m pytest -q` on the target machine.

## Remaining limitations
- Retrieval threshold/relevance needs calibration on representative documents and questions; no universal threshold is enabled yet.
- Scanned PDFs need OCR, which is not included.
- This is a development/demo project, not a production security certification.
