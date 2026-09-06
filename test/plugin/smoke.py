#!/usr/bin/env python3
"""Smoke harness for the plugin module.

Runs the module's public surface against real fixtures and records the run
to test/plugin/runs/<timestamp>/{result.json,result.md,result.log}.

Exit codes:
    0 - all checks passed
    1 - at least one check failed
    2 - harness error
"""
from __future__ import annotations

import importlib
import json
import site
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOMAIN = "plugin"
RUNS_DIR = PROJECT_ROOT / "test" / DOMAIN / "runs"
SOTA_RUN_PATH = PROJECT_ROOT / "SOTA_RUN.md"

site.addsitedir(str(PROJECT_ROOT))


@dataclass(frozen=True)
class CheckResult:
    """Result of one smoke-harness check."""

    name: str
    status: str
    duration_ms: float = 0.0
    detail: str = ""


class SerializedCheck(TypedDict):
    """JSON-ready smoke check result."""

    name: str
    status: str
    duration_ms: float
    detail: str


class RunPayload(TypedDict):
    """JSON-ready smoke harness payload."""

    domain: str
    timestamp: float
    checks: list[SerializedCheck]
    pass_count: int
    fail_count: int
    skip_count: int


def check_load() -> CheckResult:
    """Verify the module loads cleanly without side effects."""
    start = time.perf_counter()
    try:
        loaded_module = importlib.import_module(f"tools.native.{DOMAIN}")
    except (ImportError, SyntaxError, RuntimeError, OSError) as error:
        return CheckResult(
            name="load",
            status="fail",
            duration_ms=(time.perf_counter() - start) * 1000.0,
            detail=f"import error: {error}",
        )

    module_name = getattr(loaded_module, "__name__", DOMAIN)
    return CheckResult(
        name="load",
        status="pass",
        duration_ms=(time.perf_counter() - start) * 1000.0,
        detail=f"imported {module_name} cleanly",
    )


def check_describe_path() -> CheckResult:
    """Verify the generated public function handles a real filesystem path."""
    start = time.perf_counter()
    try:
        loaded_module = importlib.import_module(f"tools.native.{DOMAIN}")
        describe_path = getattr(loaded_module, "describe_path")
        result = describe_path(PROJECT_ROOT)
        expected_path = str(PROJECT_ROOT.expanduser())
        if result.status != "ok":
            return CheckResult(
                name="describe_path",
                status="fail",
                duration_ms=(time.perf_counter() - start) * 1000.0,
                detail=f"expected status ok, got {result.status}",
            )
        if result.normalized_path != expected_path:
            return CheckResult(
                name="describe_path",
                status="fail",
                duration_ms=(time.perf_counter() - start) * 1000.0,
                detail=f"expected normalized path {expected_path}, got {result.normalized_path}",
            )
    except (AttributeError, ImportError, SyntaxError, TypeError, ValueError, RuntimeError, OSError) as error:
        return CheckResult(
            name="describe_path",
            status="fail",
            duration_ms=(time.perf_counter() - start) * 1000.0,
            detail=f"behavior error: {error}",
        )

    return CheckResult(
        name="describe_path",
        status="pass",
        duration_ms=(time.perf_counter() - start) * 1000.0,
        detail=f"normalized PROJECT_ROOT to {expected_path}",
    )


