"""Transactional plugin lifecycle: zip-safe install, generations, host routes.

Modified: 2026-09-18
Modified by: Stilgar (Cursor Grok 4.6, Daeron operator)
Justification: PACKET-006. Install, reload, and routing share one generation
    model. Archives are inspected before any extract. Live generation N is never
    deleted before N+1 boot-probes. The host owns /api/plugins/{id}/{path}.
Provenance: packets/PACKET-006-transactional-lifecycle.md
Files: plugin_lifecycle.py
"""
from __future__ import annotations

import os
import shutil
import stat
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class ZipSlipError(ValueError):
    """Archive members were rejected before extraction."""


@dataclass
class EndpointDescriptor:
    method: str
    path: str
    handler: Callable[..., Any]


@dataclass
class PluginGeneration:
    generation: int
    plugin_id: str
    instance: Any
    path: Path
    endpoints: Dict[Tuple[str, str], EndpointDescriptor] = field(default_factory=dict)
    module_name: str = ""
    serving: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GenerationTable:
    """plugin_id -> serving generation. Swing is a single dict assignment."""

    def __init__(self) -> None:
        self.current: Dict[str, PluginGeneration] = {}
        self.counter: Dict[str, int] = {}

    def next_number(self, plugin_id: str) -> int:
        self.counter[plugin_id] = self.counter.get(plugin_id, 0) + 1
        return self.counter[plugin_id]

    def swing(self, generation: PluginGeneration) -> Optional[PluginGeneration]:
        previous = self.current.get(generation.plugin_id)
        generation.serving = True
        self.current[generation.plugin_id] = generation
        if previous is not None:
            previous.serving = False
        return previous

    def drop(self, plugin_id: str) -> Optional[PluginGeneration]:
        generation = self.current.pop(plugin_id, None)
        if generation is not None:
            generation.serving = False
        return generation


def inspect_zip_members(archive_path: Path) -> List[str]:
    """Reject `..`, absolute paths, and links before any extract."""
    reasons: List[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or name.startswith("\\") or (len(name) >= 2 and name[1] == ":"):
                reasons.append(f"absolute path: {info.filename}")
            parts = Path(name).parts
            if ".." in parts:
                reasons.append(f"path traversal: {info.filename}")
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and stat.S_ISLNK(mode):
                reasons.append(f"symbolic link: {info.filename}")
            extra = info.extra or b""
            if b"symlink" in extra.lower():
                reasons.append(f"link extra field: {info.filename}")
    return reasons


def extract_zip_safe(archive_path: Path, destination: Path) -> None:
    """Extract only after member inspection. Never call ZipFile.extractall."""
    reasons = inspect_zip_members(archive_path)
    if reasons:
        raise ZipSlipError("; ".join(reasons))
    destination.mkdir(parents=True, exist_ok=True)
    dest_root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            relative = info.filename.replace("\\", "/").lstrip("/")
            if not relative or relative.endswith("/"):
                target = dest_root / relative
                if not _is_within(dest_root, target):
                    raise ZipSlipError(f"escaped directory: {info.filename}")
                target.mkdir(parents=True, exist_ok=True)
                continue
            target = dest_root / relative
            if not _is_within(dest_root, target):
                raise ZipSlipError(f"escaped file: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as handle:
                shutil.copyfileobj(source, handle)


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def promote_live_link(live: Path, generation_dir: Path) -> Optional[Path]:
    """Point the stable live name at generation_dir. Never rmtree live first.

    Returns the retired directory if a real directory was moved aside.
    """
    live.parent.mkdir(parents=True, exist_ok=True)
    retired: Optional[Path] = None
    if live.exists() and not live.is_symlink():
        retired = live.with_name(f".{live.name}.retired")
        if retired.exists() or retired.is_symlink():
            if retired.is_dir() and not retired.is_symlink():
                shutil.rmtree(retired)
            else:
                retired.unlink()
        os.rename(live, retired)
    tmp = live.with_name(f".{live.name}.swp")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    try:
        tmp.symlink_to(generation_dir.resolve())
        os.replace(tmp, live)
    except Exception:
        if retired is not None and not live.exists():
            os.rename(retired, live)
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()
        raise
    return retired


def generation_root(plugin_base_dir: Path, plugin_name: str) -> Path:
    return plugin_base_dir / "installed" / ".generations" / plugin_name


def allocate_generation_dir(plugin_base_dir: Path, plugin_name: str, generation: int) -> Path:
    path = generation_root(plugin_base_dir, plugin_name) / f"g{generation}"
    path.mkdir(parents=True, exist_ok=True)
    return path
