# OPSEC — Trust Boundary and Security Posture

> **Normative.** This document owns the security posture of somnus-plugin-system.
>
> This repository loads and executes third-party code. That is its purpose. The security
> surfaces are therefore load-bearing, and several of them do not currently do what their names
> suggest. This document states what is actually enforced versus what is merely named.
>
> Full defect detail with reproduction notes: `docs/DEFECT_INDEX.md`.

---

## 1. Threat model

This is a plugin substrate embedded in larger Somnus systems. The adversarial surface is:

1. **A malicious or compromised plugin archive** — arbitrary code execution at load time.
2. **A malicious or compromised registry** — supply-chain substitution of an archive.
3. **A path-traversal payload inside an archive** — filesystem writes outside the plugin root.
4. **A resource-exhaustion plugin** — unbounded memory, CPU, or disk.

Operator context: this work is private, isolated, with no external publication requirement. That
lowers exposure. It does not make a checksum into a signature.

---

## 2. What is actually enforced

| Control | Surface | Reality |
|---|---|---|
| AST-based code analysis | `security.py:181` `CodeAnalyzer` | **Real.** Parses plugin source and flags dangerous constructs. |
| Restricted import hook | `security.py:158` `restricted_import` | **Real.** Constrains what a sandboxed plugin may import. |
| Sandbox environment | `security.py:70` `SandboxEnvironment` | **Real construction.** Builds a restricted namespace with a source template that shadows `sys`, `os`, `builtins` (`security.py:141-143`). |
| Cryptographic validator | `security.py:442` `CryptographicValidator` | **Real implementation.** |
| Dependency analysis | `security.py:529` `DependencyAnalyzer` | **Real.** |
| Manifest schema validation | `plugin_base.py:79` pydantic | **Real, but unreachable** until dependencies are installed. |
| Regex blocklist scan | `plugin_manager.py:334` `PluginSecurityManager` | **Real but shallow** — substring/regex matching on `__import__`, `eval`, `exec`, `open`, `subprocess.`, `os.system`, `os.popen`. Trivially evaded by string construction. Superseded lineage. |

**Current state: none of the above executes**, because `security.py` cannot be imported. See §3.

---

## 3. Security findings

**Resolution, 2026-09-22.** SEC-01 through SEC-10 are closed in source. The descriptions below are the original findings and are kept so a regression is recognizable. The marketplace network path remains disabled by default. Closing the defects did not turn the network on.

| Finding | Status |
|---|---|
| SEC-01 | CLOSED. `security.py` imports. `PluginPermission` is defined on `plugin_base`. |
| SEC-02 | CLOSED. Download verification requires RSA-PSS. A missing signature fails closed. A sha256 checksum is not accepted as a signature. |
| SEC-03 | CLOSED. `verify_developer_signature` is on the install path. |
| SEC-04 | CLOSED. No placeholder PEM is registered. `SOMNUS_MARKETPLACE_TRUST_KEYS` is the key source. |
| SEC-05 | CLOSED. Extraction goes through `safe_extract_zip` before the security scan. |
| SEC-06 | CLOSED. The stream counts bytes and unlinks the file past the cap. |
| SEC-07 | CLOSED. The gate uses a local score computed after verification. Server-asserted trust is stored and ignored by the gate. |
| SEC-08 | CLOSED as a default-host hijack. Registry URLs default empty. `network_enabled` defaults false. |
| SEC-09 | CLOSED. Manifest memory and CPU ceilings are measured and enforced before the next call. |
| SEC-10 | CLOSED. A bad signature fails validation. `trusted: true` does not skip verification. |

## 3a. Original findings

### SEC-01 — `security.py` cannot be imported — **CRITICAL, blocks all enforcement**

`security.py:34` imports `PluginPermission` from `plugin_base`, which does not define it
(`plugin_manager.py:75` does). The symbol is consumed at `security.py:220`, `:223`, `:226`,
`:229`, `:419`, `:433`, `:703-705`.

**Consequence: the entire code-analysis and sandboxing layer is unreachable.** Any plugin
loading that happens today happens with no security analysis whatsoever.

*Status:* grep-verified absent. `ImportError` **PREDICTED, NOT YET OBSERVED** — dependency
install is the prerequisite. *Fix lands in:* PACKET-002.

### SEC-02 — Signature verification is a checksum — **HIGH**

`marketplace.py:329-353` `verify_download` fetches JSON from a **server-supplied**
`signature_url` and compares `signature_data['signature']` against a locally computed
`hashlib.sha256(file_data).hexdigest()` (`:346-347`).

The same origin that serves the artifact serves its hash. This authenticates **nothing** against
a compromised or hostile registry — it only detects transport corruption. It additionally
returns `True` unconditionally when `signature_url` is absent (`:330-331`), so an archive
carrying no signature URL passes.

*Fix:* route verification through `TrustSystem.verify_developer_signature`. See SEC-03.

### SEC-03 — Real RSA verification exists and is never called — **HIGH**

