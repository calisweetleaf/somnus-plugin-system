"""
MORPHEUS CHAT - Plugin Marketplace & Community Integration
Enterprise-grade plugin distribution, verification, and community management system.
"""

import asyncio
import aiohttp
import hashlib
import json
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, Union
import logging
import semver
import ssl
import certifi

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature

from plugin_base import PluginManifest, PluginCapability, PluginPermission
from security import SecurityManager, SecurityReport

logger = logging.getLogger(__name__)


class MarketplaceProvider(str, Enum):
    OFFICIAL = "official"
    COMMUNITY = "community"
    ENTERPRISE = "enterprise"
    PRIVATE = "private"


class PluginStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class DistributionChannel(str, Enum):
    PUBLIC = "public"
    BETA = "beta"
    ALPHA = "alpha"
    PRIVATE = "private"


@dataclass
class MarketplaceConfig:
    official_registry_url: str = "https://marketplace.morpheus.ai"
    community_registry_url: str = "https://community.morpheus.ai"
    cache_duration_hours: int = 24
    max_download_size_mb: int = 100
    verify_signatures: bool = True
    allow_unsigned_plugins: bool = False
    trust_level_threshold: int = 3
    auto_update_enabled: bool = True
    parallel_downloads: int = 5


@dataclass
class PluginRating:
    user_id: str
    rating: float  # 1.0 to 5.0
    review: str
    version: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PluginStatistics:
    download_count: int = 0
    install_count: int = 0
    active_users: int = 0
    rating_average: float = 0.0
    rating_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PluginListing:
    plugin_id: str
    manifest: PluginManifest
    provider: MarketplaceProvider
    status: PluginStatus
    channel: DistributionChannel
    
    download_url: str
    signature_url: Optional[str] = None
    verification_key: Optional[str] = None
    
    statistics: PluginStatistics = field(default_factory=PluginStatistics)
    ratings: List[PluginRating] = field(default_factory=list)
    
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    screenshots: List[str] = field(default_factory=list)
    documentation_url: Optional[str] = None
    support_url: Optional[str] = None
    
    dependencies: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    
    trust_score: float = 0.0
    security_scan_results: Optional[SecurityReport] = None


@dataclass
class DownloadProgress:
    plugin_id: str
    total_bytes: int
    downloaded_bytes: int
    speed_bps: float
    eta_seconds: float
    status: str


