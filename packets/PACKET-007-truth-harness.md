# PACKET-007 — Truth Harness

**Owner:** next executing agent
**Status:** LANDED
**Depends on:** PACKET-006
**Size:** one session
**Priority:** high — the control plane must not have to remember itself

## Mission

Turn the component harness into an adversarial end-to-end runtime probe. Label
component checks versus E2E checks. Generate mechanical STATE facts from
executable probes.

## Required Reads

- `validate_system.py`
- `gate.sh`
- `STATE.md`
- `OPSEC.md`

## Invariant

- No pytest.
- Every run writes JSON + MD under `test/system/runs/<timestamp>/`.
- Humans write interpretation; counts come from probes.

## Surfaces

- `validate_system.py`, `gate.sh`, `tools/state_probe.py`, `STATE.md`, `OPSEC.md`

## Hard Bans

- Do not call 19/19 a system validation.
- Do not vendor host implementations into `host_protocols.py`.

## Validation

```bash
./.venv/bin/python validate_system.py
bash gate.sh
```

## Exit

Record adversarial case list and probe output. Mark PACKET-007 landed.

## Handoff

The substrate is a plugin runtime. Next work is host embedding, not more mechanisms.
