"""
MORPHEUS CHAT - Plugin Discovery Engine
Advanced plugin detection, indexing, and dependency resolution with real-time monitoring.
"""

import asyncio
import hashlib
import json
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
import logging
import fnmatch
import importlib.util
import sys

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

from plugin_base import PluginManifest, PluginCapability

logger = logging.getLogger(__name__)


@dataclass
class PluginIndex:
    """Comprehensive plugin index entry"""
    plugin_id: str
    manifest: PluginManifest
    path: Path
    hash: str
    last_scanned: datetime
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    compatibility_score: float = 1.0
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    discovery_source: str = "filesystem"
    tags: Set[str] = field(default_factory=set)


@dataclass
class DependencyNode:
    """Dependency graph node"""
    plugin_id: str
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    depth: int = 0
    circular_deps: Set[str] = field(default_factory=set)


class DiscoverySource:
    """Plugin discovery source types"""
    FILESYSTEM = "filesystem"
    MARKETPLACE = "marketplace"
    REPOSITORY = "repository"
    NETWORK = "network"
    CACHE = "cache"


class PluginFileWatcher(FileSystemEventHandler):
    """Real-time file system monitoring for plugin changes"""
    
    def __init__(self, discovery_engine: 'PluginDiscovery'):
        self.discovery_engine = discovery_engine
        self.debounce_delay = 1.0
        self.pending_scans: Dict[str, asyncio.Task] = {}
        
    def on_any_event(self, event):
        """Handle any file system event"""
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        
        # Only process relevant files
        if self._is_relevant_file(path):
            plugin_dir = self._find_plugin_directory(path)
            if plugin_dir:
                self._schedule_scan(plugin_dir)
    
    def _is_relevant_file(self, path: Path) -> bool:
        """Check if file is relevant for plugin discovery"""
        relevant_extensions = {'.py', '.json', '.yaml', '.yml', '.txt', '.md'}
        relevant_names = {'manifest.json', 'requirements.txt', '__init__.py', 'plugin.py'}
        
        return (
            path.suffix.lower() in relevant_extensions or
            path.name in relevant_names or
            'plugin' in path.name.lower()
        )
    
    def _find_plugin_directory(self, path: Path) -> Optional[Path]:
        """Find the plugin directory containing this file"""
        current = path.parent
        
        while current != current.parent:
            manifest_path = current / 'manifest.json'
            if manifest_path.exists():
                return current
            current = current.parent
        
        return None
    
    def _schedule_scan(self, plugin_dir: Path):
        """Schedule plugin directory scan with debouncing"""
        plugin_id = plugin_dir.name
        
        # Cancel existing scan
        if plugin_id in self.pending_scans:
            self.pending_scans[plugin_id].cancel()
        
        # Schedule new scan
        async def delayed_scan():
            await asyncio.sleep(self.debounce_delay)
            try:
                await self.discovery_engine.scan_plugin_directory(plugin_dir)
                logger.debug(f"Rescanned plugin directory: {plugin_dir}")
            except Exception as e:
                logger.error(f"Failed to rescan plugin directory {plugin_dir}: {e}")
            finally:
                self.pending_scans.pop(plugin_id, None)
        
        self.pending_scans[plugin_id] = asyncio.create_task(delayed_scan())


