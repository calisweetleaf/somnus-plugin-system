# Defect closure proof

Generated: 2026-09-22T08:01:45.821387+00:00

Passed 38 of 38.

| Defect | Check | Result | Detail |
|---|---|---|---|
| D-021 | checkpoint memory classification is explicit | PASS | MemoryType.USER is the checkpoint classification |
| D-022 | each collided class has one definition | PASS | {'PluginManifest': 1, 'PluginBase': 1, 'PluginDiscovery': 1, 'PluginFileWatcher': 1} |
| D-022 | plugin_manager.PluginBase is plugin_base.PluginBase | PASS | plugin_base.PluginBase |
| D-022 | manager re-exports the canonical base | PASS | identity held |
| D-001 | priority drain | PASS | dequeued ['rt', 'normal', 'low'] |
| D-014 | remove inconsistency is visible and successful | PASS | remove returned True |
| D-005 | CryptographicValidator verifies RSA-PSS | PASS | verified=True |
| D-002 | ThreadPoolExecutor shutdown accepts no timeout | PASS | ok=True |
| D-003 | zip-slip member is refused before write | PASS | raised=True escaped=[] |
| D-019 | archive install loads a canonical plugin | PASS | installed=True type=Plugin |
| D-022 | loader kept canonical manifest fields | PASS | fields=dict_keys(['name', 'version', 'description', 'author', 'plugin_type', 'capabilities', 'consciousness_level_required', 'recursive_depth_limit', 'quantum_coherence_required', 'morpheus_version_min', 'morpheus_version_max', 'python_version_min', 'dependencies', 'plugin_dependencies', 'permissions', 'trusted', 'signature', 'security_level', 'api_endpoints', 'ui_components', 'agent_actions', 'workflow_nodes', 'memory_extensions', 'memory_limit_mb', 'cpu_limit_percent', 'network_access_required', 'file_system_access', 'tags', 'license', 'homepage', 'repository', 'documentation']) |
| D-019 | marketplace info is a real inventory | PASS | active=1 keys=['active_count', 'discovered', 'installed', 'network_enabled', 'publisher_keys'] |
| SEC-10 | bad signature does not pass | PASS | valid=False issues=['Invalid cryptographic signature'] |
| D-011 | memory measurement is non-zero | PASS | success=True memory_used=4MB cpu=25.22 |
| D-011 | cpu measurement is non-zero | PASS | success=True cpu=25.0 memory_used=1 |
| D-011 | manifest budget blocks the next call | PASS | precheck_ok=False violations=['Memory usage 4MB exceeds manifest limit 1MB', 'CPU usage 25.0% exceeds manifest limit 1.0%'] manifest_id=139842971487680 live_same=True limits=1/1.0 live_limits=1/1.0 usage={'loaderproof': 4}/{'loaderproof': 25.0} success=False error=Resource limits exceeded: ['Memory usage 4MB exceeds manifest limit 1MB', 'CPU usage 25.0% exceeds manifest limit 1.0%'] |
| D-012 | canonical metrics recorded | PASS | execution_count=2 |
| D-013 | forty concurrent requests all complete | PASS | 40/40 completed |
| D-009 | seeded reactive event ran its handler | PASS | state=WorkflowState.COMPLETED later={'plugin': 'loaderproof', 'event': {'name': 'alarm', 'payload': {'kind': 'seed'}}} |
| D-009 | dispatch_event invokes the registered handler | PASS | fired=1 |
| D-010 | independent graph steps overlap | PASS | elapsed=0.469s overlap=True |
| D-010 | cyclic graph fails with a cycle diagnostic | PASS | state=WorkflowState.FAILED errors=["Cyclic dependency: [['b', 'a', 'b']]"] |
| D-002 | orchestrator stop | PASS | PluginOrchestrator.stop completed |
| D-006 | create_marketplace registers no placeholder key | PASS | keys=['proof-author'] |
| D-006 | placeholder PEM is refused | PASS | refused=True |
| D-018 | registry cache survives the client | PASS | cached=1 |
| D-016 | default network path is off and hostless | PASS | network=False |
| D-015 | community provider selects community_registry_url | PASS | https://registry.example.invalid/community |
| D-004 | RSA-PSS install verifies and loads | PASS | success=True message=Installation completed successfully |
| D-005 | verify_developer_signature accepted the artifact | PASS | Installation completed successfully |
| D-017 | install did not trust a server-asserted score | PASS | local signature score cleared the floor; server trust was not an input |
| D-004 | missing signature fails closed | PASS | verify_download=False |
| D-004 | sha256 checksum is not a signature | PASS | verify_download=False |
| D-007 | malformed hex and cryptographic mismatch are distinct | PASS | Signature for proof-author is not hexadecimal \| RSA-PSS signature mismatch for developer proof-author |
| D-008 | streaming download stops past the byte cap | PASS | downloaded=False exists=False |
| D-020 | consciousness interface is operational | PASS | coherence=0.96 depth=0 |
| D-020 | in-process peer delivery | PASS | delivered=True inbox=1 |
| D-020 | network permission is enforced | PASS | denied=True |
