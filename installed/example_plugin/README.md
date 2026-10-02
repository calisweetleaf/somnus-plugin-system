# example_plugin

Canonical reference plugin for `somnus-plugin-system`.

This plugin subclasses `plugin_base.PluginBase`, validates against the
canonical `PluginManifest`, exports `router` from `api/__init__.py`, and
loads through `PluginManager.load_plugin()`.

Reserved directories (`agents/`, `workflows/`, `memory/`, `assets/`) exist
because the authoring contract names them. No loader executes them yet.
That absence is recorded here rather than hidden behind dummy runtimes.

Runtime plugin id: `example_plugin_1.0.0`.