class DependencyResolver:
    """Advanced dependency resolution with circular detection and optimization"""
    
    def __init__(self):
        self.dependency_graph: Dict[str, DependencyNode] = {}
        self.resolution_cache: Dict[str, List[str]] = {}
        
    def add_plugin(self, plugin_id: str, dependencies: Set[str]):
        """Add plugin to dependency graph"""
        if plugin_id not in self.dependency_graph:
            self.dependency_graph[plugin_id] = DependencyNode(plugin_id)
        
        node = self.dependency_graph[plugin_id]
        node.dependencies = dependencies.copy()
        
        # Update dependents
        for dep_id in dependencies:
            if dep_id not in self.dependency_graph:
                self.dependency_graph[dep_id] = DependencyNode(dep_id)
            self.dependency_graph[dep_id].dependents.add(plugin_id)
        
        # Invalidate cache
        self._invalidate_cache()
    
    def remove_plugin(self, plugin_id: str):
        """Remove plugin from dependency graph"""
        if plugin_id not in self.dependency_graph:
            return
        
        node = self.dependency_graph[plugin_id]
        
        # Remove from dependents
        for dep_id in node.dependencies:
            if dep_id in self.dependency_graph:
                self.dependency_graph[dep_id].dependents.discard(plugin_id)
        
        # Remove from dependencies
        for dependent_id in node.dependents:
            if dependent_id in self.dependency_graph:
                self.dependency_graph[dependent_id].dependencies.discard(plugin_id)
        
        del self.dependency_graph[plugin_id]
        self._invalidate_cache()
    
    def get_load_order(self, plugin_ids: Set[str]) -> List[str]:
        """Get optimal load order for plugins with dependency resolution"""
        cache_key = '|'.join(sorted(plugin_ids))
        if cache_key in self.resolution_cache:
            return self.resolution_cache[cache_key]
        
        # Detect circular dependencies
        cycles = self._detect_cycles(plugin_ids)
        if cycles:
            logger.warning(f"Circular dependencies detected: {cycles}")
            # Break cycles by removing least important dependencies
            self._break_cycles(cycles)
        
        # Topological sort
        load_order = self._topological_sort(plugin_ids)
        
        self.resolution_cache[cache_key] = load_order
        return load_order
    
    def get_unload_order(self, plugin_ids: Set[str]) -> List[str]:
        """Get optimal unload order (reverse of load order)"""
        load_order = self.get_load_order(plugin_ids)
        return list(reversed(load_order))
    
    def get_all_dependencies(self, plugin_id: str) -> Set[str]:
        """Get all transitive dependencies for a plugin"""
        dependencies = set()
        to_process = deque([plugin_id])
        processed = set()
        
        while to_process:
            current_id = to_process.popleft()
            if current_id in processed:
                continue
            
            processed.add(current_id)
            
            if current_id in self.dependency_graph:
                node_deps = self.dependency_graph[current_id].dependencies
                dependencies.update(node_deps)
                to_process.extend(node_deps)
        
        return dependencies
    
    def get_all_dependents(self, plugin_id: str) -> Set[str]:
        """Get all transitive dependents for a plugin"""
        dependents = set()
        to_process = deque([plugin_id])
        processed = set()
        
        while to_process:
            current_id = to_process.popleft()
            if current_id in processed:
                continue
            
            processed.add(current_id)
            
            if current_id in self.dependency_graph:
                node_deps = self.dependency_graph[current_id].dependents
                dependents.update(node_deps)
                to_process.extend(node_deps)
        
        return dependents
    
    def _detect_cycles(self, plugin_ids: Set[str]) -> List[List[str]]:
        """Detect circular dependencies using DFS"""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node_id: str) -> bool:
            if node_id in rec_stack:
                # Found cycle
                cycle_start = path.index(node_id)
                cycle = path[cycle_start:] + [node_id]
                cycles.append(cycle)
                return True
            
            if node_id in visited:
                return False
            
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            if node_id in self.dependency_graph:
                for dep_id in self.dependency_graph[node_id].dependencies:
                    if dep_id in plugin_ids and dfs(dep_id):
                        pass  # Continue to find all cycles
            
            rec_stack.remove(node_id)
            path.pop()
            return False
        
        for plugin_id in plugin_ids:
            if plugin_id not in visited:
                dfs(plugin_id)
        
        return cycles
    
    def _break_cycles(self, cycles: List[List[str]]):
        """Break circular dependencies by removing edges"""
        for cycle in cycles:
            # Remove the edge with lowest priority
            min_priority = float('inf')
            edge_to_remove = None
            
            for i in range(len(cycle) - 1):
                from_id, to_id = cycle[i], cycle[i + 1]
                priority = self._get_dependency_priority(from_id, to_id)
                
                if priority < min_priority:
                    min_priority = priority
                    edge_to_remove = (from_id, to_id)
            
            if edge_to_remove:
                from_id, to_id = edge_to_remove
                self.dependency_graph[from_id].dependencies.discard(to_id)
                self.dependency_graph[to_id].dependents.discard(from_id)
                logger.info(f"Broke circular dependency: {from_id} -> {to_id}")
    
    def _get_dependency_priority(self, from_id: str, to_id: str) -> float:
        """Get priority score for dependency (lower = less important)"""
        # Simple heuristic: prefer keeping dependencies to plugins with more dependents
        to_node = self.dependency_graph.get(to_id)
        if to_node:
            return len(to_node.dependents)
        return 0.0
    
    def _topological_sort(self, plugin_ids: Set[str]) -> List[str]:
        """Perform topological sort of plugins"""
        in_degree = {}
        queue = deque()
        result = []
        
        # Calculate in-degrees
        for plugin_id in plugin_ids:
            in_degree[plugin_id] = 0
        
        for plugin_id in plugin_ids:
            if plugin_id in self.dependency_graph:
                for dep_id in self.dependency_graph[plugin_id].dependencies:
                    if dep_id in plugin_ids:
                        in_degree[plugin_id] += 1
        
        # Find nodes with no incoming edges
        for plugin_id, degree in in_degree.items():
            if degree == 0:
                queue.append(plugin_id)
        
        # Process queue
        while queue:
            current_id = queue.popleft()
            result.append(current_id)
            
            if current_id in self.dependency_graph:
                for dependent_id in self.dependency_graph[current_id].dependents:
                    if dependent_id in plugin_ids:
                        in_degree[dependent_id] -= 1
                        if in_degree[dependent_id] == 0:
                            queue.append(dependent_id)
        
        # Check for remaining cycles
        if len(result) != len(plugin_ids):
            remaining = plugin_ids - set(result)
            logger.error(f"Topological sort incomplete, remaining plugins: {remaining}")
            result.extend(remaining)  # Add remaining in arbitrary order
        
        return result
    
    def _invalidate_cache(self):
        """Invalidate resolution cache"""
        self.resolution_cache.clear()


