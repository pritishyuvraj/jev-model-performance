#!/usr/bin/env python3
"""Expose NanoJev's native decision server through the System One choice wire shape.

The bridge changes only the envelope. It forwards the original state, question,
and option descriptions, then returns the native choice and probabilities. No
BFCL labels or source answers are available to this process.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MODEL = "nanojev-unified-games-v1"
WEIGHT_REVISION = "047b927b30882a1138fc504821b82ac145a4b81a"
CODE_REVISION = "76fdfc9ecdca45a9bcef17991a07d3041a87685a"
BASE_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


def native_request(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("model") != MODEL:
        raise ValueError(f"model must be {MODEL}")
    state = payload.get("state")
    questions = payload.get("questions")
    if not isinstance(state, str) or not state.strip():
        raise ValueError("state must be a nonempty string")
    if not isinstance(questions, dict) or set(questions) != {"next"}:
        raise ValueError("expected one next question")
    q = questions["next"]
    if not isinstance(q, dict) or q.get("type") != "choice":
        raise ValueError("next must be a choice question")
    return {"states": [{"id": "case", "state": state, "questions": questions}]}


def systemone_response(native: dict[str, Any], checkpoint_dir: Path) -> dict[str, Any]:
    checkpoint = native.get("checkpoint", {})
    if checkpoint.get("base_revision") != BASE_REVISION or checkpoint.get("set_head") != "attention":
        raise ValueError("NanoJev server reported a different checkpoint")
    if Path(checkpoint.get("directory", "")).resolve() != checkpoint_dir.resolve():
        raise ValueError("NanoJev server loaded a different checkpoint directory")
    states = native.get("states")
    if not isinstance(states, list) or len(states) != 1 or states[0].get("id") != "case":
        raise ValueError("NanoJev server returned an unexpected state")
    answer = states[0].get("answers", {}).get("next", {})
    if answer.get("type") != "choice" or not isinstance(answer.get("probabilities"), dict):
        raise ValueError("NanoJev server returned no choice distribution")
    return {"model": MODEL, "answers": {"next": answer},
            "latency_ms": round(native.get("execution", {}).get("server_evaluation_seconds", 0) * 1000, 2)}


def handler_for(upstream: str, checkpoint_dir: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, body: dict[str, Any]) -> None:
            encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            if self.path == "/v1/models":
                self.send_json(200, {"models": [{"name": MODEL,
                    "run": f"C-Tianyu/NanoJev@{WEIGHT_REVISION}",
                    "base": f"Qwen/Qwen3-0.6B@{BASE_REVISION}",
                    "code_revision": CODE_REVISION, "backend": "torch", "dtype": "bfloat16"}]})
                return
            if self.path == "/health":
                try:
                    with urllib.request.urlopen(upstream + "/api/health", timeout=5) as response:
                        health = json.load(response)
                    self.send_json(200, {**health, "model": MODEL, "revision": WEIGHT_REVISION})
                except (OSError, ValueError) as error:
                    self.send_json(502, {"error": str(error)})
                return
            self.send_json(404, {"error": "Unknown route"})

        def do_POST(self) -> None:
            if self.path != "/v1/systemone":
                self.send_json(404, {"error": "Unknown route"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2_000_000:
                    raise ValueError("request size outside 1..2000000 bytes")
                payload = json.loads(self.rfile.read(size))
                body = json.dumps(native_request(payload), ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(upstream + "/api/evaluate", data=body,
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as response:
                    native = json.load(response)
                self.send_json(200, systemone_response(native, checkpoint_dir))
            except (OSError, ValueError, KeyError, TypeError, urllib.error.HTTPError) as error:
                self.send_json(502, {"error": f"{type(error).__name__}: {error}"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default="http://127.0.0.1:8765")
    parser.add_argument("--port", type=int, default=8015)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port),
                        handler_for(args.upstream.rstrip("/"), args.checkpoint_dir)).serve_forever()


if __name__ == "__main__":
    main()