def check_session_id_round_trip() -> CheckResult:
    """Verify SessionID parses, namespaces, and survives a dict round-trip."""
    start = time.perf_counter()
    try:
        loaded_module = importlib.import_module(f"tools.native.{DOMAIN}")
        session_id_type = getattr(loaded_module, "SessionID")
        parsed = session_id_type.from_string("  sess:alpha-01  ")
        if parsed.to_string() != "sess:alpha-01":
            return CheckResult(
                name="session_id_round_trip",
                status="fail",
                duration_ms=(time.perf_counter() - start) * 1000.0,
                detail=f"whitespace trim failed, got {parsed.to_string()!r}",
            )
        if not parsed.is_namespaced() or parsed.namespace() != "sess":
            return CheckResult(
                name="session_id_round_trip",
                status="fail",
                duration_ms=(time.perf_counter() - start) * 1000.0,
                detail="namespace detection failed for sess:alpha-01",
            )
        rebuilt = session_id_type.from_dict(parsed.to_dict())
        if rebuilt != parsed:
            return CheckResult(
                name="session_id_round_trip",
                status="fail",
                duration_ms=(time.perf_counter() - start) * 1000.0,
                detail="dict round-trip did not preserve equality",
            )
    except (AttributeError, ImportError, SyntaxError, TypeError, ValueError, RuntimeError, OSError) as error:
        return CheckResult(
            name="session_id_round_trip",
            status="fail",
            duration_ms=(time.perf_counter() - start) * 1000.0,
            detail=f"behavior error: {error}",
        )

    return CheckResult(
        name="session_id_round_trip",
        status="pass",
        duration_ms=(time.perf_counter() - start) * 1000.0,
        detail="parsed sess:alpha-01, detected namespace sess, dict round-trip equal",
    )


def check_session_id_file_round_trip() -> CheckResult:
    """Verify SessionID payload survives a real filesystem JSON round-trip."""
    start = time.perf_counter()
    try:
        loaded_module = importlib.import_module(f"tools.native.{DOMAIN}")
        session_id_type = getattr(loaded_module, "SessionID")
        original = session_id_type.from_string("node_07.session-A")
        with tempfile.TemporaryDirectory(prefix="somnus-plugin-") as raw:
            payload_path = Path(raw) / "session.json"
            payload_path.write_text(json.dumps(original.to_dict()), encoding="utf-8")
            loaded = json.loads(payload_path.read_text(encoding="utf-8"))
            rebuilt = session_id_type.from_dict(loaded)
            if rebuilt != original:
                return CheckResult(
                    name="session_id_file_round_trip",
                    status="fail",
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    detail="filesystem JSON round-trip did not preserve equality",
                )
    except (AttributeError, ImportError, SyntaxError, TypeError, ValueError, RuntimeError, OSError) as error:
        return CheckResult(
            name="session_id_file_round_trip",
            status="fail",
            duration_ms=(time.perf_counter() - start) * 1000.0,
            detail=f"behavior error: {error}",
        )

    return CheckResult(
        name="session_id_file_round_trip",
        status="pass",
        duration_ms=(time.perf_counter() - start) * 1000.0,
        detail="wrote session.json to temp dir and rebuilt equal SessionID",
    )


def check_session_id_rejections() -> CheckResult:
    """Verify SessionID rejects empty, oversized, and malformed values."""
    start = time.perf_counter()
    try:
        loaded_module = importlib.import_module(f"tools.native.{DOMAIN}")
        session_id_type = getattr(loaded_module, "SessionID")
        cases = ["   ", "x" * 129, "bad value!", ":leading-colon"]
        rejected = 0
        for candidate in cases:
            try:
                session_id_type.from_string(candidate)
            except ValueError:
                rejected += 1
            else:
                return CheckResult(
                    name="session_id_rejections",
                    status="fail",
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    detail=f"accepted invalid candidate {candidate!r}",
                )
        if rejected != len(cases):
            return CheckResult(
                name="session_id_rejections",
                status="fail",
                duration_ms=(time.perf_counter() - start) * 1000.0,
                detail=f"rejected {rejected} of {len(cases)} invalid candidates",
            )
    except (AttributeError, ImportError, SyntaxError, TypeError, ValueError, RuntimeError, OSError) as error:
        return CheckResult(
            name="session_id_rejections",
            status="fail",
            duration_ms=(time.perf_counter() - start) * 1000.0,
            detail=f"behavior error: {error}",
        )

    return CheckResult(
        name="session_id_rejections",
        status="pass",
        duration_ms=(time.perf_counter() - start) * 1000.0,
        detail="rejected empty, oversized, spaced, and leading-colon values",
    )


