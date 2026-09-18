#!/usr/bin/env bash
# gate.sh — validation entrypoint for somnus-plugin-system
#
# HONEST BY CONSTRUCTION. This gate reports NOT RUN when a prerequisite is absent.
# It never converts a missing prerequisite into a pass. Per AGENTS.md section 7,
# validation in this repository is experimentation, not a pytest suite.
#
# Exit codes:  0 = all runnable checks passed   1 = a check FAILED
# NOT RUN checks do not fail the gate. They are reported and counted.

set -uo pipefail
cd "$(dirname "$0")"

PASS=0; FAIL=0; SKIP=0; PEND=0
ok()   { echo "  PASS     $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL     $1"; FAIL=$((FAIL+1)); }
skip() { echo "  NOT RUN  $1"; echo "           prerequisite: $2"; SKIP=$((SKIP+1)); }
pend() { echo "  PENDING  $1"; echo "           lands in: $2"; PEND=$((PEND+1)); }

echo "=============================================================="
echo " somnus-plugin-system gate"
echo " base: $(git rev-parse --short HEAD 2>/dev/null || echo 'no git')"
echo " date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "=============================================================="

# ---------------------------------------------------------------- structure
echo
echo "[1] Structural integrity"

EXPECTED_MODULES="plugin_base plugin_manager security discovery orchestration hot_reload marketplace host_protocols host_capabilities plugin_worker"
missing=""
for m in $EXPECTED_MODULES; do [ -f "$m.py" ] || missing="$missing $m.py"; done
if [ -z "$missing" ]; then ok "all expected root modules present"
else bad "missing modules:$missing"; fi

cp_missing=0
for f in AGENTS.md CLAUDE.md SPEC.md HOST_BOUNDARY.md OPSEC.md AUTHORITY_MAP.md \
         STATE.md TASK.md CONTEXT.md MEMORY.md NOTEPAD.md filetree.md README.md workflows.md; do
  if [ ! -f "$f" ]; then bad "control-plane surface missing: $f"; cp_missing=1; fi
done
[ $cp_missing -eq 0 ] && ok "all 14 control-plane surfaces present"

