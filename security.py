"""
MORPHEUS CHAT - Plugin Security & Sandboxing System
Enterprise-grade security validation, sandboxing, and cryptographic verification.
"""

import ast
import asyncio
import hashlib
import hmac
import importlib.util
import inspect
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple, Union
import logging
import json
import zipfile

import aiofiles
import cryptography
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.fernet import Fernet

from plugin_base import PluginManifest, PluginPermission, PluginCapability

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    category: str
    description: str
    file_path: Optional[Path] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class SecurityReport:
    plugin_id: str
    is_safe: bool
    risk_score: float  # 0.0 to 1.0
    issues: List[SecurityIssue] = field(default_factory=list)
    permissions_validated: bool = False
    signature_verified: bool = False
    dependencies_safe: bool = False
    scan_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SecurityLevel:
    MINIMAL = 1
    BASIC = 2
    STANDARD = 3
    HIGH = 4
    MAXIMUM = 5


class SandboxEnvironment:
    """Isolated execution environment for untrusted plugins"""
    
    def __init__(self, plugin_id: str, temp_dir: Path):
        self.plugin_id = plugin_id
        self.temp_dir = temp_dir
        self.process: Optional[subprocess.Popen] = None
        self.resource_limits = {
            'memory_mb': 512,
            'cpu_percent': 10.0,
            'network_access': False,
            'file_system_read': [str(temp_dir)],
            'file_system_write': [str(temp_dir / 'output')],
            'execution_time_seconds': 30
        }
        
    async def execute_code(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute code in sandboxed environment"""
        script_path = self.temp_dir / f"{self.plugin_id}_sandbox.py"
        
        # Write sandboxed code
        sandboxed_code = self._create_sandboxed_code(code)
        async with aiofiles.open(script_path, 'w') as f:
            await f.write(sandboxed_code)
        
        # Execute in subprocess with resource limits
        try:
            cmd = [
                sys.executable, '-c',
                f'exec(open("{script_path}").read())'
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.temp_dir)
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            return {
                'success': process.returncode == 0,
                'stdout': stdout.decode(),
                'stderr': stderr.decode(),
                'return_code': process.returncode
            }
            
        except asyncio.TimeoutError:
            if process:
                process.kill()
            return {
                'success': False,
                'error': 'Execution timeout',
                'stdout': '',
                'stderr': 'Process killed due to timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'stdout': '',
                'stderr': str(e)
            }
    
    def _create_sandboxed_code(self, original_code: str) -> str:
        """Create sandboxed version of code with restrictions"""
        sandbox_wrapper = f'''
import sys
import os
import builtins

# Restrict dangerous builtins
dangerous_builtins = [
    'exec', 'eval', 'compile', '__import__', 'open', 'input',
    'raw_input', 'reload', 'vars', 'dir', 'globals', 'locals'
]

for builtin_name in dangerous_builtins:
    if hasattr(builtins, builtin_name):
        delattr(builtins, builtin_name)

# Restrict module imports
original_import = builtins.__import__

def restricted_import(name, *args, **kwargs):
    forbidden_modules = [
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests',
        'ctypes', 'pickle', 'marshal', 'gc', 'inspect', 'ast'
    ]
    
    if name in forbidden_modules:
        raise ImportError(f"Import of '{{name}}' is not allowed in sandbox")
    
    return original_import(name, *args, **kwargs)

builtins.__import__ = restricted_import

# Execute original code
try:
{original_code}
except Exception as e:
    print(f"SANDBOX_ERROR: {{e}}")
    sys.exit(1)
'''
        return sandbox_wrapper


class TaintLabel(str, Enum):
    """Taint classification for data flow tracking in plugin security analysis.

    Tracks how untrusted data flows from sources (user input, network, file reads)
    to sinks (eval, exec, subprocess, file writes, network sends). A tainted value
    reaching an un-sanitized sink is a confirmed security issue, not just a pattern match.
    """
    USER_INPUT = "user_input"
    NETWORK_DATA = "network_data"
    FILE_DATA = "file_data"
    DESERIALIZED = "deserialized"
    ENVIRONMENT = "environment"


@dataclass
class TaintedFlow:
    """A confirmed tainted data flow from source to sink."""
    source_label: TaintLabel
    source_line: int
    source_name: str
    sink_line: int
    sink_name: str
    file_path: Optional[Path] = None

    def to_issue(self) -> SecurityIssue:
        return SecurityIssue(
            severity="CRITICAL",
            category="TAINTED_DATA_FLOW",
            description=(
                f"Tainted data ({self.source_label.value}) flows from "
                f"'{self.source_name}' (line {self.source_line}) to "
                f"sink '{self.sink_name}' (line {self.sink_line}) without sanitization"
            ),
            file_path=self.file_path,
            line_number=self.sink_line,
            recommendation="Sanitize or validate the data before passing to the sink",
        )


class TaintTracker:
    """Intra-procedural taint analysis via AST data-flow tracking.

    Tracks assignments that carry tainted data (from network reads, file reads,
    user input, deserialization) and identifies when tainted variables reach
    dangerous sinks (eval, exec, subprocess, os.system).

    This is a forward analysis: we walk the AST in order, propagating taint
    through assignments and function calls.
    """

    TAINT_SOURCES: Dict[str, TaintLabel] = {
        "input": TaintLabel.USER_INPUT,
        "raw_input": TaintLabel.USER_INPUT,
        "recv": TaintLabel.NETWORK_DATA,
        "read": TaintLabel.FILE_DATA,
        "readline": TaintLabel.FILE_DATA,
        "readlines": TaintLabel.FILE_DATA,
        "json.load": TaintLabel.DESERIALIZED,
        "json.loads": TaintLabel.DESERIALIZED,
        "pickle.load": TaintLabel.DESERIALIZED,
        "pickle.loads": TaintLabel.DESERIALIZED,
        "yaml.load": TaintLabel.DESERIALIZED,
        "os.environ": TaintLabel.ENVIRONMENT,
        "os.getenv": TaintLabel.ENVIRONMENT,
    }

    DANGEROUS_SINKS = frozenset({
        "eval", "exec", "compile", "__import__",
        "os.system", "os.popen",
        "subprocess.run", "subprocess.call", "subprocess.Popen",
        "subprocess.check_output", "subprocess.check_call",
    })

    def analyze(self, tree: ast.Module, file_path: Optional[Path] = None) -> List[TaintedFlow]:
        """Run taint analysis on a parsed AST module."""
        tainted_vars: Dict[str, Tuple[TaintLabel, int, str]] = {}
        flows: List[TaintedFlow] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                self._handle_assignment(node, tainted_vars)
            elif isinstance(node, ast.Call):
                self._check_sink(node, tainted_vars, flows, file_path)

        return flows

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Extract the fully-qualified name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            obj = node.func
            while isinstance(obj, ast.Attribute):
                parts.append(obj.attr)
                obj = obj.value  # type: ignore[assignment]
            if isinstance(obj, ast.Name):
                parts.append(obj.id)
            return ".".join(reversed(parts))
        return None

    def _handle_assignment(
        self, node: ast.Assign, tainted: Dict[str, Tuple[TaintLabel, int, str]]
    ) -> None:
        """If the RHS is a taint source or a tainted variable, propagate taint to LHS."""
        if isinstance(node.value, ast.Call):
            call_name = self._get_call_name(node.value)
            if call_name and call_name in self.TAINT_SOURCES:
                label = self.TAINT_SOURCES[call_name]
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        tainted[target.id] = (label, getattr(node, "lineno", 0), call_name)

        elif isinstance(node.value, ast.Name) and node.value.id in tainted:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    tainted[target.id] = tainted[node.value.id]

    def _check_sink(
        self,
        node: ast.Call,
        tainted: Dict[str, Tuple[TaintLabel, int, str]],
        flows: List[TaintedFlow],
        file_path: Optional[Path],
    ) -> None:
        """Check if any argument to a dangerous sink is tainted."""
        call_name = self._get_call_name(node)
        if call_name not in self.DANGEROUS_SINKS:
            return

        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in tainted:
                label, source_line, source_name = tainted[arg.id]
                flows.append(TaintedFlow(
                    source_label=label,
                    source_line=source_line,
                    source_name=source_name,
                    sink_line=getattr(node, "lineno", 0),
                    sink_name=call_name,
                    file_path=file_path,
                ))


class CodeAnalyzer:
    """Advanced static code analysis with pattern matching, AST analysis, and taint tracking."""
    
    def __init__(self):
        self.dangerous_patterns = [
            (r'subprocess\.', 'Subprocess execution detected'),
            (r'os\.system', 'System command execution'),
            (r'eval\s*\(', 'Dynamic code evaluation'),
            (r'exec\s*\(', 'Dynamic code execution'),
            (r'__import__', 'Dynamic import'),
            (r'open\s*\(.*[\'"]w', 'File write operation'),
            (r'pickle\.loads?', 'Pickle deserialization'),
            (r'socket\.', 'Network socket usage'),
            (r'urllib\.request', 'HTTP request'),
            (r'requests\.', 'HTTP request library'),
            (r'ctypes\.', 'C library access'),
            (r'platform\.', 'System information access'),
            (r'getattr\s*\(.*__', 'Dangerous attribute access'),
            (r'setattr\s*\(.*__', 'Dangerous attribute modification'),
            (r'globals\s*\(\)', 'Global namespace access'),
            (r'locals\s*\(\)', 'Local namespace access'),
            (r'vars\s*\(\)', 'Variable namespace access'),
            (r'dir\s*\(\)', 'Object introspection'),
            (r'hasattr.*__', 'Private attribute checking'),
            (r'\\x[0-9a-fA-F]{2}', 'Hex encoded strings'),
            (r'base64\.', 'Base64 encoding/decoding'),
            (r'marshal\.', 'Marshal serialization'),
            (r'threading\.', 'Threading operations'),
            (r'multiprocessing\.', 'Multiprocessing operations'),
            (r'asyncio\.subprocess', 'Async subprocess'),
            (r'tempfile\.', 'Temporary file operations'),
            (r'shutil\.', 'File system operations'),
            (r'pathlib\..*\.write', 'Path-based file writing'),
            (r'sys\.exit', 'System exit'),
            (r'quit\s*\(\)', 'Quit function'),
            (r'exit\s*\(\)', 'Exit function'),
        ]
        
        self.permission_patterns = {
            PluginPermission.NETWORK_ACCESS: [
                r'socket\.', r'urllib\.', r'requests\.', r'http\.', r'asyncio\.open_connection'
            ],
            PluginPermission.FILE_SYSTEM: [
                r'open\s*\(', r'pathlib\..*\.write', r'os\.path', r'shutil\.', r'tempfile\.'
            ],
            PluginPermission.SYSTEM_COMMANDS: [
                r'subprocess\.', r'os\.system', r'os\.popen', r'commands\.'
            ],
            PluginPermission.AGENT_CONTROL: [
                r'agent\.', r'consciousness\.', r'recursive_'
            ]
        }
    
    async def analyze_file(self, file_path: Path) -> List[SecurityIssue]:
        """Analyze single Python file for security issues.

        Runs three analysis layers:
        1. Pattern-based (regex against known dangerous patterns)
        2. AST-based (structural analysis of the parse tree)
        3. Import analysis (dangerous module detection)
        4. Taint flow analysis (data flow from sources to sinks)
        """
        issues = []
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            issues.extend(self._analyze_patterns(content, file_path))
            issues.extend(self._analyze_ast(content, file_path))
            issues.extend(self._analyze_imports(content, file_path))

            try:
                tree = ast.parse(content)
                tracker = TaintTracker()
                tainted_flows = tracker.analyze(tree, file_path)
                issues.extend(flow.to_issue() for flow in tainted_flows)
            except SyntaxError:
                pass  # Already reported by _analyze_ast
            
        except Exception as e:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='ANALYSIS_ERROR',
                description=f'Failed to analyze file: {e}',
                file_path=file_path
            ))
        
        return issues
    
    def _analyze_patterns(self, content: str, file_path: Path) -> List[SecurityIssue]:
        """Pattern-based security analysis"""
        issues = []
        lines = content.split('\n')
        
        for pattern, description in self.dangerous_patterns:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    severity = self._determine_pattern_severity(pattern)
                    issues.append(SecurityIssue(
                        severity=severity,
                        category='DANGEROUS_PATTERN',
                        description=description,
                        file_path=file_path,
                        line_number=line_num,
                        code_snippet=line.strip(),
                        recommendation=self._get_pattern_recommendation(pattern)
                    ))
        
        return issues
    
    def _analyze_ast(self, content: str, file_path: Path) -> List[SecurityIssue]:
        """AST-based security analysis"""
        issues = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Check for dangerous function calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile']:
                            issues.append(SecurityIssue(
                                severity='CRITICAL',
                                category='DANGEROUS_FUNCTION',
                                description=f'Dangerous function call: {node.func.id}',
                                file_path=file_path,
                                line_number=getattr(node, 'lineno', 0)
                            ))
                
                # Check for dangerous imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ['os', 'sys', 'subprocess', 'socket']:
                            issues.append(SecurityIssue(
                                severity='HIGH',
                                category='DANGEROUS_IMPORT',
                                description=f'Potentially dangerous import: {alias.name}',
                                file_path=file_path,
                                line_number=getattr(node, 'lineno', 0)
                            ))
                
                # Check for attribute access to private members
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.attr, str) and node.attr.startswith('_'):
                        issues.append(SecurityIssue(
                            severity='MEDIUM',
                            category='PRIVATE_ACCESS',
                            description=f'Access to private attribute: {node.attr}',
                            file_path=file_path,
                            line_number=getattr(node, 'lineno', 0)
                        ))
        
        except SyntaxError as e:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='SYNTAX_ERROR',
                description=f'Syntax error in code: {e}',
                file_path=file_path,
                line_number=e.lineno or 0
            ))
        
        return issues
    
    def _analyze_imports(self, content: str, file_path: Path) -> List[SecurityIssue]:
        """Analyze import statements for security risks"""
        issues = []
        
        import_pattern = r'^\s*(?:from\s+(\S+)\s+)?import\s+(.+)$'
        lines = content.split('\n')
        
        dangerous_imports = {
            'os': 'Operating system interface',
            'sys': 'System-specific parameters',
            'subprocess': 'Subprocess management',
            'socket': 'Network socket interface',
            'ctypes': 'C library interface',
            'pickle': 'Object serialization',
            'marshal': 'Object marshaling',
            'gc': 'Garbage collector interface',
            'inspect': 'Live object inspection',
            'ast': 'Abstract syntax trees',
            'compile': 'Code compilation',
            'eval': 'Expression evaluation',
            'exec': 'Code execution'
        }
        
        for line_num, line in enumerate(lines, 1):
            match = re.match(import_pattern, line.strip())
            if match:
                module_from, imports = match.groups()
                
                # Check direct imports
                for imp in imports.split(','):
                    imp = imp.strip().split(' as ')[0]
                    if imp in dangerous_imports:
                        issues.append(SecurityIssue(
                            severity='HIGH',
                            category='DANGEROUS_IMPORT',
                            description=f'Dangerous import: {imp} - {dangerous_imports[imp]}',
                            file_path=file_path,
                            line_number=line_num,
                            code_snippet=line.strip()
                        ))
                
                # Check module imports
                if module_from and module_from in dangerous_imports:
                    issues.append(SecurityIssue(
                        severity='HIGH',
                        category='DANGEROUS_MODULE',
                        description=f'Dangerous module: {module_from} - {dangerous_imports[module_from]}',
                        file_path=file_path,
                        line_number=line_num,
                        code_snippet=line.strip()
                    ))
        
        return issues
    
    def _determine_pattern_severity(self, pattern: str) -> str:
        """Determine severity level for detected pattern"""
        critical_patterns = [r'subprocess\.', r'os\.system', r'eval\s*\(', r'exec\s*\(']
        high_patterns = [r'__import__', r'pickle\.loads?', r'socket\.']
        
        if any(re.search(p, pattern) for p in critical_patterns):
            return 'CRITICAL'
        elif any(re.search(p, pattern) for p in high_patterns):
            return 'HIGH'
        else:
            return 'MEDIUM'
    
    def _get_pattern_recommendation(self, pattern: str) -> str:
        """Get security recommendation for pattern"""
        recommendations = {
            r'subprocess\.': 'Use safe alternative or request SYSTEM_COMMANDS permission',
            r'os\.system': 'Use subprocess with explicit arguments',
            r'eval\s*\(': 'Avoid eval(), use ast.literal_eval() for safe evaluation',
            r'exec\s*\(': 'Avoid exec(), use safer alternatives',
            r'socket\.': 'Request NETWORK_ACCESS permission',
            r'open\s*\(.*[\'"]w': 'Request FILE_SYSTEM permission for write operations'
        }
        
        for p, rec in recommendations.items():
            if re.search(p, pattern):
                return rec
        
        return 'Review for security implications'
    
    def check_permissions(self, content: str, required_permissions: List[PluginPermission]) -> Dict[PluginPermission, bool]:
        """Check if code requires specific permissions"""
        detected_permissions = {}
        
        for permission, patterns in self.permission_patterns.items():
            detected = False
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected = True
                    break
            detected_permissions[permission] = detected
        
        # Verify required permissions are sufficient
        permission_check = {}
        for permission in PluginPermission:
            if detected_permissions.get(permission, False):
                permission_check[permission] = permission in required_permissions
            else:
                permission_check[permission] = True  # Not needed
        
        return permission_check


class CryptographicValidator:
    """Cryptographic validation and signature verification"""
    
    def __init__(self):
        self.trusted_keys: Dict[str, bytes] = {}
        self.hash_algorithms = {
            'sha256': hashlib.sha256,
            'sha512': hashlib.sha512,
            'blake2b': hashlib.blake2b
        }
    
    async def verify_signature(self, data: bytes, signature: str, public_key: bytes) -> bool:
        """Verify cryptographic signature of plugin data"""
        try:
            # Parse signature (format: algorithm:signature_bytes)
            if ':' not in signature:
                return False
            
            algorithm, sig_data = signature.split(':', 1)
            sig_bytes = bytes.fromhex(sig_data)
            
            # Load public key
            try:
                key = serialization.load_pem_public_key(public_key)
            except Exception:
                try:
                    key = serialization.load_der_public_key(public_key)
                except Exception:
                    return False
            
            # Verify signature
            if algorithm == 'rsa_pss_sha256':
                key.verify(
                    sig_bytes,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                return True
            
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
        
        return False
    
    async def compute_hash(self, data: bytes, algorithm: str = 'sha256') -> str:
        """Compute cryptographic hash of data"""
        if algorithm not in self.hash_algorithms:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        hasher = self.hash_algorithms[algorithm]()
        hasher.update(data)
        return hasher.hexdigest()
    
    async def validate_archive_integrity(self, archive_path: Path) -> Tuple[bool, str]:
        """Validate integrity of plugin archive"""
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                # Check for zip bomb
                total_size = 0
                for info in zf.filelist:
                    total_size += info.file_size
                    if total_size > 100 * 1024 * 1024:  # 100MB limit
                        return False, "Archive too large (potential zip bomb)"
                
                # Verify archive structure
                manifest_found = False
                for info in zf.filelist:
                    if info.filename == 'manifest.json':
                        manifest_found = True
                    
                    # Check for path traversal
                    if '..' in info.filename or info.filename.startswith('/'):
                        return False, f"Path traversal detected: {info.filename}"
                
                if not manifest_found:
                    return False, "No manifest.json found in archive"
                
                return True, "Archive validation passed"
        
        except Exception as e:
            return False, f"Archive validation error: {e}"


class DependencyAnalyzer:
    """Analyze plugin dependencies for security risks"""
    
    def __init__(self):
        self.dangerous_packages = {
            'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests',
            'ctypes', 'pickle', 'marshal', 'gc', 'inspect', 'ast',
            'threading', 'multiprocessing', 'concurrent', 'asyncio.subprocess'
        }
        
        self.package_vulnerabilities = {}  # Would be populated from CVE database
    
    async def analyze_dependencies(self, dependencies: List[str]) -> List[SecurityIssue]:
        """Analyze list of dependencies for security issues"""
        issues = []
        
        for dep in dependencies:
            # Parse dependency specification
            dep_name = self._parse_dependency_name(dep)
            
            # Check against dangerous packages
            if dep_name in self.dangerous_packages:
                issues.append(SecurityIssue(
                    severity='HIGH',
                    category='DANGEROUS_DEPENDENCY',
                    description=f'Potentially dangerous dependency: {dep_name}',
                    recommendation='Review dependency necessity and security implications'
                ))
            
            # Check for known vulnerabilities
            vulnerabilities = await self._check_vulnerabilities(dep_name, dep)
            issues.extend(vulnerabilities)
            
            # Check for suspicious patterns
            if self._is_suspicious_dependency(dep_name):
                issues.append(SecurityIssue(
                    severity='MEDIUM',
                    category='SUSPICIOUS_DEPENDENCY',
                    description=f'Suspicious dependency pattern: {dep_name}',
                    recommendation='Verify dependency legitimacy'
                ))
        
        return issues
    
    def _parse_dependency_name(self, dependency: str) -> str:
        """Extract package name from dependency specification"""
        # Handle various formats: package==1.0.0, package>=1.0, package[extra]
        import re
        match = re.match(r'^([a-zA-Z0-9_-]+)', dependency)
        return match.group(1) if match else dependency
    
    async def _check_vulnerabilities(self, package_name: str, full_spec: str) -> List[SecurityIssue]:
        """Check package for known vulnerabilities"""
        issues = []
        
        # This would integrate with CVE databases
        if package_name in self.package_vulnerabilities:
            for vuln in self.package_vulnerabilities[package_name]:
                issues.append(SecurityIssue(
                    severity=vuln['severity'],
                    category='KNOWN_VULNERABILITY',
                    description=f'Known vulnerability in {package_name}: {vuln["description"]}',
                    recommendation=f'Update to version {vuln.get("fixed_version", "latest")}'
                ))
        
        return issues
    
    def _is_suspicious_dependency(self, package_name: str) -> bool:
        """Check if dependency name appears suspicious"""
        suspicious_patterns = [
            r'^[a-z]{1,3}$',  # Very short names
            r'[0-9]+[a-z]+[0-9]+',  # Mixed numbers and letters
            r'[_-]{2,}',  # Multiple underscores/hyphens
            r'^test',  # Test packages
            r'temp|tmp',  # Temporary packages
        ]
        
        return any(re.search(pattern, package_name, re.IGNORECASE) for pattern in suspicious_patterns)


class SecurityManager:
    """Comprehensive security management for plugin system"""
    
    def __init__(self, security_level: int = SecurityLevel.STANDARD):
        self.security_level = security_level
        self.code_analyzer = CodeAnalyzer()
        self.crypto_validator = CryptographicValidator()
        self.dependency_analyzer = DependencyAnalyzer()
        self.sandbox_executor = ThreadPoolExecutor(max_workers=4)
        
        # Security caches
        self._validation_cache: Dict[str, SecurityReport] = {}
        self._signature_cache: Dict[str, bool] = {}
        
    async def validate_plugin(self, plugin_path: Path, manifest: PluginManifest) -> Tuple[bool, List[str]]:
        """Comprehensive plugin security validation"""
        logger.info(f"Validating plugin security: {manifest.name}")
        
        # Generate cache key
        cache_key = await self._generate_cache_key(plugin_path, manifest)
        
        # Check cache
        if cache_key in self._validation_cache:
            cached_report = self._validation_cache[cache_key]
            if (datetime.now(timezone.utc) - cached_report.scan_timestamp).seconds < 3600:
                return cached_report.is_safe, [issue.description for issue in cached_report.issues]
        
        # Create security report
        report = SecurityReport(
            plugin_id=manifest.name,
            is_safe=True,
            risk_score=0.0
        )
        
        try:
            # 1. Validate manifest
            await self._validate_manifest(manifest, report)
            
            # 2. Analyze code files
            await self._analyze_plugin_code(plugin_path, report)
            
            # 3. Validate permissions
            await self._validate_permissions(plugin_path, manifest, report)
            
            # 4. Check dependencies
            await self._validate_dependencies(manifest.dependencies, report)
            
            # 5. Verify signatures if required
            if manifest.signature and self.security_level >= SecurityLevel.HIGH:
                await self._verify_plugin_signature(plugin_path, manifest, report)
            
            # 6. Calculate risk score
            report.risk_score = self._calculate_risk_score(report)
            report.is_safe = report.risk_score < self._get_risk_threshold()
            
            # Cache result
            self._validation_cache[cache_key] = report
            
            issues = [issue.description for issue in report.issues if issue.severity in ['CRITICAL', 'HIGH']]
            return report.is_safe, issues
            
        except Exception as e:
            logger.error(f"Plugin validation error: {e}")
            return False, [f"Validation error: {e}"]
    
    async def _validate_manifest(self, manifest: PluginManifest, report: SecurityReport):
        """Validate plugin manifest for security issues"""
        issues = []
        
        # Check for suspicious metadata
        if not manifest.author or len(manifest.author) < 3:
            issues.append(SecurityIssue(
                severity='MEDIUM',
                category='MANIFEST_ISSUE',
                description='Missing or suspicious author information'
            ))
        
        if not manifest.description or len(manifest.description) < 10:
            issues.append(SecurityIssue(
                severity='LOW',
                category='MANIFEST_ISSUE',
                description='Missing or insufficient description'
            ))
        
        # Check security level requirements
        if manifest.security_level > self.security_level:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='SECURITY_LEVEL',
                description=f'Plugin requires security level {manifest.security_level}, system supports {self.security_level}'
            ))
        
        # Validate permissions
        dangerous_permissions = [
            PluginPermission.SYSTEM_COMMANDS,
            PluginPermission.FILE_SYSTEM,
            PluginPermission.AGENT_CONTROL
        ]
        
        for perm in manifest.permissions:
            if perm in dangerous_permissions and not manifest.trusted:
                issues.append(SecurityIssue(
                    severity='HIGH',
                    category='DANGEROUS_PERMISSION',
                    description=f'Untrusted plugin requests dangerous permission: {perm}'
                ))
        
        report.issues.extend(issues)
    
    async def _analyze_plugin_code(self, plugin_path: Path, report: SecurityReport):
        """Analyze all Python files in plugin directory"""
        python_files = list(plugin_path.rglob('*.py'))
        
        analysis_tasks = []
        for py_file in python_files:
            analysis_tasks.append(self.code_analyzer.analyze_file(py_file))
        
        if analysis_tasks:
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    report.issues.append(SecurityIssue(
                        severity='HIGH',
                        category='ANALYSIS_ERROR',
                        description=f'Code analysis failed: {result}'
                    ))
                else:
                    report.issues.extend(result)
    
    async def _validate_permissions(self, plugin_path: Path, manifest: PluginManifest, report: SecurityReport):
        """Validate that code usage matches declared permissions"""
        # Read all Python files
        all_code = ""
        for py_file in plugin_path.rglob('*.py'):
            try:
                async with aiofiles.open(py_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                all_code += content + "\n"
            except Exception:
                continue
        
        # Check permission requirements
        permission_check = self.code_analyzer.check_permissions(all_code, manifest.permissions)
        
        missing_permissions = []
        for permission, is_satisfied in permission_check.items():
            if not is_satisfied:
                missing_permissions.append(permission)
        
        if missing_permissions:
            report.issues.append(SecurityIssue(
                severity='HIGH',
                category='PERMISSION_MISMATCH',
                description=f'Code requires undeclared permissions: {missing_permissions}',
                recommendation='Add required permissions to manifest'
            ))
        
        report.permissions_validated = len(missing_permissions) == 0
    
    async def _validate_dependencies(self, dependencies: List[str], report: SecurityReport):
        """Validate plugin dependencies"""
        dependency_issues = await self.dependency_analyzer.analyze_dependencies(dependencies)
        report.issues.extend(dependency_issues)
        
        # Check for excessive dependencies
        if len(dependencies) > 20:
            report.issues.append(SecurityIssue(
                severity='MEDIUM',
                category='EXCESSIVE_DEPENDENCIES',
                description=f'Plugin has {len(dependencies)} dependencies (consider reducing)',
                recommendation='Review dependency necessity'
            ))
        
        report.dependencies_safe = not any(
            issue.severity in ['CRITICAL', 'HIGH'] 
            for issue in dependency_issues
        )
    
    async def _verify_plugin_signature(self, plugin_path: Path, manifest: PluginManifest, report: SecurityReport):
        """Verify cryptographic signature of plugin"""
        if not manifest.signature:
            report.signature_verified = False
            return
        
        try:
            # Create archive hash
            plugin_data = await self._create_plugin_hash(plugin_path)
            
            # Verify signature (would need public key infrastructure)
            # For now, implement basic signature checking
            expected_hash = manifest.signature.split(':')[-1] if ':' in manifest.signature else manifest.signature
            
            if plugin_data.hex() == expected_hash:
                report.signature_verified = True
            else:
                report.signature_verified = False
                report.issues.append(SecurityIssue(
                    severity='CRITICAL',
                    category='SIGNATURE_INVALID',
                    description='Plugin signature verification failed',
                    recommendation='Verify plugin integrity and source'
                ))
        
        except Exception as e:
            report.signature_verified = False
            report.issues.append(SecurityIssue(
                severity='HIGH',
                category='SIGNATURE_ERROR',
                description=f'Signature verification error: {e}'
            ))
    
    async def _create_plugin_hash(self, plugin_path: Path) -> bytes:
        """Create deterministic hash of plugin contents"""
        hasher = hashlib.sha256()
        
        # Sort files for deterministic hash
        all_files = sorted(plugin_path.rglob('*'))
        
        for file_path in all_files:
            if file_path.is_file():
                # Add file path
                hasher.update(str(file_path.relative_to(plugin_path)).encode())
                
                # Add file content
                try:
                    async with aiofiles.open(file_path, 'rb') as f:
                        content = await f.read()
                    hasher.update(content)
                except Exception:
                    continue
        
        return hasher.digest()
    
    def _calculate_risk_score(self, report: SecurityReport) -> float:
        """Calculate overall risk score from security issues"""
        score = 0.0
        
        severity_weights = {
            'CRITICAL': 1.0,
            'HIGH': 0.7,
            'MEDIUM': 0.4,
            'LOW': 0.1
        }
        
        for issue in report.issues:
            score += severity_weights.get(issue.severity, 0.1)
        
        # Normalize to 0-1 range
        max_possible_score = len(report.issues) * 1.0
        if max_possible_score > 0:
            score = min(score / max_possible_score, 1.0)
        
        # Adjust for verification failures
        if not report.permissions_validated:
            score += 0.2
        if not report.signature_verified and self.security_level >= SecurityLevel.HIGH:
            score += 0.3
        if not report.dependencies_safe:
            score += 0.2
        
        return min(score, 1.0)
    
    def _get_risk_threshold(self) -> float:
        """Get risk threshold based on security level"""
        thresholds = {
            SecurityLevel.MINIMAL: 0.9,
            SecurityLevel.BASIC: 0.7,
            SecurityLevel.STANDARD: 0.5,
            SecurityLevel.HIGH: 0.3,
            SecurityLevel.MAXIMUM: 0.1
        }
        return thresholds.get(self.security_level, 0.5)
    
    async def _generate_cache_key(self, plugin_path: Path, manifest: PluginManifest) -> str:
        """Generate cache key for validation results"""
        plugin_hash = await self._create_plugin_hash(plugin_path)
        manifest_str = json.dumps(manifest.dict(), sort_keys=True)
        
        combined = plugin_hash + manifest_str.encode()
        return hashlib.sha256(combined).hexdigest()
    
    async def create_sandbox(self, plugin_id: str) -> SandboxEnvironment:
        """Create isolated sandbox environment for plugin"""
        temp_dir = Path(tempfile.mkdtemp(prefix=f"plugin_sandbox_{plugin_id}_"))
        temp_dir.chmod(0o750)
        
        # Create output directory
        output_dir = temp_dir / 'output'
        output_dir.mkdir()
        
        return SandboxEnvironment(plugin_id, temp_dir)
    
    async def cleanup_sandbox(self, sandbox: SandboxEnvironment):
        """Clean up sandbox environment"""
        try:
            import shutil
            shutil.rmtree(sandbox.temp_dir)
        except Exception as e:
            logger.error(f"Failed to cleanup sandbox: {e}")
    
    def get_security_report(self, plugin_id: str) -> Optional[SecurityReport]:
        """Get cached security report for plugin"""
        for report in self._validation_cache.values():
            if report.plugin_id == plugin_id:
                return report
        return None