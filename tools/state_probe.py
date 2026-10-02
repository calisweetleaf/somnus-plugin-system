#!/usr/bin/env python3
"""Mechanical STATE probe for somnus-plugin-system.

Writes test/system/STATE_PROBE.{json,md} and refreshes the generated
block in STATE.md. Humans write interpretation only.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEGIN = "<!-- STATE_PROBE_BEGIN -->"
END = "<!-- STATE_PROBE_END -->"


def _run(args: list[str]) -> str:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return (result.stdout or "").strip()


def _class_count(symbol: str) -> int:
    total = 0
    for path in ROOT.glob("*.py"):
        text = path.read_text()
        total += len(re.findall(rf"^class {re.escape(symbol)}\b", text, re.M))
    return total


def _latest_harness() -> dict:
    runs = sorted((ROOT / "test" / "system" / "runs").glob("*/result.json"))
    if not runs:
        return {}
    return json.loads(runs[-1].read_text())


def _resolved_sec() -> list[str]:
    text = (ROOT / "OPSEC.md").read_text()
    return re.findall(r"### (SEC-\d+)[^\n]*RESOLVED[^\n]*", text)


def _pending_from_gate_note() -> list[str]:
    return []


def collect() -> dict:
    harness = _latest_harness()
    summary = harness.get("summary", {})
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head": _run(["git", "rev-parse", "--short", "HEAD"]),
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "duplicate_class_counts": {
            "PluginManifest": _class_count("PluginManifest"),
            "PluginBase": _class_count("PluginBase"),
            "PluginDiscovery": _class_count("PluginDiscovery"),
            "PluginFileWatcher": _class_count("PluginFileWatcher"),
        },
        "harness": {
            "timestamp": harness.get("timestamp"),
            "pass_count": summary.get("pass_count"),
            "fail_count": summary.get("fail_count"),
            "component_pass": summary.get("component_pass"),
            "component_total": summary.get("component_total"),
            "e2e_pass": summary.get("e2e_pass"),
            "e2e_total": summary.get("e2e_total"),
            "result": summary.get("result"),
        },
        "resolved_sec": _resolved_sec(),
        "pending_gate_findings": _pending_from_gate_note(),
    }


def render_md(facts: dict) -> str:
    counts = facts["duplicate_class_counts"]
    harness = facts["harness"]
    lines = [
        f"- Generated: `{facts['generated_at']}`",
        f"- HEAD: `{facts['head']}` on `{facts['branch']}`",
        f"- Duplicate class counts: Manifest={counts['PluginManifest']} Base={counts['PluginBase']} Discovery={counts['PluginDiscovery']} FileWatcher={counts['PluginFileWatcher']}",
        f"- Latest harness: {harness.get('result')} pass={harness.get('pass_count')} fail={harness.get('fail_count')} component={harness.get('component_pass')}/{harness.get('component_total')} e2e={harness.get('e2e_pass')}/{harness.get('e2e_total')} ({harness.get('timestamp')})",
        f"- Resolved SEC ids: {', '.join(facts['resolved_sec']) or 'none'}",
        f"- Pending gate findings: {', '.join(facts['pending_gate_findings']) or 'none recorded by probe'}",
    ]
    return "\n".join(lines) + "\n"


def write_state(facts: dict, block: str) -> None:
    state_path = ROOT / "STATE.md"
    text = state_path.read_text()
    if BEGIN not in text or END not in text:
        text = text.rstrip() + f"\n\n## 5. Mechanical probe\n\n{BEGIN}\n{block}{END}\n"
    else:
        pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
        text = pattern.sub(f"{BEGIN}\n{block}{END}", text)
    state_path.write_text(text)


def main() -> int:
    facts = collect()
    block = render_md(facts)
    out_dir = ROOT / "test" / "system"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "STATE_PROBE.json").write_text(json.dumps(facts, indent=2) + "\n")
    (out_dir / "STATE_PROBE.md").write_text("# Mechanical STATE probe\n\n" + block)
    write_state(facts, block)
    print(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
