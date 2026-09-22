# somnus_reference

This plugin is the worked example of the canonical contract.

The loader in `plugin_manager.py` reads `manifest.json`, executes `plugin.py`,
and requires `class Plugin` to subclass `plugin_base.PluginBase`. It then
imports `api/__init__.py` and mounts the exported `router` at
`/api/plugins/{plugin_id}`.

Directories the loader does not read:

- `agents/` — action catalog, loaded by `plugin.py`
- `workflows/` — node descriptors, loaded by `plugin.py`
- `memory/` — checkpoint classification, loaded by `plugin.py`
- `assets/` — this document

`trusted` is false. There is no signature. A signature, when present, must be
`rsa_pss_sha256:<hex>` over the canonical tree with the signature field
removed. `network_access_required` is false, and `NETWORK_ACCESS` is not
declared, so `network_request` raises `PermissionError`.