class PluginCompatibilityChecker:
    """Check plugin compatibility and generate compatibility scores"""
    
    def __init__(self):
        self.version_cache: Dict[str, str] = {}
        
    def check_compatibility(self, plugin: PluginManifest, system_info: Dict[str, Any]) -> Tuple[bool, float, List[str]]:
        """Check plugin compatibility with system"""
        issues = []
        score = 1.0
        compatible = True
        
        # Check Morpheus version compatibility
        morpheus_version = system_info.get('morpheus_version', '1.0.0')
        if not self._version_in_range(morpheus_version, plugin.morpheus_version_min, plugin.morpheus_version_max):
            compatible = False
            score *= 0.0
            issues.append(f"Morpheus version {morpheus_version} not in range {plugin.morpheus_version_min}-{plugin.morpheus_version_max}")
        
        # Check Python version compatibility
        python_version = system_info.get('python_version', sys.version.split()[0])
        if not self._version_compatible(python_version, plugin.python_version_min):
            compatible = False
            score *= 0.0
            issues.append(f"Python version {python_version} below minimum {plugin.python_version_min}")
        
        # Check capability requirements
        system_capabilities = set(system_info.get('capabilities', []))
        required_caps = set(plugin.capabilities)
        missing_caps = required_caps - system_capabilities
        
        if missing_caps:
            score *= max(0.1, 1.0 - len(missing_caps) / max(len(required_caps), 1))
            issues.append(f"Missing capabilities: {missing_caps}")
        
        # Check resource requirements
        available_memory = system_info.get('available_memory_mb', 0)
        if plugin.memory_limit_mb > available_memory:
            score *= 0.5
            issues.append(f"Insufficient memory: need {plugin.memory_limit_mb}MB, have {available_memory}MB")
        
        # Check security level compatibility
        system_security_level = system_info.get('security_level', 3)
        if plugin.security_level > system_security_level:
            score *= 0.7
            issues.append(f"Security level mismatch: plugin needs {plugin.security_level}, system has {system_security_level}")
        
        return compatible, score, issues
    
    def _version_in_range(self, version: str, min_version: str, max_version: str) -> bool:
        """Check if version is within range"""
        return (self._version_compatible(version, min_version) and 
                self._version_compatible(max_version, version))
    
    def _version_compatible(self, version: str, min_version: str) -> bool:
        """Check if version meets minimum requirement"""
        try:
            v_parts = [int(x) for x in version.split('.')]
            min_parts = [int(x) for x in min_version.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(v_parts), len(min_parts))
            v_parts.extend([0] * (max_len - len(v_parts)))
            min_parts.extend([0] * (max_len - len(min_parts)))
            
            return v_parts >= min_parts
        except (ValueError, AttributeError):
            return False


