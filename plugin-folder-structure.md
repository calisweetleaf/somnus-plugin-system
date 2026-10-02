# Morpheus Chat Plugin Architecture: Folder Structure & Discovery

## Hierarchical Plugin Organization

```
morpheus_plugins/
├── core/ # Plugin management kernel (highest privilege)
│ ├── __init__.py
│ ├── plugin_manager.py # Central orchestrator
│ ├── plugin_base.py # Abstract base classes
│ ├── security.py # Security validation & sandboxing
│ ├── discovery.py # Plugin discovery engine
│ ├── hot_reload.py # Hot-reload mechanism
│ ├── orchestration.py # Plugin workflow management
│ └── marketplace.py # Community integration
│
├── installed/ # User-installed plugins (user-space)
│ ├── example_plugin/
│ │ ├── __init__.py
│ │ ├── plugin.py # Main plugin class (inherits PluginBase)
│ │ ├── manifest.json # Plugin metadata & configuration
│ │ ├── requirements.txt # Python dependencies
│ │ ├── api/ # FastAPI endpoints
│ │ │ ├── __init__.py
│ │ │ ├── routes.py # API route definitions
│ │ │ └── models.py # Pydantic models
│ │ ├── ui/ # Frontend components
│ │ │ ├── components.js # React/vanilla JS components
│ │ │ ├── styles.css # Plugin-specific styling
│ │ │ └── templates/ # HTML templates
│ │ ├── agents/ # Agent action definitions
│ │ │ ├── __init__.py
│ │ │ └── actions.py # Agent-callable functions
│ │ ├── memory/ # Memory extensions
│ │ │ ├── __init__.py
│ │ │ └── extensions.py # Custom memory types/handlers
│ │ ├── workflows/ # Workflow node definitions
│ │ │ ├── __init__.py
│ │ │ └── nodes.py # Workflow processing nodes
│ │ ├── assets/ # Static assets (images, data files)
│ │ ├── tests/ # Plugin unit tests
│ │ ├── docs/ # Plugin documentation
│ │ └── config/ # Configuration files
│
├── community/ # Community/marketplace plugins
│ ├── verified/ # Cryptographically signed plugins
│ ├── experimental/ # Community contributions
│ └── featured/ # Curated high-quality plugins
│
├── templates/ # Plugin development templates
│ ├── basic_plugin/ # Minimal plugin template
│ ├── api_extension/ # API-focused plugin template
│ ├── ui_component/ # UI-focused plugin template
│ ├── agent_action/ # Agent action plugin template
│ └── workflow_node/ # Workflow node plugin template
│
├── sandbox/ # Isolated execution environments
│ ├── untrusted/ # Sandboxed execution for untrusted plugins
│ └── temp/ # Temporary plugin loading space
│
└── cache/ # Plugin caching and optimization
    ├── compiled/ # Compiled plugin bytecode
    ├── signatures/ # Cryptographic signature cache
    └── dependencies/ # Resolved dependency cache
```

## Dynamic Discovery Mechanism

The discovery system operates through multiple scanning strategies:

### 1. File System Scanning

- **Recursive directory traversal** with manifest.json detection
- **Inotify/ReadDirectoryChangesW** for real-time file system monitoring
- **Debounced change detection** to prevent reload storms during development

### 2. Manifest-Based Registration

```json
{
  "name": "example_plugin",
  "version": "1.0.0",
  "api_version": "1.0",
  "description": "Example plugin demonstrating core functionality",
  "author": "Plugin Developer",
  "homepage": "https://github.com/developer/example-plugin",
  "repository": "https://github.com/developer/example-plugin.git",
  "license": "MIT",
  
  "plugin_type": "api_extension",
  "morpheus_version_min": "1.0.0",
  "morpheus_version_max": "2.0.0",
  "python_version_min": "3.11",
  
  "dependencies": [
    "requests>=2.28.0",
    "pydantic>=2.0.0"
  ],
  
  "permissions": [
    "read_memory",
    "write_memory", 
    "network_access",
    "user_interface"
  ],
  
  "api_endpoints": [
    "/process_data",
    "/get_status",
    "/configure"
  ],
  
  "ui_components": [
    "SettingsPanel",
    "StatusWidget"
  ],
  
  "agent_actions": [
    "custom_research",
    "data_transformation"
  ],
  
  "workflow_nodes": [
    "DataProcessor",
    "ContentGenerator"
  ],
  
  "memory_extensions": [
    "CustomMemoryType",
    "SpecializedRetrieval"
  ],
  
  "trusted": false,
  "signature": "sha256:abcd1234...",
  "tags": ["research", "data-processing", "ai-tools"]
}
```

### 3. Registration Process

1. **Manifest Validation**: Schema validation, version compatibility checking
2. **Security Analysis**: Code scanning, dependency analysis, signature verification
3. **Dependency Resolution**: Automatic dependency installation with version conflict detection
4. **Capability Registration**: API endpoints, UI components, agent actions catalogued
5. **Integration Validation**: Compatibility testing with existing plugins and core system

### 4. Multi-Source Discovery

- **Local Discovery**: Installed and user-developed plugins
- **Community Discovery**: Marketplace and repository scanning
- **Network Discovery**: Distributed plugin registries (future enhancement)
- **Version Management**: Multiple versions, rollback capabilities

## Discovery Engine Implementation

The discovery engine implements sophisticated caching and indexing:

### Plugin Index Structure

```json
{
  "plugin_id": {
    "manifest": PluginManifest,
    "path": Path,
    "status": PluginStatus,
    "dependencies": List[str],
    "dependents": List[str], # Plugins that depend on this one
    "compatibility_matrix": Dict[str, bool],
    "performance_metrics": Dict[str, float],
    "last_scanned": datetime,
    "hash": str # Content hash for change detection
  }
}
```

### Change Detection Algorithm

1. **Content Hashing**: SHA-256 hashes of plugin files for change detection
2. **Dependency Tracking**: Graph-based dependency change propagation
3. **Selective Reloading**: Only reload affected plugins and their dependents
4. **State Preservation**: Maintain plugin state across reloads where possible

This architecture ensures that plugin discovery is both comprehensive and efficient, supporting rapid development cycles while maintaining system stability and security.
