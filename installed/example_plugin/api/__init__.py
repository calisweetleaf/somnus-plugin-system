"""API package entry. The loader imports this module and reads ``router``."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROUTES = Path(__file__).resolve().parent / "routes.py"
_spec = importlib.util.spec_from_file_location("somnus_reference_api_routes", _ROUTES)
if _spec is None or _spec.loader is None:
    raise ImportError("somnus_reference api/routes.py is missing")
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

router = _module.router

__all__ = ["router"]
