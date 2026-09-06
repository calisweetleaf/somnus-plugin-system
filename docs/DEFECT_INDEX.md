DEFECT_INDEX.md
Classification: INTERNAL
Version: 1.0
Date: 2026-09-05
Author/Origin: Claude Code (execution arm), source-read only, no runtime executed
Status: DRAFT

## Scope and Evidence Standard

This is an evidence-class defect register for `somnus-plugin-system` at commit `5278e3c`. Every entry below was located by direct source read this session and confirmed with `grep`/`sed` line extraction. Each entry carries an evidence classification:

- **VERIFIED-BY-READ** — the defect's mechanism is fully traceable from source alone (control flow, type signatures, dead-code reachability). No runtime execution is needed to know the defect exists.
- **PREDICTED** — the defect requires runtime execution (a live interpreter, network access, or installed dependencies) to observe directly. Marked entries have not been executed this session; the prerequisite is stated explicitly.

A repository-wide grep this session for `NotImplementedError`, `TODO`, `FIXME`, `XXX`, `HACK`, and bare-ellipsis (`...`) function bodies returned **zero matches** across all seven modules. Every defect catalogued below is live, executing code — none of it is an acknowledged stub, placeholder, or self-flagged incompleteness. This repository does not know it is broken in these ways.

---

## Summary Table