def main() -> int:
    """Run smoke checks and write all required artifacts."""
    runs_dir = RUNS_DIR / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    runs_dir.mkdir(parents=True, exist_ok=True)

    checks = [
        check_load(),
        check_describe_path(),
        check_session_id_round_trip(),
        check_session_id_file_round_trip(),
        check_session_id_rejections(),
    ]
    serialized_checks = [_serialize_check(check) for check in checks]
    payload: RunPayload = {
        "domain": DOMAIN,
        "timestamp": time.time(),
        "checks": serialized_checks,
        "pass_count": sum(1 for check in checks if check.status == "pass"),
        "fail_count": sum(1 for check in checks if check.status == "fail"),
        "skip_count": sum(1 for check in checks if check.status == "skip"),
    }

    summary = _render_md(payload)
    (runs_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (runs_dir / "result.md").write_text(summary + "\n", encoding="utf-8")
    (runs_dir / "result.log").write_text(_render_log(payload), encoding="utf-8")
    _update_sota_run(payload, runs_dir)
    print(summary)
    return 0 if payload["fail_count"] == 0 else 1


def _serialize_check(check: CheckResult) -> SerializedCheck:
    """Convert a check result into a JSON-ready dictionary."""
    return {
        "name": check.name,
        "status": check.status,
        "duration_ms": check.duration_ms,
        "detail": check.detail,
    }


def _render_md(payload: RunPayload) -> str:
    """Render the run as a first-person narrative summary."""
    lines = [f"# Smoke run for {payload['domain']}", ""]
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(payload["timestamp"]))
    lines.append(f"I ran the smoke harness on {timestamp}.")
    lines.append(
        f"I found {payload['pass_count']} passing checks, "
        f"{payload['fail_count']} failing checks, and {payload['skip_count']} skipped checks."
    )
    lines.append("")
    for check in payload["checks"]:
        marker = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[check["status"]]
        lines.append(f"- [{marker}] {check['name']} ({check['duration_ms']:.1f} ms) - {check['detail']}")
    return "\n".join(lines)


def _render_log(payload: RunPayload) -> str:
    """Render a deterministic stdout/stderr style log artifact."""
    lines = [
        f"command: python3 test/{{DOMAIN}}/smoke.py",
        "stdout:",
        _render_md(payload),
        "",
        "stderr:",
        "<none captured by harness>",
        "",
    ]
    return "\n".join(lines)


def _update_sota_run(payload: RunPayload, runs_dir: Path) -> None:
    """Update the project SOTA_RUN.md ledger with the latest smoke run."""
    if not SOTA_RUN_PATH.exists():
        return

    marker_start = "<!-- SOTA_RUN_LATEST_START -->"
    marker_end = "<!-- SOTA_RUN_LATEST_END -->"
    run_relative = runs_dir.relative_to(PROJECT_ROOT).as_posix()
    status = "pass" if payload["fail_count"] == 0 else "fail"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(payload["timestamp"]))
    latest_block = "\n".join(
        [
            marker_start,
            "## Latest Smoke Run",
            "",
            "- status: " + status,
            "- timestamp_utc: " + timestamp,
            "- run_dir: " + run_relative,
            "- result_json: " + run_relative + "/result.json",
            "- result_md: " + run_relative + "/result.md",
            "- result_log: " + run_relative + "/result.log",
            "- pass_count: " + str(payload["pass_count"]),
            "- fail_count: " + str(payload["fail_count"]),
            "- skip_count: " + str(payload["skip_count"]),
            marker_end,
        ]
    )
    ledger = SOTA_RUN_PATH.read_text(encoding="utf-8")
    if marker_start in ledger and marker_end in ledger:
        before = ledger.split(marker_start, 1)[0].rstrip()
        after = ledger.split(marker_end, 1)[1].lstrip()
        ledger = before + "\n\n" + latest_block + "\n\n" + after
    else:
        ledger = ledger.rstrip() + "\n\n" + latest_block + "\n"
    SOTA_RUN_PATH.write_text(ledger, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
