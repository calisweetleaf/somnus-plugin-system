"""Workflow node descriptors named by the manifest.

These descriptors are data. The orchestrator does not discover them from
disk. A host that builds a ``WorkflowDefinition`` can copy ``node_id`` into
a graph step.
"""
from __future__ import annotations

from typing import Any, Dict, List


def catalog() -> List[Dict[str, Any]]:
    return [
        {
            "node_id": "reference.observe",
            "plugin_method": "record_observation",
            "inputs": ["note"],
            "outputs": ["observation"],
        }
    ]