class PluginScanner:
    """Efficient plugin directory scanning with caching"""
    
    def __init__(self):
        self.scan_cache: Dict[str, Tuple[float, PluginIndex]] = {}
        self.ignore_patterns = {
            '__pycache__', '*.pyc', '*.pyo', '.git', '.svn', '.hg',
            'node_modules', '.venv', 'venv', '.env', 'test', 'tests'
        }
        
    async def scan_directory(self, directory: Path, source: str = DiscoverySource.FILESYSTEM) -> Dict[str, PluginIndex]:
        """Scan directory for plugins with intelligent caching"""
        plugins = {}
        
        if not directory.exists() or not directory.is_dir():
            return plugins
        
        # Find potential plugin directories
        plugin_dirs = await self._find_plugin_directories(directory)
        
        # Scan each plugin directory
        scan_tasks = []
        for plugin_dir in plugin_dirs:
            scan_tasks.append(self._scan_plugin_directory(plugin_dir, source))
        
        if scan_tasks:
            results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Plugin scan failed: {result}")
                elif result:
                    plugins[result.plugin_id] = result
        
        return plugins
    
    async def _find_plugin_directories(self, root_directory: Path) -> List[Path]:
        """Find directories that might contain plugins"""
        plugin_dirs = []
        
        async def scan_recursive(directory: Path, depth: int = 0):
            if depth > 3:  # Limit recursion depth
                return
            
            try:
                for item in directory.iterdir():
                    if item.is_dir() and not self._should_ignore(item):
                        # Check if this directory contains a manifest
                        manifest_path = item / 'manifest.json'
                        if manifest_path.exists():
                            plugin_dirs.append(item)
                        else:
                            # Recurse into subdirectories
                            await scan_recursive(item, depth + 1)
            except (PermissionError, OSError) as e:
                logger.debug(f"Cannot scan directory {directory}: {e}")
        
        await scan_recursive(root_directory)
        return plugin_dirs
    
    async def _scan_plugin_directory(self, plugin_dir: Path, source: str) -> Optional[PluginIndex]:
        """Scan individual plugin directory"""
        manifest_path = plugin_dir / 'manifest.json'
        
        if not manifest_path.exists():
            return None
        
        try:
            # Check cache first
            cache_key = str(plugin_dir)
            dir_mtime = plugin_dir.stat().st_mtime
            
            if cache_key in self.scan_cache:
                cached_mtime, cached_index = self.scan_cache[cache_key]
                if cached_mtime >= dir_mtime:
                    return cached_index
            
            # Load and validate manifest
            async with open(manifest_path, 'r') as f:
                manifest_data = json.loads(await f.read())
            
            manifest = PluginManifest(**manifest_data)
            
            # Calculate directory hash
            dir_hash = await self._calculate_directory_hash(plugin_dir)
            
            # Extract dependencies
            dependencies = set(manifest.plugin_dependencies)
            
            # Generate tags
            tags = set(manifest.tags)
            if manifest.plugin_type:
                tags.add(manifest.plugin_type)
            
            # Create index entry
            index = PluginIndex(
                plugin_id=manifest.name,
                manifest=manifest,
                path=plugin_dir,
                hash=dir_hash,
                last_scanned=datetime.now(timezone.utc),
                dependencies=dependencies,
                discovery_source=source,
                tags=tags
            )
            
            # Cache result
            self.scan_cache[cache_key] = (dir_mtime, index)
            
            return index
            
        except Exception as e:
            logger.error(f"Failed to scan plugin directory {plugin_dir}: {e}")
            return None
    
    async def _calculate_directory_hash(self, directory: Path) -> str:
        """Calculate hash of directory contents for change detection"""
        hasher = hashlib.sha256()
        
        # Sort files for deterministic hash
        all_files = []
        for item in directory.rglob('*'):
            if item.is_file() and not self._should_ignore(item):
                all_files.append(item)
        
        all_files.sort()
        
        for file_path in all_files:
            try:
                # Add file path relative to plugin directory
                rel_path = file_path.relative_to(directory)
                hasher.update(str(rel_path).encode())
                
                # Add file modification time
                hasher.update(str(file_path.stat().st_mtime).encode())
                
                # For small files, add content
                if file_path.stat().st_size < 10240:  # 10KB
                    async with open(file_path, 'rb') as f:
                        content = await f.read()
                    hasher.update(content)
                
            except (OSError, IOError):
                continue
        
        return hasher.hexdigest()
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored during scanning"""
        name = path.name
        
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        
        return name.startswith('.')


class PluginDiscovery:
    """Advanced plugin discovery engine with multi-source support and real-time monitoring"""
    
    def __init__(self, plugin_base_dir: Path):
        self.plugin_base_dir = plugin_base_dir
        self.plugin_index: Dict[str, PluginIndex] = {}
        self.dependency_resolver = DependencyResolver()
        self.compatibility_checker = PluginCompatibilityChecker()
        self.scanner = PluginScanner()
        
        # File system monitoring
        self.file_watcher = PluginFileWatcher(self)
        self.observer: Optional[Observer] = None
        
        # Discovery sources
        self.discovery_sources = {
            DiscoverySource.FILESYSTEM: plugin_base_dir / 'installed',
            DiscoverySource.MARKETPLACE: plugin_base_dir / 'community',
            DiscoverySource.CACHE: plugin_base_dir / 'cache'
        }
        
        # System information for compatibility checking
        self.system_info = {
            'morpheus_version': '1.0.0',
            'python_version': sys.version.split()[0],
            'capabilities': [cap.value for cap in PluginCapability],
            'available_memory_mb': 4096,
            'security_level': 3
        }
        
        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()
        
    async def start_monitoring(self):
        """Start real-time file system monitoring"""
        try:
            self.observer = Observer()
            
            for source_name, source_path in self.discovery_sources.items():
                if source_path.exists():
                    self.observer.schedule(
                        self.file_watcher,
                        str(source_path),
                        recursive=True
                    )
                    logger.info(f"Started monitoring {source_name} at {source_path}")
            
            self.observer.start()
            
            # Schedule periodic full scans
            periodic_scan_task = asyncio.create_task(self._periodic_scan())
            self.background_tasks.add(periodic_scan_task)
            
        except Exception as e:
            logger.error(f"Failed to start plugin monitoring: {e}")
    
    async def stop_monitoring(self):
        """Stop file system monitoring"""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        self.background_tasks.clear()
    
    async def discover_plugins(self) -> Dict[str, PluginManifest]:
        """Discover all plugins from all sources"""
        discovered_plugins = {}
        
        # Scan all discovery sources
        for source_name, source_path in self.discovery_sources.items():
            try:
                source_plugins = await self.scanner.scan_directory(source_path, source_name)
                
                for plugin_id, plugin_index in source_plugins.items():
                    # Check compatibility
                    compatible, score, issues = self.compatibility_checker.check_compatibility(
                        plugin_index.manifest, self.system_info
                    )
                    
                    plugin_index.compatibility_score = score
                    
                    if compatible or score > 0.5:  # Include partially compatible plugins
                        self.plugin_index[plugin_id] = plugin_index
                        discovered_plugins[plugin_id] = plugin_index.manifest
                        
                        # Update dependency graph
                        self.dependency_resolver.add_plugin(plugin_id, plugin_index.dependencies)
                        
                        if issues:
                            logger.warning(f"Plugin {plugin_id} compatibility issues: {issues}")
                    else:
                        logger.info(f"Plugin {plugin_id} incompatible (score: {score:.2f}): {issues}")
                
                logger.info(f"Discovered {len(source_plugins)} plugins from {source_name}")
                
            except Exception as e:
                logger.error(f"Failed to scan {source_name} at {source_path}: {e}")
        
        logger.info(f"Total discovered plugins: {len(discovered_plugins)}")
        return discovered_plugins
    
    async def scan_plugin_directory(self, plugin_dir: Path) -> Optional[PluginIndex]:
        """Scan specific plugin directory"""
        return await self.scanner._scan_plugin_directory(plugin_dir, DiscoverySource.FILESYSTEM)
    
    async def refresh_cache(self):
        """Refresh plugin discovery cache"""
        logger.info("Refreshing plugin discovery cache")
        
        # Clear cache
        self.plugin_index.clear()
        self.dependency_resolver = DependencyResolver()
        self.scanner.scan_cache.clear()
        
        # Rediscover plugins
        await self.discover_plugins()
    
    def get_plugin_path(self, plugin_id: str) -> Optional[Path]:
        """Get path to plugin directory"""
        plugin_index = self.plugin_index.get(plugin_id)
        return plugin_index.path if plugin_index else None
    
    def get_plugin_manifest(self, plugin_id: str) -> Optional[PluginManifest]:
        """Get plugin manifest"""
        plugin_index = self.plugin_index.get(plugin_id)
        return plugin_index.manifest if plugin_index else None
    
    def get_plugin_dependencies(self, plugin_id: str) -> Set[str]:
        """Get plugin dependencies"""
        return self.dependency_resolver.get_all_dependencies(plugin_id)
    
    def get_plugin_dependents(self, plugin_id: str) -> Set[str]:
        """Get plugins that depend on this plugin"""
        return self.dependency_resolver.get_all_dependents(plugin_id)
    
    def get_load_order(self, plugin_ids: Set[str]) -> List[str]:
        """Get optimal load order for plugins"""
        return self.dependency_resolver.get_load_order(plugin_ids)
    
    def get_unload_order(self, plugin_ids: Set[str]) -> List[str]:
        """Get optimal unload order for plugins"""
        return self.dependency_resolver.get_unload_order(plugin_ids)
    
    def search_plugins(self, 
                      query: str = "", 
                      plugin_type: Optional[str] = None,
                      tags: Optional[Set[str]] = None,
                      capabilities: Optional[Set[PluginCapability]] = None) -> List[PluginIndex]:
        """Search plugins with filtering"""
        results = []
        
        for plugin_index in self.plugin_index.values():
            # Text search
            if query:
                searchable_text = f"{plugin_index.manifest.name} {plugin_index.manifest.description} {plugin_index.manifest.author}".lower()
                if query.lower() not in searchable_text:
                    continue
            
            # Type filter
            if plugin_type and plugin_index.manifest.plugin_type != plugin_type:
                continue
            
            # Tags filter
            if tags and not tags.intersection(plugin_index.tags):
                continue
            
            # Capabilities filter
            if capabilities:
                plugin_caps = set(plugin_index.manifest.capabilities)
                if not capabilities.intersection(plugin_caps):
                    continue
            
            results.append(plugin_index)
        
        # Sort by compatibility score
        results.sort(key=lambda x: x.compatibility_score, reverse=True)
        return results
    
    def get_plugin_statistics(self) -> Dict[str, Any]:
        """Get discovery statistics"""
        stats = {
            'total_plugins': len(self.plugin_index),
            'by_source': defaultdict(int),
            'by_type': defaultdict(int),
            'by_compatibility': {
                'compatible': 0,
                'partially_compatible': 0,
                'incompatible': 0
            },
            'dependency_stats': {
                'plugins_with_deps': 0,
                'total_dependencies': 0,
                'circular_dependencies': len(self.dependency_resolver._detect_cycles(set(self.plugin_index.keys())))
            }
        }
        
        for plugin_index in self.plugin_index.values():
            stats['by_source'][plugin_index.discovery_source] += 1
            stats['by_type'][plugin_index.manifest.plugin_type] += 1
            
            if plugin_index.compatibility_score >= 1.0:
                stats['by_compatibility']['compatible'] += 1
            elif plugin_index.compatibility_score >= 0.5:
                stats['by_compatibility']['partially_compatible'] += 1
            else:
                stats['by_compatibility']['incompatible'] += 1
            
            if plugin_index.dependencies:
                stats['dependency_stats']['plugins_with_deps'] += 1
                stats['dependency_stats']['total_dependencies'] += len(plugin_index.dependencies)
        
        return stats
    
    async def _periodic_scan(self):
        """Periodic full scan for plugin changes"""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                
                # Check for changes since last scan
                changes_detected = False
                
                for plugin_id, plugin_index in list(self.plugin_index.items()):
                    try:
                        current_hash = await self.scanner._calculate_directory_hash(plugin_index.path)
                        if current_hash != plugin_index.hash:
                            changes_detected = True
                            logger.info(f"Changes detected in plugin {plugin_id}")
                            break
                    except Exception:
                        continue
                
                if changes_detected:
                    await self.refresh_cache()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic scan error: {e}")
                await asyncio.sleep(60)  # Wait before retrying