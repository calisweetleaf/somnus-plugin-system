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

**Current state (2026-09-18, PACKET-005):** `PluginManager.load_plugin` calls
`SecurityManager.validate_plugin`, then assembles `HostCapabilityFacade`. Isolated
plugins are staged through `create_sandbox` and imported only in
`plugin_worker.worker_entry`. Marketplace extract-then-validate remains SEC-05.
Permissions are object-capability policy.

---

## 3. Active security findings

### SEC-01 — `security.py` cannot be imported — **RESOLVED**

`PluginPermission` lives in `plugin_base.py`. `import security` succeeds. The production
loader calls `SecurityManager.validate_plugin`. Historical claim that the symbol was
missing is stale; do not revive it.

*Residual:* analysis is static for HOST_INTEGRATED / VERIFIED. ISOLATED plugins
that fail the host-integrated safety bar still load in a worker; CRITICAL
issues are the remaining refusal class for that domain.

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

### SEC-10 — Signature verification stub returns True — **RESOLVED by deletion**

`PluginSecurityManager` and its always-true `_verify_signature` were deleted in PACKET-002.
Signature checking on the load path is `security.SecurityManager._verify_plugin_signature`
when a signature is present and security level is HIGH.

---

## 4. Operational rules

- **Never enable the marketplace network path** until SEC-02 through SEC-08 are resolved.
  `install_from_archive` with a locally verified archive is the only defensible install route
  today, and only after SEC-05 is fixed.
- **Never treat `trusted: true` in a manifest as a verified trust root.** It is a
  self-assertion. It now selects `HOST_INTEGRATED` domain. That is policy input,
  not proof of origin.
- **Never log credentials, tokens, or keys.** Per global operator doctrine.
- **Never commit a real private key or a real trust root to this repository.** The placeholder
  at `marketplace.py:839-842` must be replaced by host-supplied configuration, not by a
  committed key.
- **Assume plugin code is hostile.** Static analysis runs on load. Untrusted
  `security_level >= 4` plugins import in a worker. Do not treat a passing scan
  as a sandbox for host-integrated plugins.

---

## 5. Resolution ownership

| Finding | Lands in |
|---|---|
| SEC-01 | `packets/PACKET-002-lineage-convergence.md` |
| SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-07, SEC-08 | Not yet packetized. A marketplace hardening packet must be written before any network path is enabled. |
| SEC-09 | Not yet packetized. Depends on `orchestration.py` resource instrumentation. |
| SEC-10 | `packets/PACKET-002-lineage-convergence.md` (deletion) |