# ---------------------------------------------------- host boundary contract
echo
echo "[2] Host boundary — Protocol seam, no donor imports"
DONOR=$(grep -rn '^from \(core\|schemas\|backend\)\.' ./*.py 2>/dev/null || true)
DONOR_COUNT=$(printf '%s' "$DONOR" | grep -c . || true)
if [ "$DONOR_COUNT" -eq 0 ]; then
  ok "no donor core/schemas/backend imports"
else
  bad "host boundary drift: donor imports reappeared ($DONOR_COUNT)"
  printf '%s\n' "$DONOR" | sed 's/^/           /'
fi
HOST_SITES=$(grep -n '^from host_protocols import' plugin_base.py plugin_manager.py hot_reload.py host_capabilities.py 2>/dev/null || true)
HOST_COUNT=$(printf '%s' "$HOST_SITES" | grep -c . || true)
if [ "$HOST_COUNT" -ge 4 ]; then
  ok "host_protocols Protocol seam present ($HOST_COUNT import sites)"
else
  bad "host_protocols seam missing or incomplete ($HOST_COUNT sites)"
fi

# ------------------------------------------------------- lineage convergence
echo
echo "[3] Lineage convergence (lands in PACKET-002)"
for sym in PluginManifest PluginBase PluginDiscovery PluginFileWatcher; do
  n=$(grep -c "^class $sym\b" ./*.py 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
  if [ "$n" -eq 1 ]; then ok "$sym defined once"
  elif [ "$n" -eq 0 ]; then bad "$sym not defined anywhere"
  else
    pend "$sym defined $n times (expected 1)" "PACKET-002"
    grep -n "^class $sym\b" ./*.py | sed 's/^/           /'
  fi
done

# --------------------------------------------------------- packet contract
echo
echo "[4] Packet field contract"
VP="$HOME/.claude/skills/somnus-accelerate/scripts/validate-packet.mjs"
if ! command -v node >/dev/null 2>&1; then
  skip "packet validation" "node not on PATH"
elif [ ! -f "$VP" ]; then
  skip "packet validation" "validator not found at $VP"
elif [ -z "$(ls packets/*.md 2>/dev/null)" ]; then
  skip "packet validation" "no packets in packets/"
else
  for p in packets/*.md; do
    if node "$VP" "$p" >/dev/null 2>&1; then ok "$(basename "$p")"
    else bad "$(basename "$p") — missing or unpopulated required field"; fi
  done
fi

# --------------------------------------------------------- empty-file check
echo
echo "[5] Zero-byte file check"
EMPTY=$(find installed -type f -size 0 2>/dev/null | grep -v '__init__.py' || true)
EMPTYN=$(printf '%s' "$EMPTY" | grep -c . || true)
if [ "$EMPTYN" -eq 0 ]; then ok "no unexpected zero-byte files under installed/"
else
  pend "$EMPTYN zero-byte files under installed/" "PACKET-004"
  printf '%s\n' "$EMPTY" | head -5 | sed 's/^/           /'
fi

# ------------------------------------------------- foreign artifact drift
echo
echo "[5b] Foreign artifact drift"
KNOWN="plugin_base plugin_manager security discovery orchestration hot_reload marketplace host_protocols host_capabilities plugin_worker validate_system"
STRAY=""
for f in $(git ls-files --others --exclude-standard -- '*.py' 2>/dev/null); do
  case "$f" in installed/*|test/harness_plugins/*|test/system/runs/*) continue ;; esac
  base=$(basename "$f" .py); hit=0
  for k in $KNOWN; do [ "$base" = "$k" ] && hit=1; done
  [ "$hit" -eq 0 ] && STRAY="$STRAY $f"
done
if [ -z "$STRAY" ]; then ok "no untracked .py outside the 7 known modules"
else
  pend "untracked .py files not part of this repository:$STRAY" "operator decision — see TASK.md"
fi

if [ -f requirements.txt ] && [ -f pyproject.toml ]; then
  pend "requirements.txt coexists with pyproject.toml — they disagree" "operator decision — see TASK.md"
  echo "           pyproject.toml is the dependency contract. Do NOT pip install -r requirements.txt."
else
  ok "single dependency contract"
fi

# ------------------------------------------------------------ import truth
echo
echo "[6] Import chain"
if [ ! -x .venv/bin/python ]; then
  skip "import chain (all 7 modules)" "no .venv — run PACKET-001"
  skip "dependency resolution"        "no .venv — run PACKET-001"
else
  for m in $EXPECTED_MODULES; do
    if err=$(.venv/bin/python -c "import $m" 2>&1); then ok "import $m"
    else
      first=$(printf '%s' "$err" | tail -1)
      case "$first" in
        *core.memory_core*|*schemas.session*|*core.security_layer*|*"No module named 'core'"*|*"No module named 'schemas'"*)
          echo "  EXPECTED import $m blocked at host boundary — see HOST_BOUNDARY.md"
          echo "           $first" ;;
        *) bad "import $m — $first" ;;
      esac
    fi
  done
fi

# ------------------------------------------------------------------ tests
echo
echo "[7] Test suite"
skip "test suite" "none exists in this repository by design — validation here is experimentation (AGENTS.md section 7)"

# ----------------------------------------------------------------- summary
echo
echo "=============================================================="
echo " PASS $PASS   FAIL $FAIL   PENDING $PEND   NOT RUN $SKIP"
echo
echo " base:  $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$UNCOMMITTED" -gt 0 ]; then
  echo " WARNING: $UNCOMMITTED uncommitted path(s) in the working tree."
  echo "          The control plane may exist only as uncommitted state."
  echo "          A git checkout/stash/reset --hard would destroy it."
fi
if [ "$FAIL" -gt 0 ]; then
  echo " GATE: FAIL"
  echo "=============================================================="
  exit 1
fi
echo
echo " GATE: PASS on runnable checks."
if [ "$PEND" -gt 0 ]; then
  echo " *** $PEND PENDING finding(s) — known unresolved work still live in source."
  echo " *** Do NOT report this gate as green without naming them."
fi
if [ "$SKIP" -gt 0 ]; then
  echo " *** $SKIP check(s) NOT RUN. A NOT RUN is not a pass."
  echo " *** Name the check and its prerequisite when reporting."
fi
echo "=============================================================="
exit 0