`marketplace.py:164-183` `TrustSystem.verify_developer_signature` implements genuine
RSA-PSS/SHA-256 verification via `cryptography`. Repository-wide grep finds **zero call sites**.
The correct control is present and disconnected.

Compounding: `marketplace.py:182` catches `(InvalidSignature, Exception)` — the `Exception` arm
makes `InvalidSignature` redundant and swallows key-parse errors as "unverified" rather than
surfacing them.

### SEC-04 — Placeholder public key shipped as official — **HIGH**

`marketplace.py:839-842` contains a literal truncated PEM whose body includes the text
`...official marketplace public key...`. It is seeded via
`register_developer_key("morpheus_official", ...)` at `:844`. `register_developer_key` (`:185`)
stores raw bytes **without parsing**, so the malformed key fails only inside
`load_pem_public_key` (`:169`) — code that is unreachable anyway per SEC-03.

**No real trust root is configured in this repository.**

### SEC-05 — Zip-slip in archive extraction — **HIGH**

`marketplace.py:479` and `:538` call `zip_ref.extractall(extract_dir)` with **no member-path
sanitization**. Archive entries containing `../` write outside the intended directory.

Aggravating: the security scan runs **after** extraction (`:494`, `:553`). By the time analysis
happens, traversal writes have already landed.

`install_from_archive` (`:524`) is the only genuinely functional installation path in the
module — and it is the one carrying this defect.

### SEC-06 — Unbounded download despite a declared size cap — **MEDIUM**

`marketplace.py:290` checks `Content-Length` against the configured cap, but the streaming loop
at `:298-300` never enforces it. A server that omits or understates `Content-Length` writes
unbounded bytes to disk.

### SEC-07 — Trust gate is either a hard block or a no-op — **MEDIUM**

`install_from_listing` gates on `listing.trust_score < trust_level_threshold / 5.0` = `0.6`
(`:458`, `:64`). But `install_from_marketplace` (`:445-453`) takes the listing straight from
`RegistryClient.get_plugin_details`, whose `trust_score` comes from
`data.get('trust_score', 0.0)` (`:421`) and is **never recomputed** by `TrustSystem` on that
path. `calculate_trust_score` runs only in `search_plugins` (`:734`) and `get_plugin_details`
(`:743`).

So installation either always fails at `0.0`, or accepts a trust score **the remote server
asserted about itself**.

### SEC-08 — Registry hosts do not exist — **INFORMATIONAL, but a hijack surface**

`marketplace.py:58-59` hardcode `https://marketplace.morpheus.ai` and
`https://community.morpheus.ai`. Neither exists. `community_registry_url` is never read
repository-wide, so `MarketplaceProvider.COMMUNITY` (`:35`) has no transport at all.

**Unregistered domains referenced by a client that would trust their responses are a
registration-hijack surface.** Before any network path is enabled, either the domains must be
controlled or the defaults must be removed.

TLS itself is configured correctly: `ssl.create_default_context(cafile=certifi.where())`
(`:198`), `TCPConnector` (`:199`), 30s total / 10s connect timeouts (`:200`).

### SEC-09 — Resource limits are declared and unenforceable — **MEDIUM**

`manifest.memory_limit_mb` and `manifest.cpu_limit_percent` (`plugin_base.py:114-115`) are
validated on input and not enforced at runtime. `orchestration.py:635` hardcodes CPU usage to
`0.0`, so `ResourceMonitor.check_resource_limits` (`:124`) can never trip its CPU branch
(`:132`). `ExecutionResult.memory_used` (`:74`) is never assigned.

A resource-exhaustion plugin is currently unconstrained by these fields.

### SEC-10 — Signature verification stub returns True — **MEDIUM, superseded lineage**

`plugin_manager.py:426-430` — the superseded lineage's signature verification is a stub that
**always returns `True`**. Scheduled for deletion in PACKET-002. Do not carry it forward.

---

## 4. Operational rules

- **Leave the marketplace network path disabled** unless an operator sets `network_enabled`
  and supplies registry URLs. SEC-02 through SEC-08 are closed in source. That closure is not
  permission to point the client at an unregistered host. Local archive install and the local
  registry transport are the paths that run with the defaults.
- **Never treat `trusted: true` in a manifest as meaningful.** It is a self-assertion by the
  plugin author with no verification behind it.
- **Never log credentials, tokens, or keys.** Per global operator doctrine.
- **Never commit a real private key or a real trust root to this repository.** The placeholder
  at `marketplace.py:839-842` must be replaced by host-supplied configuration, not by a
  committed key.
- **Assume plugin code is hostile.** `security.py` imports and its analysis runs during load.
  A pattern match or a failed signature rejects the plugin.

---

## 5. Resolution ownership

| Finding | Landed |
|---|---|
| SEC-01, SEC-10 | Lineage convergence. `PluginPermission` lives on `plugin_base`. Signature verification fails closed. |
| SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-07, SEC-08 | Marketplace hardening, 2026-09-22. Network remains off by default. |
| SEC-09 | Orchestration admission, 2026-09-22. Manifest ceilings are enforced. |
