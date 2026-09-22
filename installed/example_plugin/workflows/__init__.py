"""Reserved workflow surface.

``PluginManager`` does not import this package. ``plugin.py`` loads
``nodes.py`` by file path. Graph execution lives in ``orchestration.py``
and consumes a ``WorkflowDefinition``, not this directory.
"""
