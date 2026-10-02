#!/usr/bin/env bash
# Cloud Agent bootstrap for somnus-plugin-system.
#
# Idempotent. Creates ./.venv and installs the pyproject dependency contract
# (the 9 declared third-party dependencies plus the `serve` extra: uvicorn).
#
# Host types are declared in host_protocols.py (Protocol seam). This script
# does not vendor a host MemoryManager. The embedding system supplies concrete
# implementations that structurally satisfy those protocols. See HOST_BOUNDARY.md.
set -euo pipefail
cd "$(dirname "$0")/.."

# python3-venv is required to create virtual environments on Debian/Ubuntu base
# images and is not present on the default Cloud Agent image.
if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
  if [ "$(id -u)" -eq 0 ]; then APT="apt-get"; else APT="sudo apt-get"; fi
  $APT update -qq
  $APT install -y -qq python3-venv
fi

# Create the virtual environment the gate expects at ./.venv (idempotent).
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/pip install -e '.[serve]'

echo "somnus-plugin-system environment ready (.venv). Validate with: bash gate.sh"
