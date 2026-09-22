# Reference plugin load

Passed 8/8.

- PASS no zero-byte files: empty=[]
- PASS manifest validates: name=somnus_reference version=1.0.0 type=api_extension
- PASS Plugin subclasses canonical PluginBase: class=Plugin
- PASS router exports three distinct paths: paths=['/checkpoint', '/contract', '/lifecycle']
- PASS loader activates the reference plugin: loaded=True state=PluginState.ACTIVE
- PASS contract route returns the manifest identity: status=200 body={'plugin_id': 'somnus_reference', 'name': 'somnus_reference', 'version': '1.0.0', 'plugin_type': 'api_extension', 'permissions': ['read_memory', 'write_memory', 'user_interface'], 'capabilities': ['memory_integration', 'consciousness_access', 'real_time_adaptation'], 'api_endpoints': ['/contract', '/lifecycle', '/checkpoint'], 'agent_actions': ['describe_contract', 'record_observation'], 'workflow_nodes': ['reference.observe'], 'memory_extensions': ['user_checkpoint'], 'network_access_required': False, 'state': 'active', 'coherence': 1.0}
- PASS lifecycle route is not the contract route: status=200 body={'plugin_id': 'somnus_reference', 'state': 'active', 'ledger': ['initialize', 'activate'], 'actions': ['describe_contract', 'record_observation'], 'nodes': [{'node_id': 'reference.observe', 'plugin_method': 'record_observation', 'inputs': ['note'], 'outputs': ['observation']}], 'checkpoint_kind': 'user_checkpoint'}
- PASS checkpoint route stores a user-scoped host memory: status=200 checkpoint=ckpt_fdcc342f37b63d2b_1 memory_type=user