class TrustSystem:
    def __init__(self):
        self.developer_scores: Dict[str, float] = {}
        self.plugin_scores: Dict[str, float] = {}
        self.verification_keys: Dict[str, bytes] = {}
        
    def calculate_trust_score(self, listing: PluginListing) -> float:
        base_score = 0.0
        
        developer_score = self.developer_scores.get(listing.manifest.author, 0.5)
        base_score += developer_score * 0.3
        
        if listing.provider == MarketplaceProvider.OFFICIAL:
            base_score += 0.4
        elif listing.provider == MarketplaceProvider.ENTERPRISE:
            base_score += 0.3
        elif listing.provider == MarketplaceProvider.COMMUNITY:
            base_score += 0.1
        
        if listing.statistics.rating_count > 0:
            rating_factor = min(listing.statistics.rating_average / 5.0, 1.0)
            review_factor = min(listing.statistics.rating_count / 100.0, 1.0)
            base_score += rating_factor * review_factor * 0.2
        
        if listing.statistics.download_count > 1000:
            base_score += 0.1
        
        if listing.security_scan_results:
            security_factor = 1.0 - listing.security_scan_results.risk_score
            base_score *= security_factor
        
        age_days = (datetime.now(timezone.utc) - listing.published_at).days
        if age_days > 365:
            base_score *= 0.9
        
        return min(base_score, 1.0)
    
    def verify_developer_signature(self, data: bytes, signature: str, developer_id: str) -> bool:
        if developer_id not in self.verification_keys:
            return False
        
        try:
            public_key = serialization.load_pem_public_key(self.verification_keys[developer_id])
            signature_bytes = bytes.fromhex(signature)
            
            public_key.verify(
                signature_bytes,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except (InvalidSignature, Exception):
            return False
    
    def register_developer_key(self, developer_id: str, public_key: bytes):
        self.verification_keys[developer_id] = public_key
        if developer_id not in self.developer_scores:
            self.developer_scores[developer_id] = 0.5


class RegistryClient:
    def __init__(self, config: MarketplaceConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, Tuple[datetime, Any]] = {}
        
    async def __aenter__(self):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'Morpheus-Plugin-Client/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_plugins(self, 
                           query: str = "",
                           category: Optional[str] = None,
                           provider: Optional[MarketplaceProvider] = None,
                           channel: DistributionChannel = DistributionChannel.PUBLIC,
                           page: int = 1,
                           limit: int = 20) -> List[PluginListing]:
        
        cache_key = f"search:{query}:{category}:{provider}:{channel}:{page}:{limit}"
        cached_result = self._get_cached(cache_key)
        if cached_result:
            return cached_result
        
        params = {
            'q': query,
            'page': page,
            'limit': limit,
            'channel': channel.value
        }
        
        if category:
            params['category'] = category
        if provider:
            params['provider'] = provider.value
        
        url = f"{self.config.official_registry_url}/api/v1/plugins/search"
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                listings = [self._parse_listing(item) for item in data.get('plugins', [])]
                self._cache_result(cache_key, listings)
                return listings
            else:
                logger.error(f"Plugin search failed: {response.status}")
                return []
    
    async def get_plugin_details(self, plugin_id: str, version: Optional[str] = None) -> Optional[PluginListing]:
        cache_key = f"details:{plugin_id}:{version}"
        cached_result = self._get_cached(cache_key)
        if cached_result:
            return cached_result
        
        url = f"{self.config.official_registry_url}/api/v1/plugins/{plugin_id}"
        params = {}
        if version:
            params['version'] = version
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                listing = self._parse_listing(data)
                self._cache_result(cache_key, listing)
                return listing
            else:
                return None
    
    async def get_plugin_versions(self, plugin_id: str) -> List[str]:
        url = f"{self.config.official_registry_url}/api/v1/plugins/{plugin_id}/versions"
        
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('versions', [])
            else:
                return []
    
    async def download_plugin(self, listing: PluginListing, target_path: Path, 
                            progress_callback: Optional[callable] = None) -> bool:
        
        async with self.session.get(listing.download_url) as response:
            if response.status != 200:
                logger.error(f"Download failed: {response.status}")
                return False
            
            total_size = int(response.headers.get('Content-Length', 0))
            
            if total_size > self.config.max_download_size_mb * 1024 * 1024:
                logger.error(f"Plugin too large: {total_size} bytes")
                return False
            
            downloaded = 0
            start_time = datetime.now()
            
            with open(target_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        eta = (total_size - downloaded) / speed if speed > 0 else 0
                        
                        progress = DownloadProgress(
                            plugin_id=listing.plugin_id,
                            total_bytes=total_size,
                            downloaded_bytes=downloaded,
                            speed_bps=speed,
                            eta_seconds=eta,
                            status="downloading"
                        )
                        progress_callback(progress)
        
        if progress_callback:
            progress_callback(DownloadProgress(
                plugin_id=listing.plugin_id,
                total_bytes=total_size,
                downloaded_bytes=downloaded,
                speed_bps=0,
                eta_seconds=0,
                status="completed"
            ))
        
        return True
    
    async def verify_download(self, listing: PluginListing, file_path: Path) -> bool:
        if not listing.signature_url or not self.config.verify_signatures:
            return True
        
        try:
            async with self.session.get(listing.signature_url) as response:
                if response.status != 200:
                    return False
                
                signature_data = await response.json()
                signature = signature_data.get('signature')
                algorithm = signature_data.get('algorithm', 'sha256')
                
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                if algorithm == 'sha256':
                    file_hash = hashlib.sha256(file_data).hexdigest()
                    return file_hash == signature
                
                return False
        
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    async def submit_rating(self, plugin_id: str, rating: PluginRating) -> bool:
        url = f"{self.config.official_registry_url}/api/v1/plugins/{plugin_id}/ratings"
        
        data = {
            'rating': rating.rating,
            'review': rating.review,
            'version': rating.version
        }
        
        async with self.session.post(url, json=data) as response:
            return response.status == 200
    
    async def report_plugin(self, plugin_id: str, reason: str, details: str) -> bool:
        url = f"{self.config.official_registry_url}/api/v1/plugins/{plugin_id}/report"
        
        data = {
            'reason': reason,
            'details': details
        }
        
        async with self.session.post(url, json=data) as response:
            return response.status == 200
    
    def _parse_listing(self, data: Dict[str, Any]) -> PluginListing:
        manifest_data = data.get('manifest', {})
        manifest = PluginManifest(**manifest_data)
        
        statistics_data = data.get('statistics', {})
        statistics = PluginStatistics(
            download_count=statistics_data.get('download_count', 0),
            install_count=statistics_data.get('install_count', 0),
            active_users=statistics_data.get('active_users', 0),
            rating_average=statistics_data.get('rating_average', 0.0),
            rating_count=statistics_data.get('rating_count', 0)
        )
        
        ratings_data = data.get('ratings', [])
        ratings = [
            PluginRating(
                user_id=r.get('user_id', ''),
                rating=r.get('rating', 0.0),
                review=r.get('review', ''),
                version=r.get('version', ''),
                timestamp=datetime.fromisoformat(r.get('timestamp', datetime.now(timezone.utc).isoformat()))
            )
            for r in ratings_data
        ]
        
        return PluginListing(
            plugin_id=data.get('plugin_id', manifest.name),
            manifest=manifest,
            provider=MarketplaceProvider(data.get('provider', 'community')),
            status=PluginStatus(data.get('status', 'approved')),
            channel=DistributionChannel(data.get('channel', 'public')),
            download_url=data.get('download_url', ''),
            signature_url=data.get('signature_url'),
            verification_key=data.get('verification_key'),
            statistics=statistics,
            ratings=ratings,
            published_at=datetime.fromisoformat(data.get('published_at', datetime.now(timezone.utc).isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now(timezone.utc).isoformat())),
            screenshots=data.get('screenshots', []),
            documentation_url=data.get('documentation_url'),
            support_url=data.get('support_url'),
            dependencies=data.get('dependencies', []),
            conflicts=data.get('conflicts', []),
            trust_score=data.get('trust_score', 0.0)
        )
    
    def _get_cached(self, key: str) -> Any:
        if key in self.cache:
            timestamp, data = self.cache[key]
            if datetime.now(timezone.utc) - timestamp < timedelta(hours=self.config.cache_duration_hours):
                return data
            else:
                del self.cache[key]
        return None
    
    def _cache_result(self, key: str, data: Any):
        self.cache[key] = (datetime.now(timezone.utc), data)


class PluginInstaller:
    def __init__(self, plugin_manager, security_manager: SecurityManager, config: MarketplaceConfig):
        self.plugin_manager = plugin_manager
        self.security_manager = security_manager
        self.config = config
        self.temp_dir = Path(tempfile.gettempdir()) / "morpheus_plugin_installs"
        self.temp_dir.mkdir(exist_ok=True)
        
    async def install_from_marketplace(self, plugin_id: str, version: Optional[str] = None,
                                     progress_callback: Optional[callable] = None) -> Tuple[bool, str]:
        
        async with RegistryClient(self.config) as client:
            listing = await client.get_plugin_details(plugin_id, version)
            if not listing:
                return False, f"Plugin {plugin_id} not found in marketplace"
            
            return await self.install_from_listing(listing, progress_callback)
    
    async def install_from_listing(self, listing: PluginListing, 
                                 progress_callback: Optional[callable] = None) -> Tuple[bool, str]:
        
        if listing.trust_score < self.config.trust_level_threshold / 5.0:
            return False, f"Plugin trust score too low: {listing.trust_score}"
        
        temp_file = self.temp_dir / f"{listing.plugin_id}_{listing.manifest.version}.zip"
        
        try:
            async with RegistryClient(self.config) as client:
                success = await client.download_plugin(listing, temp_file, progress_callback)
                if not success:
                    return False, "Download failed"
                
                if not await client.verify_download(listing, temp_file):
                    return False, "Download verification failed"
            
            extract_dir = self.temp_dir / f"{listing.plugin_id}_extracted"
            if extract_dir.exists():
                import shutil
                shutil.rmtree(extract_dir)
            extract_dir.mkdir()
            
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            plugin_dir = self._find_plugin_directory(extract_dir)
            if not plugin_dir:
                return False, "Invalid plugin archive structure"
            
            manifest_path = plugin_dir / 'manifest.json'
            if not manifest_path.exists():
                return False, "Plugin manifest not found"
            
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            
            manifest = PluginManifest(**manifest_data)
            
            is_safe, security_issues = await self.security_manager.validate_plugin(plugin_dir, manifest)
            if not is_safe and not self.config.allow_unsigned_plugins:
                return False, f"Security validation failed: {security_issues}"
            
            target_dir = self.plugin_manager.plugin_base_dir / "installed" / listing.plugin_id
            if target_dir.exists():
                import shutil
                shutil.rmtree(target_dir)
            
            import shutil
            shutil.move(str(plugin_dir), str(target_dir))
            
            success = await self.plugin_manager.load_plugin(listing.plugin_id)
            if success:
                logger.info(f"Successfully installed plugin: {listing.plugin_id}")
                return True, "Installation completed successfully"
            else:
                return False, "Plugin installation succeeded but loading failed"
        
        except Exception as e:
            logger.error(f"Plugin installation failed: {e}")
            return False, f"Installation error: {e}"
        
        finally:
            if temp_file.exists():
                temp_file.unlink()
            if 'extract_dir' in locals() and extract_dir.exists():
                import shutil
                shutil.rmtree(extract_dir)
    
    async def install_from_archive(self, archive_path: Path, 
                                 progress_callback: Optional[callable] = None) -> Tuple[bool, str]:
        
        if not archive_path.exists() or not archive_path.is_file():
            return False, "Archive file not found"
        
        if archive_path.stat().st_size > self.config.max_download_size_mb * 1024 * 1024:
            return False, "Archive file too large"
        
        extract_dir = self.temp_dir / f"local_install_{int(datetime.now().timestamp())}"
        extract_dir.mkdir()
        
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            plugin_dir = self._find_plugin_directory(extract_dir)
            if not plugin_dir:
                return False, "Invalid plugin archive structure"
            
            manifest_path = plugin_dir / 'manifest.json'
            if not manifest_path.exists():
                return False, "Plugin manifest not found"
            
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            
            manifest = PluginManifest(**manifest_data)
            
            is_safe, security_issues = await self.security_manager.validate_plugin(plugin_dir, manifest)
            if not is_safe:
                if not self.config.allow_unsigned_plugins:
                    return False, f"Security validation failed: {security_issues}"
                else:
                    logger.warning(f"Installing potentially unsafe plugin: {security_issues}")
            
            target_dir = self.plugin_manager.plugin_base_dir / "installed" / manifest.name
            if target_dir.exists():
                import shutil
                shutil.rmtree(target_dir)
            
            import shutil
            shutil.move(str(plugin_dir), str(target_dir))
            
            success = await self.plugin_manager.load_plugin(manifest.name)
            if success:
                logger.info(f"Successfully installed plugin from archive: {manifest.name}")
                return True, "Installation completed successfully"
            else:
                return False, "Plugin installation succeeded but loading failed"
        
        except Exception as e:
            logger.error(f"Archive installation failed: {e}")
            return False, f"Installation error: {e}"
        
        finally:
            if extract_dir.exists():
                import shutil
                shutil.rmtree(extract_dir)
    
    async def uninstall_plugin(self, plugin_id: str) -> Tuple[bool, str]:
        try:
            if plugin_id in self.plugin_manager.active_plugins:
                await self.plugin_manager.unload_plugin(plugin_id)
            
            plugin_dir = self.plugin_manager.plugin_base_dir / "installed" / plugin_id
            if plugin_dir.exists():
                import shutil
                shutil.rmtree(plugin_dir)
                logger.info(f"Uninstalled plugin: {plugin_id}")
                return True, "Plugin uninstalled successfully"
            else:
                return False, "Plugin directory not found"
        
        except Exception as e:
            logger.error(f"Plugin uninstallation failed: {e}")
            return False, f"Uninstallation error: {e}"
    
    def _find_plugin_directory(self, extract_dir: Path) -> Optional[Path]:
        for item in extract_dir.iterdir():
            if item.is_dir():
                manifest_path = item / 'manifest.json'
                if manifest_path.exists():
                    return item
        
        manifest_path = extract_dir / 'manifest.json'
        if manifest_path.exists():
            return extract_dir
        
        return None


class UpdateManager:
    def __init__(self, plugin_manager, installer: PluginInstaller, config: MarketplaceConfig):
        self.plugin_manager = plugin_manager
        self.installer = installer
        self.config = config
        self.update_check_interval = timedelta(hours=6)
        self.last_update_check: Optional[datetime] = None
        self.available_updates: Dict[str, PluginListing] = {}
        
    async def check_for_updates(self, force: bool = False) -> Dict[str, str]:
        now = datetime.now(timezone.utc)
        
        if (not force and self.last_update_check and 
            now - self.last_update_check < self.update_check_interval):
            return {pid: listing.manifest.version for pid, listing in self.available_updates.items()}
        
        self.last_update_check = now
        self.available_updates.clear()
        
        async with RegistryClient(self.config) as client:
            update_tasks = []
            
            for plugin_id, plugin in self.plugin_manager.active_plugins.items():
                task = asyncio.create_task(self._check_plugin_update(client, plugin_id, plugin.manifest.version))
                update_tasks.append(task)
            
            if update_tasks:
                results = await asyncio.gather(*update_tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Update check failed: {result}")
                    elif result:
                        plugin_id, listing = result
                        self.available_updates[plugin_id] = listing
        
        return {pid: listing.manifest.version for pid, listing in self.available_updates.items()}
    
    async def _check_plugin_update(self, client: RegistryClient, plugin_id: str, 
                                 current_version: str) -> Optional[Tuple[str, PluginListing]]:
        
        try:
            versions = await client.get_plugin_versions(plugin_id)
            if not versions:
                return None
            
            latest_version = max(versions, key=lambda v: semver.VersionInfo.parse(v))
            
            if semver.VersionInfo.parse(latest_version) > semver.VersionInfo.parse(current_version):
                listing = await client.get_plugin_details(plugin_id, latest_version)
                if listing:
                    return plugin_id, listing
        
        except Exception as e:
            logger.debug(f"Update check failed for {plugin_id}: {e}")
        
        return None
    
    async def update_plugin(self, plugin_id: str, progress_callback: Optional[callable] = None) -> Tuple[bool, str]:
        if plugin_id not in self.available_updates:
            return False, "No update available"
        
        listing = self.available_updates[plugin_id]
        
        try:
            current_plugin = self.plugin_manager.active_plugins.get(plugin_id)
            if current_plugin:
                await self.plugin_manager.unload_plugin(plugin_id)
            
            success, message = await self.installer.install_from_listing(listing, progress_callback)
            
            if success:
                del self.available_updates[plugin_id]
                logger.info(f"Successfully updated plugin: {plugin_id}")
            else:
                if current_plugin:
                    await self.plugin_manager.load_plugin(plugin_id)
            
            return success, message
        
        except Exception as e:
            logger.error(f"Plugin update failed: {e}")
            return False, f"Update error: {e}"
    
    async def update_all_plugins(self, progress_callback: Optional[callable] = None) -> Dict[str, Tuple[bool, str]]:
        if not self.config.auto_update_enabled:
            return {}
        
        await self.check_for_updates(force=True)
        
        results = {}
        for plugin_id in list(self.available_updates.keys()):
            success, message = await self.update_plugin(plugin_id, progress_callback)
            results[plugin_id] = (success, message)
        
        return results


class PluginMarketplace:
    def __init__(self, plugin_manager, security_manager: SecurityManager, 
                 config: Optional[MarketplaceConfig] = None):
        
        self.plugin_manager = plugin_manager
        self.security_manager = security_manager
        self.config = config or MarketplaceConfig()
        
        self.trust_system = TrustSystem()
        self.installer = PluginInstaller(plugin_manager, security_manager, self.config)
        self.update_manager = UpdateManager(plugin_manager, self.installer, self.config)
        
        self.download_progress: Dict[str, DownloadProgress] = {}
        self.installation_history: List[Dict[str, Any]] = []
        
    async def search_plugins(self, query: str = "", **filters) -> List[PluginListing]:
        async with RegistryClient(self.config) as client:
            listings = await client.search_plugins(query, **filters)
            
            for listing in listings:
                listing.trust_score = self.trust_system.calculate_trust_score(listing)
            
            listings.sort(key=lambda x: x.trust_score, reverse=True)
            return listings
    
    async def get_plugin_details(self, plugin_id: str, version: Optional[str] = None) -> Optional[PluginListing]:
        async with RegistryClient(self.config) as client:
            listing = await client.get_plugin_details(plugin_id, version)
            if listing:
                listing.trust_score = self.trust_system.calculate_trust_score(listing)
            return listing
    
    async def install_plugin(self, plugin_id: str, version: Optional[str] = None) -> Tuple[bool, str]:
        def progress_callback(progress: DownloadProgress):
            self.download_progress[plugin_id] = progress
        
        success, message = await self.installer.install_from_marketplace(plugin_id, version, progress_callback)
        
        self.installation_history.append({
            'plugin_id': plugin_id,
            'version': version,
            'success': success,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        if plugin_id in self.download_progress:
            del self.download_progress[plugin_id]
        
        return success, message
    
    async def install_from_file(self, archive_path: Path) -> Tuple[bool, str]:
        return await self.installer.install_from_archive(archive_path)
    
    async def uninstall_plugin(self, plugin_id: str) -> Tuple[bool, str]:
        success, message = await self.installer.uninstall_plugin(plugin_id)
        
        self.installation_history.append({
            'plugin_id': plugin_id,
            'action': 'uninstall',
            'success': success,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return success, message
    
    async def check_for_updates(self) -> Dict[str, str]:
        return await self.update_manager.check_for_updates()
    
    async def update_plugin(self, plugin_id: str) -> Tuple[bool, str]:
        def progress_callback(progress: DownloadProgress):
            self.download_progress[plugin_id] = progress
        
        success, message = await self.update_manager.update_plugin(plugin_id, progress_callback)
        
        if plugin_id in self.download_progress:
            del self.download_progress[plugin_id]
        
        return success, message
    
    async def update_all_plugins(self) -> Dict[str, Tuple[bool, str]]:
        return await self.update_manager.update_all_plugins()
    
    async def submit_plugin_rating(self, plugin_id: str, rating: float, review: str) -> bool:
        rating_obj = PluginRating(
            user_id="current_user",
            rating=rating,
            review=review,
            version=self.plugin_manager.active_plugins[plugin_id].manifest.version
        )
        
        async with RegistryClient(self.config) as client:
            return await client.submit_rating(plugin_id, rating_obj)
    
    async def report_plugin(self, plugin_id: str, reason: str, details: str) -> bool:
        async with RegistryClient(self.config) as client:
            return await client.report_plugin(plugin_id, reason, details)
    
    def get_download_progress(self, plugin_id: str) -> Optional[DownloadProgress]:
        return self.download_progress.get(plugin_id)
    
    def get_installation_history(self) -> List[Dict[str, Any]]:
        return self.installation_history.copy()
    
    def get_marketplace_stats(self) -> Dict[str, Any]:
        return {
            'config': {
                'auto_update_enabled': self.config.auto_update_enabled,
                'verify_signatures': self.config.verify_signatures,
                'trust_level_threshold': self.config.trust_level_threshold
            },
            'stats': {
                'active_downloads': len(self.download_progress),
                'installation_history_count': len(self.installation_history),
                'developer_trust_scores': len(self.trust_system.developer_scores),
                'cached_entries': len(getattr(self, '_registry_cache', {}))
            }
        }


async def create_marketplace(plugin_manager, security_manager: SecurityManager, 
                           config: Optional[MarketplaceConfig] = None) -> PluginMarketplace:
    marketplace = PluginMarketplace(plugin_manager, security_manager, config)
    
    official_key = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2gD+6F8H9L4Q8l0mV5R1
...official marketplace public key...
-----END PUBLIC KEY-----"""
    
    marketplace.trust_system.register_developer_key("morpheus_official", official_key)
    
    return marketplace