| ID | Severity | Module | One-line |
|---|---|---|---|
| D-001 | HIGH | orchestration.py | Priority queue dequeues in enum-definition order, not declared priority order — REALTIME drains last. |
| D-002 | HIGH | orchestration.py | `ThreadPoolExecutor.shutdown(wait=True, timeout=30)` — `timeout` is not a valid kwarg; guaranteed `TypeError` on orchestrator stop. |
| D-009 | MEDIUM | orchestration.py | Reactive workflow mode registers event handlers into a dict that is never read by anything. |
| D-010 | MEDIUM | orchestration.py | Graph workflow mode executes serially with no concurrency and no cycle detection. |
| D-011 | MEDIUM | orchestration.py | CPU usage is hardcoded to `0.0`; memory usage defaults to `0` and is never assigned — resource limit checks can never trip on CPU. |
| D-012 | MEDIUM | orchestration.py | Metrics loop guards on a `metrics` attribute the real `PluginBase` (plugin_manager.py lineage) never has — permanent no-op. |
| D-013 | HIGH | orchestration.py | Callback assigned after enqueue; a lock-contention race leaves `request.callback` `None`, silently discarding a result and hanging the awaiting future forever. |
| D-014 | LOW | orchestration.py | `except ValueError: pass` in queue removal swallows a dequeue/remove race, leaving stale pending-request accounting. |
| D-003 | HIGH | marketplace.py | Zip-slip: `extractall()` with no path sanitization, security scan runs after extraction. |
| D-004 | HIGH | marketplace.py | "Signature verification" is a same-server checksum compare — authenticates nothing; unconditionally passes when signature URL absent. |
| D-005 | MEDIUM | marketplace.py | Real RSA-PSS signature verification exists and is never called anywhere in the repository. |
| D-006 | HIGH | marketplace.py | A placeholder truncated PEM literally containing "...official marketplace public key..." is registered as the trusted key for the official registry. |
| D-007 | LOW | marketplace.py | `except (InvalidSignature, Exception)` makes the specific exception clause dead and swallows key-parse errors as "unverified" rather than surfacing them. |
| D-008 | MEDIUM | marketplace.py | Content-Length cap is checked once but never enforced in the streaming download loop — unbounded write to disk possible. |
| D-015 | LOW | marketplace.py | `community_registry_url` is defined and never read anywhere — the COMMUNITY provider has no transport. |
| D-016 | HIGH | marketplace.py | Both registry hostnames are non-existent domains; no server, schema, or fixture backs the marketplace wire format anywhere. |
| D-017 | HIGH | marketplace.py | Trust gate is either an unconditional hard block (real path always scores 0.0) or a no-op (marketplace path trusts the remote server's self-asserted score). |
| D-018 | MEDIUM | marketplace.py | Reported cache never survives a call; the real cache is scoped to a context manager that closes before stats are read — the 24-hour cache duration setting is unreachable. |
| D-019 | LOW | plugin_manager.py | Marketplace integration entry point is a docstring plus a comment plus `pass`. |
| D-020 | LOW | plugin_base.py | Two ABC interfaces are declared and implemented by nothing. |
| D-021 | LOW | plugin_base.py | In-place hand patch of donor memory-type constants, with the prior (now-wrong) values still visible in trailing comments. |
| D-022 | HIGH | plugin_base.py / plugin_manager.py | The manifest shape with the richest declared surface is not the manifest shape the only reachable loader actually constructs. |

Grouped by module: **orchestration.py** — D-001, D-002, D-009 through D-014 (8 defects). **marketplace.py** — D-003 through D-008, D-015 through D-018 (10 defects). **plugin_manager.py** — D-019 (1 defect, plus co-listed in D-022). **plugin_base.py** — D-020, D-021 (2 defects, plus co-listed in D-022). **Cross-lineage** — D-022 (1 defect).

---

## orchestration.py

### D-001 — Inverted priority queue
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ

`ExecutionPriority` (`orchestration.py:33-38`) is declared in ascending-severity order: `LOW`, `NORMAL`, `HIGH`, `CRITICAL`, `REALTIME`. `ExecutionQueue.__init__` (`orchestration.py:151`) builds `self.queues` as a dict literal in REALTIME-first order (`orchestration.py:154-160`):
```python
self.queues = {
    ExecutionPriority.REALTIME: deque(),
    ExecutionPriority.CRITICAL: deque(),
    ExecutionPriority.HIGH: deque(),
    ExecutionPriority.NORMAL: deque(),
    ExecutionPriority.LOW: deque()
}
```
This ordering is decorative. `dequeue()` (`orchestration.py:172`) does not iterate `self.queues` — it iterates the enum itself: `for priority in ExecutionPriority:` (`orchestration.py:175`), which walks enum members in **definition order** (`LOW` first, `REALTIME` last), independent of the dict's insertion order.

**Failure mode:** the queue drains `LOW`-priority requests first and `REALTIME`-priority requests last whenever any lower-priority queue is non-empty — the exact inversion of the priority scheme's evident intent.

**Reproduce/confirm:** read `orchestration.py:33-38` (enum definition order) against `orchestration.py:172-181` (`dequeue`'s iteration target). No execution required — the dict literal at `:154-160` is provably unread by `dequeue`.

---

### D-002 — Guaranteed TypeError on orchestrator shutdown
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ (mechanism); PREDICTED (the raised exception itself — requires a live interpreter to observe the traceback)

`PluginExecutor.shutdown` (`orchestration.py:255-256`):
```python
def shutdown(self):
    self.executor.shutdown(wait=True, timeout=30)
```
`self.executor` here is a `concurrent.futures.ThreadPoolExecutor` (assigned at `orchestration.py:201`). `ThreadPoolExecutor.shutdown` accepts only `wait` and `cancel_futures` as keyword arguments in the Python standard library — `timeout` is not a valid parameter for this method on any supported CPython version.

This method is reached from `PluginOrchestrator.stop()` (`orchestration.py:492`), where `self.executor` (a `PluginExecutor` instance, assigned at `orchestration.py:460`) has its `.shutdown()` called with no arguments at `orchestration.py:510`. Because `PluginOrchestrator.executor` is a `PluginExecutor`, not a bare `ThreadPoolExecutor`, this call dispatches to `PluginExecutor.shutdown` at `orchestration.py:255-256`, which then makes the invalid call against the underlying `ThreadPoolExecutor`.

**Failure mode:** every call to `PluginOrchestrator.stop()` raises `TypeError: shutdown() got an unexpected keyword argument 'timeout'` before orchestrator teardown can complete.

**Reproduce/confirm:** static — read `orchestration.py:201` (assigns `ThreadPoolExecutor`), `:255-256` (invalid kwarg call), `:460` (`PluginOrchestrator.executor = PluginExecutor()`), `:510` (`self.executor.shutdown()` dispatching into the buggy method). Confirming the raised traceback specifically requires running `PluginOrchestrator.stop()` under a live interpreter — not done this session.

---

### D-009 — Reactive workflow mode is inert
**Severity:** MEDIUM
**Evidence:** VERIFIED-BY-READ

`WorkflowEngine._execute_reactive` (`orchestration.py:414`) builds a local `event_handlers` dict (`orchestration.py:415`), populates it per trigger (`orchestration.py:424`), and stores it into `execution.context['event_handlers']` (`orchestration.py:426`). A repository-wide grep for `event_handlers` shows no read access to this key anywhere else in `orchestration.py` or any other module.

**Failure mode:** selecting `ExecutionMode.REACTIVE` for a workflow silently does nothing beyond populating a dict that no code ever consults — no event ever triggers a registered handler.

**Reproduce/confirm:** grep `event_handlers` repository-wide; the only write is `orchestration.py:426`, no reads exist.

---

### D-010 — Graph workflow mode is serial and cycle-blind
**Severity:** MEDIUM
**Evidence:** VERIFIED-BY-READ

`WorkflowEngine._execute_graph` (`orchestration.py:379`) maintains an `available_steps` set (`orchestration.py:382`) and processes it with `while available_steps:` (`orchestration.py:391`), popping one step (`orchestration.py:392`) and `await`-ing its execution before the loop iterates again. Independent branches of the dependency graph are never scheduled concurrently — each step, regardless of whether it shares a dependency with the previous one, blocks the next iteration.

No cycle-detection logic exists in this method: `available_steps.add(next_step_index)` (`orchestration.py:407`) adds successor steps without checking whether they have already been visited or whether a dependency cycle exists. A cyclic dependency graph does not raise an error — affected steps are simply never added to `available_steps` and are silently dropped from execution once their unmet dependency never resolves.

**Failure mode:** (a) no parallelism in a mode whose entire purpose is dependency-graph execution; (b) a cyclic graph produces silently incomplete workflow execution rather than a diagnostic error.

**Reproduce/confirm:** read `orchestration.py:379-412`; trace that every path to `_execute_graph`'s inner loop body contains an `await` with no `asyncio.gather` or task-group construct, and that no visited-set or cycle check exists before `:407`'s `add`.

---

### D-011 — Hardcoded zero resource metrics
**Severity:** MEDIUM
**Evidence:** VERIFIED-BY-READ

`orchestration.py:635`:
```python
0.0,  # CPU usage would be calculated here
```
This literal is passed as a metrics argument inside the execution result path (`orchestration.py:614` calls `check_resource_limits`, and the CPU branch of that check, `orchestration.py:132`, per the source read this session, can never observe a non-zero CPU value because nothing upstream of it ever computes one). `ExecutionResult.memory_used` defaults to `0` (`orchestration.py:74`) and a grep of `execute_plugin_method` (`orchestration.py:198-241` region) shows no assignment to `result.memory_used` anywhere in that method body — it is read out at `orchestration.py:634` still carrying its default.

**Failure mode:** `ResourceMonitor.check_resource_limits` (`orchestration.py:124`) can never trip its CPU-usage branch, because the value it evaluates is permanently `0.0`. Memory-based resource limiting is equally inert because `memory_used` is never populated above its zero default.

**Reproduce/confirm:** read `orchestration.py:74` (default), `orchestration.py:198-241` (`execute_plugin_method` body, no assignment to `memory_used`), `orchestration.py:635` (hardcoded `0.0` comment), `orchestration.py:124-132` (`check_resource_limits`, CPU branch).

---

### D-012 — Metrics loop is a permanent no-op against the real loader
**Severity:** MEDIUM
**Evidence:** VERIFIED-BY-READ

`orchestration.py:714`:
```python
if hasattr(plugin, 'metrics'):
```
This guards the body at `orchestration.py:714-...` (through roughly `:724` per the metrics-loop routine) that would otherwise record per-plugin metrics. The `PluginBase` class actually reachable through the only wired loader (`plugin_manager.py:147`, `class PluginBase(ABC)`) declares no `metrics` attribute anywhere in its body. A grep of `plugin_manager.py` for `self.metrics` or `metrics:` inside the `PluginBase` class definition returns nothing.

**Failure mode:** `hasattr(plugin, 'metrics')` evaluates `False` for every plugin instantiated through the real loader, so the metrics-recording body at `:714` onward never executes, for any plugin, ever, under the current lineage split.

**Reproduce/confirm:** read `plugin_manager.py:147` through its full class body for absence of a `metrics` attribute; read `orchestration.py:714` for the guard.

---

### D-013 — Latent callback race
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ (mechanism); PREDICTED (the actual hang — requires concurrent execution under real lock contention to trigger)

`PluginOrchestrator.execute_plugin_request` (`orchestration.py:513`):
1. `orchestration.py:514` — `await self.execution_queue.enqueue(request)`. `enqueue` (`orchestration.py:165-171`) acquires `self.lock` (`asyncio.Lock`, assigned `orchestration.py:162`) before appending the request to its priority deque and to `self.pending_requests`.
2. `orchestration.py:528` — **after** the enqueue call returns, `request.callback = callback` is assigned.
3. A worker thread dequeuing this same request (`orchestration.py:648`) checks `if request.callback:` before invoking it (`orchestration.py:650`).

If `enqueue`'s internal lock acquisition (`orchestration.py:165`, `async with self.lock:`) suspends the calling coroutine under contention — i.e., another coroutine holds the lock when `execute_plugin_request` reaches step 1 — a worker task can dequeue and process this exact request before line 528 has executed, because the request object was already inserted into `pending_requests` inside the locked section, and Python's cooperative scheduling permits the worker's task to run during the `await` suspension between enqueue's completion and line 528's synchronous assignment on the original task. When this interleaving occurs, the worker at `:648` observes `request.callback is None`, takes the `if request.callback:` branch's false path, discards the result, and `await result_future` at `orchestration.py:531` never resolves.

**Failure mode:** under the specific interleaving described, the original caller hangs on `await result_future` indefinitely — no exception, no timeout, no log entry, a permanently stuck coroutine.

**Reproduce/confirm:** static trace of `orchestration.py:513-533` (request construction and callback assignment order) against `orchestration.py:648-650` (worker's callback-null check). Confirming the actual hang requires running the orchestrator under real concurrent load with induced lock contention — not done this session.

---

### D-014 — Swallowed exception in queue removal
**Severity:** LOW
**Evidence:** VERIFIED-BY-READ

`ExecutionQueue.remove` (`orchestration.py:186-192`):
```python
async def remove(self, request_id: str) -> bool:
    async with self.lock:
        request = self.pending_requests.pop(request_id, None)
        if request:
            try:
                self.queues[request.priority].remove(request)
                return True
            except ValueError:
                pass
        return False
```
If a concurrent `dequeue()` (`orchestration.py:172-181`) has already popped `request` out of its priority deque (`orchestration.py:178`, `queue.popleft()`) between this method's `pending_requests.pop` and its own `self.queues[...].remove(request)` call, `deque.remove` raises `ValueError` (item not in deque), which is caught and silently discarded at `:190-191`.

**Failure mode:** the request has already been removed from `pending_requests` (`:187`) regardless of whether the deque-side removal succeeded, so this is not itself a double-removal bug — but the silent `pass` means a genuine dequeue/remove race is never logged or surfaced, leaving no trace that the race occurred, which will hide the symptom if this interacts with D-013's race under load.

**Reproduce/confirm:** read `orchestration.py:186-192`, cross-reference against `dequeue`'s `queue.popleft()` at `orchestration.py:178` for the race window.

---

## marketplace.py

### D-003 — Zip-slip
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ

Two call sites extract untrusted archive contents with no member-path sanitization:
- `marketplace.py:479` — `zip_ref.extractall(extract_dir)`, inside the archive-install path.
- `marketplace.py:538` — `zip_ref.extractall(archive_path)`'s destination `extract_dir`, inside a second install path (confirmed at `marketplace.py:536-538`: `with zipfile.ZipFile(archive_path, 'r') as zip_ref: zip_ref.extractall(extract_dir)`).

`zipfile.ZipFile.extractall` performs no sanitization of member names containing `../` path traversal sequences. A crafted archive entry named e.g. `../../../../etc/somefile` will be written outside `extract_dir`.

The security scan that does exist runs after extraction has already completed in both paths: `marketplace.py:494` (first path, `self.security_manager.validate_plugin(plugin_dir, manifest)` called after `extractall` at `:479`) and `marketplace.py:553` (second path, same pattern after `extractall` at `:538`).

**Failure mode:** a malicious plugin archive can write files to arbitrary filesystem locations reachable by the process's write permissions, before any security check runs, and regardless of what that check would have found.

**Reproduce/confirm:** read `marketplace.py:475-500` and `:535-555` for the extract-then-validate ordering; no runtime execution needed — `zipfile.ZipFile.extractall`'s lack of path sanitization is documented standard-library behavior, and no sanitizing wrapper appears anywhere in this module.

---

### D-004 — Checksum presented as signature verification
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ

`RegistryClient.verify_download` (`marketplace.py:329-350`):
```python
async def verify_download(self, listing: PluginListing, file_path: Path) -> bool:
    if not listing.signature_url or not self.config.verify_signatures:
        return True
    ...
    signature_data = await response.json()
    signature = signature_data.get('signature')
    algorithm = signature_data.get('algorithm', 'sha256')
    with open(file_path, 'rb') as f:
        file_data = f.read()
    if algorithm == 'sha256':
        file_hash = hashlib.sha256(file_data).hexdigest()
        return file_hash == signature
    return False
```
`signature_url` is a server-supplied URL (part of the same `PluginListing` the server itself provided). The method fetches JSON from that URL and compares a locally computed SHA-256 hash of the downloaded artifact against a `signature` field the same remote server asserted. Since the artifact and the "signature" both originate from the same untrusted party, this scheme authenticates message integrity against transport corruption at best — it provides zero protection against a malicious or compromised server serving a malicious artifact alongside a matching hash of that same malicious artifact.

Additionally, `marketplace.py:330-331` returns `True` unconditionally whenever `listing.signature_url` is falsy — absence of a signature URL is treated as verification success, not failure.

**Failure mode:** any registry response (or MITM of one) can serve an arbitrary artifact with a self-consistent hash and pass "verification" unconditionally; omitting `signature_url` entirely also passes.

**Reproduce/confirm:** read `marketplace.py:329-350` in full; the logic is self-contained and requires no runtime execution to assess — the trust root and the artifact source are provably the same party by inspection of the code path alone.

---

### D-005 — Real RSA verification is dead code
**Severity:** MEDIUM
**Evidence:** VERIFIED-BY-READ

`TrustSystem.verify_developer_signature` (`marketplace.py:164-182`) implements genuine RSA-PSS/SHA-256 signature verification via the `cryptography` library:
```python
def verify_developer_signature(self, data: bytes, signature: str, developer_id: str) -> bool:
    ...
    public_key = serialization.load_pem_public_key(self.verification_keys[developer_id])
    signature_bytes = bytes.fromhex(signature)
    public_key.verify(signature_bytes, data, padding.PSS(...), hashes.SHA256())
    return True
    except (InvalidSignature, Exception):
        return False
```
A repository-wide grep of `verify_developer_signature` shows exactly one occurrence — its own definition at `marketplace.py:168`. No other line in any of the seven modules calls this method.

**Failure mode:** none directly — this is unreachable code, not a runtime hazard. Its significance is that the module contains a technically sound verification primitive that the actual install/verify paths (D-004) do not use.

**Reproduce/confirm:** grep `verify_developer_signature` repository-wide; one match, the definition.

---

### D-006 — Placeholder public key shipped as official
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ

`marketplace.py:838-842` (inside `create_marketplace`):
```python
official_key = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2gD+6F8H9L4Q8l0mV5R1
...official marketplace public key...
-----END PUBLIC KEY-----"""

marketplace.trust_system.register_developer_key("morpheus_official", official_key)
```
The PEM body contains the literal placeholder text `...official marketplace public key...` in place of base64 key material — this is not a valid, complete PEM-encoded public key. It is registered under the identifier `"morpheus_official"` via `register_developer_key` (`marketplace.py:185-188`), which stores the raw bytes verbatim with no parsing or validation at registration time: `self.verification_keys[developer_id] = public_key` (`marketplace.py:186`).

Because `register_developer_key` never parses the key, this malformed placeholder is accepted silently at registration. It would only fail — inside `load_pem_public_key` (`marketplace.py:169`) — if `verify_developer_signature` were ever called for `"morpheus_official"`. Per D-005, that method has zero call sites, so this malformed key is never exercised and its brokenness is currently invisible.

**Failure mode:** a placeholder value is present in the codebase under a name (`morpheus_official`) that reads as production trust material. If D-005's dead code is ever wired up, this specific key would cause a hard failure (unparseable PEM) rather than a security gap — but as shipped, its presence under an "official" label in live code is itself the defect.

**Reproduce/confirm:** read `marketplace.py:838-844` for the literal placeholder text; read `marketplace.py:185-188` for the unvalidated storage.

---

### D-007 — Exception handler defeats itself
**Severity:** LOW
**Evidence:** VERIFIED-BY-READ

`marketplace.py:182`:
```python
except (InvalidSignature, Exception):
    return False
```
`InvalidSignature` is a subclass of `Exception`; listing it alongside the bare `Exception` in the same tuple is redundant — the bare `Exception` clause alone would already catch every `InvalidSignature` instance. The practical effect is that this handler catches everything, including `KeyError`, `TypeError`, or a `ValueError` from `bytes.fromhex(signature)` (`marketplace.py:170`) if `signature` is malformed — all such errors are folded into the same `return False` ("unverified") outcome as a genuine cryptographic verification failure, with no distinguishing log or re-raise.

**Failure mode:** a malformed or missing key, a malformed signature string, or an actual cryptographic mismatch are all indistinguishable at the call site — all read as "verification failed," which hampers diagnosing why a given developer key or signature is rejected. Given D-005 (this method is unreachable in practice), the immediate operational impact is nil, but the pattern would mask real errors the moment the method is wired up.

**Reproduce/confirm:** read `marketplace.py:164-182` in full; the redundant tuple and its consequences are apparent from the `except` clause alone.

---

### D-008 — Unbounded download despite a declared size cap
**Severity:** MEDIUM
**Evidence:** VERIFIED-BY-READ

`marketplace.py:290` checks a declared `Content-Length` response header against a configured size cap before beginning the streaming download loop. The streaming loop itself (`marketplace.py:298-300`) writes each received chunk to disk without re-checking cumulative bytes written against that cap.

**Failure mode:** a server that omits the `Content-Length` header, or sends a `Content-Length` value smaller than the actual body it streams, causes the download loop to write an effectively unbounded number of bytes to disk — the cap exists only as a pre-flight header check, not as an enforced streaming invariant.

**Reproduce/confirm:** read `marketplace.py:285-300`; confirm the cap comparison occurs once (against the header) and the subsequent `async for chunk in response.content.iter_chunked(...)`-style loop (`:298-300`) has no running-total comparison against the same cap. Observing an actual unbounded write requires a live network response with a lying or absent `Content-Length` — not executed this session (PREDICTED for the runtime symptom; VERIFIED-BY-READ for the missing enforcement).

---

### D-015 — Dead registry endpoint
**Severity:** LOW
**Evidence:** VERIFIED-BY-READ

`MarketplaceConfig.community_registry_url` (`marketplace.py:59`) is defined with a default value. A repository-wide grep of `community_registry_url` shows exactly one occurrence — its own definition at `:59`. `MarketplaceProvider.COMMUNITY` (`marketplace.py:35`) exists as an enum value and is referenced at `marketplace.py:143` inside trust-score calculation (a scoring weight for community-provided listings), but every actual network call in `RegistryClient` (search, details, versions, ratings, report — `marketplace.py:238,256,271,356,368`) builds its URL from `self.config.official_registry_url` exclusively.

**Failure mode:** `MarketplaceProvider.COMMUNITY` is a value that can appear in data but has no corresponding transport — there is no code path that would ever fetch from a community registry, despite the config field existing to support one.

**Reproduce/confirm:** grep `community_registry_url` (one match: the definition) and grep `official_registry_url` (five call sites, all URL construction).

---

### D-016 — Both registry hosts are non-existent
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ (for absence of any backing implementation in this repository); PREDICTED (for DNS/network resolution failure, which requires an actual network call to observe)

`marketplace.py:58-59`:
```python
official_registry_url: str = "https://marketplace.morpheus.ai"
community_registry_url: str = "https://community.morpheus.ai"
```
No server implementation, OpenAPI/schema document, or test fixture for either host exists anywhere in this repository. The wire format these endpoints are expected to return is defined only implicitly, by what `RegistryClient._parse_listing` (`marketplace.py:378-422`, per the field-access pattern read this session) expects to find in a JSON response — there is no independent schema document to validate against.

The only marketplace code path that can function without these hosts is `PluginInstaller.install_from_archive` (`marketplace.py:524`, confirmed operating on a local `archive_path` rather than a network fetch), which does not depend on either registry URL.

**Failure mode:** every registry-dependent code path (search, install-from-marketplace, ratings, update-check) will fail to connect at the network layer against these hostnames, or will succeed against whatever actually resolves for `marketplace.morpheus.ai` / `community.morpheus.ai` today, in either case not against a system this repository defines or controls.

**Reproduce/confirm:** grep the repository for any server implementation, fixture, or schema file matching these hosts (none found this session); confirming actual DNS/connection failure requires a live network call — not performed this session.

---

### D-017 — Trust gate is either a hard block or a no-op
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ

Two independent install code paths apply the trust threshold inconsistently:
- `PluginInstaller.install_from_listing` (`marketplace.py:455`) gates at `marketplace.py:458`: `if listing.trust_score < self.config.trust_level_threshold / 5.0:` where `trust_level_threshold` defaults to `3` (`marketplace.py:64`), making the effective threshold `0.6`.
- `PluginListing.trust_score` (`marketplace.py:113`) defaults to `0.0` and is populated directly from server data via `trust_score=data.get('trust_score', 0.0)` (`marketplace.py:421`, inside listing parsing) for any listing that did not go through `search_plugins` or `get_plugin_details`.
- `calculate_trust_score` (`marketplace.py:133`, the method that would independently compute a trust score rather than trust the server's assertion) is invoked only at `marketplace.py:734` (inside `search_plugins`) and `marketplace.py:743` (inside `get_plugin_details`).
- `install_from_marketplace` (`marketplace.py:445-453`) calls `install_from_listing` (`:453`) directly on a listing obtained without necessarily passing through `search_plugins`/`get_plugin_details` first — in which case `listing.trust_score` still carries whatever raw value `data.get('trust_score', 0.0)` produced (`:421`), never recomputed by `calculate_trust_score`.

**Failure mode:** if a listing reaches `install_from_listing` without having passed through `search_plugins`/`get_plugin_details`, its `trust_score` is `0.0` by default and the gate at `:458` always fails (`0.0 < 0.6`) — a hard, unconditional block. If it did pass through one of those two methods, the "trust score" being gated on is exactly whatever value the remote registry server self-reported in its JSON response (`:421`'s `data.get('trust_score', ...)`), which the server controls entirely — a no-op from a trust-verification standpoint.

**Reproduce/confirm:** read `marketplace.py:64` (threshold constant), `:113` and `:421` (trust_score default and population from server data), `:445-458` (the two install entry points and the gate), `:733-743` (the only two call sites of `calculate_trust_score`).

---

### D-018 — Cache never survives a call
**Severity:** MEDIUM
**Evidence:** VERIFIED-BY-READ

`marketplace.py:830` (inside a stats/status method):
```python
'cached_entries': len(getattr(self, '_registry_cache', {}))
```
A grep of `_registry_cache` repository-wide shows exactly one occurrence — this read, via `getattr` with a default of `{}`. No assignment to `self._registry_cache` exists anywhere. This attribute is therefore always absent, and `cached_entries` is always reported as `0`.

The cache that actually exists is `RegistryClient.cache` (`marketplace.py:195`, `self.cache: Dict[str, Tuple[datetime, Any]] = {}`), read and written at `marketplace.py:425-434` inside the registry request path. However, `RegistryClient` instances are constructed inside `async with` blocks at four call sites (`marketplace.py:730, 740, 806, 810`, per this session's read) — each such block creates a fresh `RegistryClient`, uses it, and lets it go out of scope at block exit, discarding `self.cache` along with it. `MarketplaceConfig.cache_duration_hours` defaults to `24` (`marketplace.py:60`), a setting whose entire premise is a cache that outlives a single call — which this cache never does.

**Failure mode:** (a) the reported `cached_entries` statistic is permanently and misleadingly `0`; (b) the actual cache mechanism cannot ever accumulate hits across calls because its owning object is recreated and discarded every time, making the 24-hour cache duration configuration inert.

**Reproduce/confirm:** grep `_registry_cache` (one match, the `getattr` read); grep `self.cache` and `RegistryClient(` construction sites to confirm the `async with` scoping pattern at `:730,740,806,810`.

---

### D-019 — Marketplace integration stub
**Severity:** LOW
**Evidence:** VERIFIED-BY-READ

`plugin_manager.py:912-916`:
```python
async def get_plugin_marketplace_info(self) -> Dict[str, Any]:
    """..."""
    # This would implement marketplace integration
    pass
```
This method's entire body, after its docstring, is a comment describing intended future behavior followed by `pass`. Note this is the one location in the repository where a comment reads like an acknowledged stub — it does not use `TODO`/`FIXME` markers, which is why the repository-wide marker grep (see Scope section) returns zero hits despite this method being, functionally, exactly that: an unimplemented stub.

**Failure mode:** any caller of `get_plugin_marketplace_info` receives `None` (the implicit return of a function whose body is only `pass`) rather than the `Dict[str, Any]` its signature promises.

**Reproduce/confirm:** read `plugin_manager.py:912-916` directly.

---

## plugin_base.py

### D-020 — Declared-but-unimplemented interfaces
**Severity:** LOW
**Evidence:** VERIFIED-BY-READ

`plugin_base.py:168` declares `class ConsciousnessInterface(ABC)` and `plugin_base.py:211` declares `class NetworkInterface(ABC)`. `PluginBase` (`plugin_base.py:230`) is declared as `class PluginBase(PluginInterface, StateInterface, ABC)` — it inherits only `PluginInterface` and `StateInterface`, not `ConsciousnessInterface` or `NetworkInterface`. A grep of the repository for any other class inheriting from either interface returns no matches.

**Failure mode:** none at runtime — these are simply unused abstract base classes. Their presence signals a designed-but-unbuilt extension point (consciousness-specific and network-specific plugin capabilities) rather than a defect that breaks anything currently working.

**Reproduce/confirm:** read `plugin_base.py:168, 211, 230`; grep repository-wide for `ConsciousnessInterface` and `NetworkInterface` as base classes (only the two declarations themselves appear).

---

### D-021 — Donor API drift partially hand-patched in place
**Severity:** LOW
**Evidence:** VERIFIED-BY-READ

`plugin_base.py:444-465` (memory-context creation calls) shows values that have been edited with the prior values left visible as trailing comments:
```python
memory_type=MemoryType.USER,          # changed from MemoryType.SYSTEM
...
scope=MemoryScope.USER,               # changed from MemoryScope.PLUGIN
```
(pattern repeated at `plugin_base.py:465` for a second `memory_type=MemoryType.USER` assignment). This is evidence that `MemoryType.SYSTEM`/`MemoryScope.PLUGIN` were the original values written against an earlier version of the host-supplied `core.memory_core` API (Section 7 of ARCHITECTURE.md), and were hand-edited to `MemoryType.USER`/`MemoryScope.USER` at some point after the donor API's enum values shifted — without removing the evidence of the prior values.

**Failure mode:** none directly observable from this repository alone — `MemoryType` and `MemoryScope` are host-supplied types (`plugin_base.py:22`) not defined here, so whether `.SYSTEM`/`.PLUGIN` still exist as valid members on the host's actual enum cannot be determined from this repository. The defect is the incomplete repair pattern itself: a partial hand-patch with no accompanying note explaining why, which is a maintenance hazard for the next engineer who does not know whether the remaining `.USER` values are correct or themselves in need of further correction.

**Reproduce/confirm:** read `plugin_base.py:440-466` directly for the comment-preserved prior values.

---

## Cross-Lineage

### D-022 — Manifest schema drift between lineages
**Severity:** HIGH
**Evidence:** VERIFIED-BY-READ

`plugin_manager.py:88-141` — the `PluginManifest` dataclass the only fully-wired loader (`plugin_manager.py:687`, `PluginManifest.from_file`) actually parses at runtime — has no `capabilities` field, no `workflow_nodes` field, no `memory_extensions` field, no `security_level` field, and no resource-limit fields (`memory_limit_mb`, `cpu_limit_percent`). It types `plugin_type` as a `PluginType` enum (`plugin_manager.py:63`) and `permissions` as `List[PluginPermission]` (enum, `plugin_manager.py:75`).

`plugin_base.py:79-136` — the operator-designated canonical `PluginManifest` (pydantic `BaseModel`) — declares all 33 fields including every one of the above, and types `plugin_type` as a bare `str` and `permissions` as a free-form `List[str]`.

**Failure mode:** a `manifest.json` authored against the canonical schema's documented field set (capabilities, workflow_nodes, memory_extensions, security_level, resource limits) will have every one of those fields silently discarded when parsed by the actual loader's dataclass, because Python dataclasses constructed via `**data`-style unpacking against an undeclared field raise `TypeError: unexpected keyword argument` rather than silently ignoring it — meaning a manifest with any canonical-only field present will, if parsed by the `plugin_manager.py:88` dataclass, fail construction outright rather than degrade gracefully. Conversely, a manifest authored strictly against the loader's narrower dataclass schema has no field for `capabilities`/`workflow_nodes`/`memory_extensions`/`security_level` at all, so a plugin author following the canonical (`plugin_base.py`) schema documentation will produce a manifest the real loader cannot construct.

**Reproduce/confirm:** read `plugin_manager.py:88-141` field-by-field against `plugin_base.py:79-136` field-by-field; the field-set difference is directly enumerable from both class bodies with no execution required. See ARCHITECTURE.md Section 9 for the full side-by-side field table and Section 2 (Collision 1) for the type-collision framing.
