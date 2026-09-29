#!/usr/bin/env python3
"""Score BFCL V1 Jev tool choices against a local System One HTTP server.

Only ``jev.laya.state`` and ``jev.laya.questions`` are sent to the server.
BFCL source records and gold labels stay in this evaluator. Both models see the
same payload, so this measures first-step tool selection, not arguments or task
completion. A response error counts against the full-set accuracy and is also
reported separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "data" / "bfcl_v1" / "cases.jsonl"
DEFAULTS = {
    "laya": {
        "endpoint": "http://127.0.0.1:8007",
        "model": "convaiinnovations/laya-typed-decisions",
        "revision": "1a793eb568e6718f15941d08f85432581df534e3",
    },
    "kev": {
        "endpoint": "http://127.0.0.1:8008",
        "model": "kev-latest",
        "revision": "9a45d25eb2ab761841196625383fa1dff0e56c1e",
    },
}
STRATA = ("multi_tool_call", "one_tool_call", "one_tool_no_call")
NO_FUNCTION_ACTIONS = frozenset(("no_tool", "clarify", "cannot_answer"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def stratum(case: dict[str, Any]) -> str:
    tools = [option["id"] for option in case["jev"]["options"] if option["kind"] == "tool"]
    if case["kind"] == "no_call" and len(tools) == 1 and case["gold_next_action_ids"] == ["no_tool"]:
        return "one_tool_no_call"
    if case["kind"] == "single_call" and len(tools) == 1:
        return "one_tool_call"
    if case["kind"] == "single_call" and len(tools) > 1:
        return "multi_tool_call"
    raise ValueError(f"{case['id']}: not in a defined first-step routing stratum")


def load_cases(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            case = json.loads(line)
            case_id = case["id"]
            if case_id in seen:
                raise ValueError(f"{path}:{line_no}: duplicate case ID {case_id}")
            seen.add(case_id)
            if case.get("score_eligible") is not True:
                raise ValueError(f"{case_id}: not score eligible")
            gold = case.get("gold_next_action_ids")
            option_ids = case["jev"]["option_ids"]
            payload = case["jev"]["laya"]
            question = payload["questions"]["next"]
            if not isinstance(gold, list) or len(gold) != 1 or gold[0] not in option_ids:
                raise ValueError(f"{case_id}: expected one offered gold action")
            if not isinstance(payload["state"], str) or question.get("type") != "choice":
                raise ValueError(f"{case_id}: malformed Laya/TypeSafe choice payload")
            if list(question["criteria"]) != option_ids or len(set(option_ids)) != len(option_ids):
                raise ValueError(f"{case_id}: criteria must match offered option IDs in order")
            stratum(case)
            cases.append(case)
    if not cases:
        raise ValueError(f"{path}: no cases")
    manifest_path = path.with_name("manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if manifest and manifest.get("cases_sha256") != sha256(path):
        raise ValueError(f"{path}: SHA-256 does not match sibling manifest.json")
    if manifest and manifest.get("selected_count") != len(cases):
        raise ValueError(f"{path}: count does not match sibling manifest.json")
    return cases, manifest


def http_json(url: str, *, payload: dict[str, Any] | None, api_key: str | None, timeout: float) -> dict[str, Any]:
    headers = {"accept": "application/json"}
    body = None
    if payload is not None:
        headers["content-type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read(1000).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    if not isinstance(result, dict):
        raise ValueError("server returned a non-object JSON value")
    return result


def server_probe(endpoint: str, api_key: str | None, timeout: float) -> dict[str, Any]:
    """Record advertised identity where provided; endpoints are not all identical."""
    result: dict[str, Any] = {}
    for route in ("/v1/models", "/health"):
        try:
            result[route] = http_json(endpoint + route, payload=None, api_key=api_key, timeout=timeout)
        except (OSError, ValueError, RuntimeError) as error:
            result[route] = {"unavailable": f"{type(error).__name__}: {error}"}
    return result


def stable_server_identity(probe: dict[str, Any], requested_model: str) -> dict[str, Any]:
    """Extract stable identity fields; omit runtime counters from /v1/models."""
    identity: dict[str, Any] = {}
    models = probe.get("/v1/models", {}).get("models")
    if isinstance(models, list):
        card = next((item for item in models if isinstance(item, dict) and item.get("name") == requested_model), None)
        if isinstance(card, dict):
            for key in ("name", "run", "base", "device", "backend", "dtype", "temperature", "revision", "model_id"):
                if key in card:
                    identity[key] = card[key]
    health = probe.get("/health", {})
    if isinstance(health, dict):
        for key in ("device", "revisions", "loaded", "model", "model_id", "revision"):
            if key in health:
                identity[f"health_{key}"] = health[key]
    return identity


def read_predictions(path: Path, run_id: str, case_ids: set[str]) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    latest: dict[str, dict[str, Any]] = {}
    attempts: Counter[str] = Counter()
    if not path.exists():
        return latest, attempts
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_no}: incomplete or invalid JSONL; preserve the file and repair it before resuming") from error
            case_id = item.get("case_id")
            if item.get("run_id") != run_id or case_id not in case_ids:
                raise ValueError(f"{path}:{line_no}: row belongs to another run or case set")
            latest[case_id] = item
            attempts[case_id] += 1
    return latest, attempts


def validate_answer(body: dict[str, Any], option_ids: list[str]) -> tuple[str, dict[str, float]]:
    answers = body.get("answers")
    answer = answers.get("next") if isinstance(answers, dict) else None
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ValueError("response has no answers.next choice")
    choice = answer.get("choice")
    if choice not in option_ids:
        raise ValueError(f"response chose an unoffered action: {choice!r}")
    raw = answer.get("probabilities")
    if not isinstance(raw, dict) or set(raw) != set(option_ids):
        raise ValueError("response probabilities do not cover exactly the offered actions")
    probabilities: dict[str, float] = {}
    for option_id in option_ids:
        value = raw[option_id]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"invalid probability for {option_id!r}")
        probabilities[option_id] = float(value)
    if abs(sum(probabilities.values()) - 1.0) > 0.02:
        raise ValueError("response probabilities do not sum to 1")
    return choice, probabilities


def predict_case(case: dict[str, Any], *, endpoint: str, model: str, api_key: str | None,
                 timeout: float, retries: int, run_id: str, attempt: int) -> dict[str, Any]:
    case_id = case["id"]
    gold = case["gold_next_action_ids"][0]
    prompt = case["jev"]["laya"]
    # Construct a fresh dict to make it impossible to include source/gold by accident.
    payload = {"model": model, "state": prompt["state"], "questions": prompt["questions"]}
    common: dict[str, Any] = {
        "run_id": run_id,
        "case_id": case_id,
        "category": case["category"],
        "stratum": stratum(case),
        "gold_action": gold,
        "attempt": attempt,
        "completed_at_utc": utc_now(),
    }
    started = time.perf_counter()
    last_error: Exception | None = None
    for retry in range(retries + 1):
        try:
            body = http_json(endpoint + "/v1/systemone", payload=payload, api_key=api_key, timeout=timeout)
            choice, probabilities = validate_answer(body, case["jev"]["option_ids"])
            usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
            return {
                **common,
                "status": "ok",
                "predicted_action": choice,
                "correct": choice == gold,
                "probabilities": probabilities,
                "response_model": body.get("model"),
                "input_tokens": usage.get("input_tokens"),
                "server_latency_ms": body.get("latency_ms"),
                "wall_latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "http_retries": retry,
            }
        except (OSError, ValueError, RuntimeError) as error:
            last_error = error
            if retry < retries:
                time.sleep(min(2 ** retry, 4))
    return {
        **common,
        "status": "error",
        "predicted_action": None,
        "correct": False,
        "error": {"type": type(last_error).__name__, "message": str(last_error)[:1000]},
        "wall_latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "http_retries": retries,
    }


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    correct = sum(row["status"] == "ok" and row["correct"] for row in rows)
    tool_selection_correct = sum(
        row["status"] == "ok" and (
            row["predicted_action"] == row["gold_action"]
            or (row["gold_action"] == "no_tool" and row["predicted_action"] in NO_FUNCTION_ACTIONS)
        )
        for row in rows
    )
    errors = sum(row["status"] == "error" for row in rows)
    responded = total - errors
    return {
        "total": total,
        "correct": correct,
        "tool_selection_correct": tool_selection_correct,
        "errors": errors,
        "incorrect_responses": responded - correct,
        "accuracy_all_cases": correct / total if total else None,
        "tool_selection_accuracy_all_cases": tool_selection_correct / total if total else None,
        "accuracy_responded_only": correct / responded if responded else None,
    }


def summarize(cases: list[dict[str, Any]], latest: dict[str, dict[str, Any]], run: dict[str, Any]) -> dict[str, Any]:
    completed = [latest[case["id"]] for case in cases if case["id"] in latest]
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in completed:
        by_stratum[row["stratum"]].append(row)
        by_category[row["category"]].append(row)
    return {
        "schema": "bfcl-v1-jev-eval-summary/v1",
        "generated_at_utc": utc_now(),
        "run": run,
        "expected_count": len(cases),
        "completed_count": len(completed),
        "is_complete": len(completed) == len(cases),
        "overall": metrics(completed),
        "by_stratum": {key: metrics(by_stratum[key]) for key in STRATA if key in by_stratum},
        "by_category": {key: metrics(by_category[key]) for key in sorted(by_category)},
        "error_cases": [row["case_id"] for row in completed if row["status"] == "error"],
        "response_models": dict(sorted(Counter(str(row.get("response_model")) for row in completed if row["status"] == "ok").items())),
        "note": "accuracy_all_cases scores the exact BFCL-derived action. tool_selection_accuracy_all_cases also credits clarify/cannot_answer on BFCL no-call cases because no function was selected. Errors count as incorrect in both. Neither scores arguments or tool execution.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True,
                        help="Short result name, such as laya, kev, von, or rizzo")
    parser.add_argument("--endpoint", help="Base URL of an already-running native /v1/systemone server")
    parser.add_argument("--model", help="Model field sent in each System One request")
    parser.add_argument("--model-revision", help="Declared pinned model revision for the run manifest")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, help="Resumable prediction JSONL (default: results/bfcl_v1_<provider>.jsonl)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--retries", type=int, default=2, help="Retries after an HTTP/response error per case")
    parser.add_argument("--rerun-errors", action="store_true", help="Retry previously recorded error cases on resume")
    parser.add_argument("--limit", type=int, help="Process at most this many pending cases; useful for a smoke test")
    parser.add_argument("--api-key-env", help="Environment variable containing a server bearer token")
    args = parser.parse_args()
    if args.timeout <= 0 or args.retries < 0 or (args.limit is not None and args.limit < 1):
        parser.error("timeout must be positive, retries non-negative, and limit positive")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", args.provider):
        parser.error("provider must be a lowercase name using letters, digits, _ or -")
    defaults = DEFAULTS.get(args.provider, {})
    endpoint = (args.endpoint or defaults.get("endpoint") or "").rstrip("/")
    model = args.model or defaults.get("model")
    revision = args.model_revision or defaults.get("revision")
    if not endpoint or not model or not revision:
        parser.error("custom providers require --endpoint, --model and --model-revision")
    cases_path = args.cases.resolve()
    output = (args.output or ROOT / "results" / f"bfcl_v1_{args.provider}.jsonl").resolve()
    meta_path = output.with_suffix(".meta.json")
    summary_path = output.with_suffix(".summary.json")
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    if args.api_key_env and not api_key:
        parser.error(f"{args.api_key_env} is unset or empty")

    cases, source_manifest = load_cases(cases_path)
    run_config = {
        "provider": args.provider,
        "requested_model": model,
        "declared_model_revision": revision,
        "endpoint": endpoint,
        "cases_path": str(cases_path),
        "cases_sha256": sha256(cases_path),
        "source_tag": source_manifest.get("source_tag") if source_manifest else None,
        "source_commit": source_manifest.get("source_commit") if source_manifest else None,
        "selection_review_sha256": (source_manifest.get("selection_review") or {}).get("sha256") if source_manifest else None,
    }
    run_id = hashlib.sha256(json.dumps(run_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if output.exists() and not meta_path.exists():
        raise ValueError(f"{output} exists without {meta_path}; refusing an ambiguous resume")
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if metadata.get("run_id") != run_id or metadata.get("run") != run_config:
            raise ValueError(f"{meta_path} belongs to a different model, endpoint, or case hash")
    else:
        probe = server_probe(endpoint, api_key, min(args.timeout, 10.0))
        metadata = {
            "schema": "bfcl-v1-jev-eval-run/v1",
            "created_at_utc": utc_now(),
            "run_id": run_id,
            "run": run_config,
            "server_probe": probe,
            "server_identity": stable_server_identity(probe, model),
            "predictions_file": str(output),
        }
        write_json_atomic(meta_path, metadata)

    latest, attempts = read_predictions(output, run_id, {case["id"] for case in cases})
    pending = [case for case in cases if case["id"] not in latest or (args.rerun_errors and latest[case["id"]]["status"] == "error")]
    if args.limit is not None:
        pending = pending[:args.limit]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as stream:
        for index, case in enumerate(pending, 1):
            row = predict_case(case, endpoint=endpoint, model=model, api_key=api_key,
                               timeout=args.timeout, retries=args.retries, run_id=run_id,
                               attempt=attempts[case["id"]] + 1)
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            latest[case["id"]] = row
            print(f"[{index}/{len(pending)}] {case['id']}: {row['predicted_action'] or row['status']}", file=sys.stderr)
    summary = summarize(cases, latest, run_config)
    write_json_atomic(summary_path, summary)
    print(json.dumps({"summary": str(summary_path), "completed_count": summary["completed_count"],
                      "expected_count": summary["expected_count"], "overall": summary["overall"],
                      "by_stratum": summary["by_stratum"]}, indent=2))
    return 2 if summary["is_complete"] and summary["overall"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
