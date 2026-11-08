"""Checks the real OpenAI SDK plumbing against a local mock server (no API key needed)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from datatidy.llm import FakeBackend, OpenAICompatibleBackend, get_backend, load_env


class Handler(BaseHTTPRequestHandler):
    seen: list = []
    reject_json_mode = False

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Handler.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        if Handler.reject_json_mode and "response_format" in body:
            self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "json mode unsupported"}}).encode()); return
        out = {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
               "choices": [{"index": 0, "finish_reason": "stop",
                            "message": {"role": "assistant", "content": '{"plan": []}'}}],
               "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode())

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    Handler.seen = []; Handler.reject_json_mode = False
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


def test_backend_sends_expected_request_and_parses_usage(server):
    b = OpenAICompatibleBackend("groq", api_key="test-key", base_url=server, model="my-model")
    r = b.complete("SYS", "USER")
    assert r.text == '{"plan": []}' and (r.prompt_tokens, r.completion_tokens) == (7, 3)
    seen = Handler.seen[0]
    assert seen["path"].endswith("/chat/completions") and seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "my-model" and seen["body"]["temperature"] == 0.0
    assert seen["body"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_backend_retries_without_json_mode_if_rejected(server):
    Handler.reject_json_mode = True
    b = OpenAICompatibleBackend("ollama", base_url=server)
    assert b.complete("s", "u").text == '{"plan": []}'
    assert "response_format" in Handler.seen[0]["body"] and "response_format" not in Handler.seen[-1]["body"]


def test_missing_key_gives_helpful_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        OpenAICompatibleBackend("groq")


def test_unknown_provider_and_ollama_needs_no_key():
    with pytest.raises(ValueError):
        OpenAICompatibleBackend("skynet")
    assert OpenAICompatibleBackend("ollama").name.startswith("ollama:")


def test_env_file_loader_does_not_override(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# comment\nDT_A=from_file\nDT_B="quoted"\n')
    monkeypatch.setenv("DT_A", "real_env")
    monkeypatch.delenv("DT_B", raising=False)
    load_env(f)
    import os
    assert os.environ["DT_A"] == "real_env" and os.environ["DT_B"] == "quoted"
    monkeypatch.delenv("DT_B", raising=False)


def test_get_backend_reads_provider_from_env(monkeypatch):
    monkeypatch.setenv("DATATIDY_PROVIDER", "ollama")
    monkeypatch.delenv("DATATIDY_MODEL", raising=False)
    assert get_backend().name == "ollama:llama3.2"


def test_fake_backend_runs_out():
    with pytest.raises(RuntimeError):
        FakeBackend([]).complete("a", "b")
