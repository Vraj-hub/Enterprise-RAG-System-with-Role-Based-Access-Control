import httpx
import pytest

from app.embeddings import OllamaEmbedder


def test_ollama_http_error_includes_server_response(monkeypatch):
    body = '{"error":"llama-server process has terminated: exit status 0xc0000005"}'
    request = httpx.Request("POST", "http://localhost:11434/api/embed")
    response = httpx.Response(500, text=body, request=request)
    monkeypatch.setattr("app.embeddings.httpx.post", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="Ollama embeddings failed") as exc_info:
        OllamaEmbedder().embed(["sample"])

    assert "llama-server process has terminated" in str(exc_info.value)
    assert "0xc0000005" in str(exc_info.value)
