"""
MORPHEUS CHAT - Plugin Marketplace & Community Integration
Enterprise-grade plugin distribution, verification, and community management system.
"""

import asyncio
import aiohttp
import hashlib
import json
import os
import shutil
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


class ListingStatus(str, Enum):
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


class MarketplaceNetworkDisabled(RuntimeError):
    """Raised when a registry call requires the network and the network is off."""


@dataclass
class MarketplaceConfig:
    """Distribution settings.

    Registry URLs default to empty. The previous defaults were hostnames this
    repository does not control. Leaving them populated would make a client
    trust whatever registered those names. Set `network_enabled` and an
    explicit URL together when an operator owns the registry.

    `local_registry_root` is the transport that works with the network off:
    a directory of plugin trees the embedding system already has on disk.
    """
    official_registry_url: str = ""
    community_registry_url: str = ""
    enterprise_registry_url: str = ""
    private_registry_url: str = ""
    local_registry_root: Optional[str] = None
    network_enabled: bool = False
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
    status: ListingStatus
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
    server_asserted_trust: float = 0.0
    signature_verified: bool = False
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
        """Score a listing from local evidence.

        A registry's self-reported `trust_score` is not an input. Provider
        bonuses apply only after a developer signature has verified. An
        unknown developer contributes nothing, so an unsigned listing stays
        under the default install threshold.
        """
        developer_score = self.developer_scores.get(listing.manifest.author, 0.0)
        base_score = developer_score * 0.3

        if listing.signature_verified:
            base_score += 0.45
            if listing.provider == MarketplaceProvider.OFFICIAL:
                base_score += 0.2
            elif listing.provider == MarketplaceProvider.ENTERPRISE:
                base_score += 0.15
            elif listing.provider == MarketplaceProvider.COMMUNITY:
                base_score += 0.05

            if listing.statistics.rating_count > 0:
                rating_factor = min(listing.statistics.rating_average / 5.0, 1.0)
                review_factor = min(listing.statistics.rating_count / 100.0, 1.0)
                base_score += rating_factor * review_factor * 0.2

            if listing.statistics.download_count > 1000:
                base_score += 0.1

        if listing.security_scan_results and listing.security_scan_results.risk_score > 0:
            security_factor = max(0.0, 1.0 - listing.security_scan_results.risk_score)
            base_score *= security_factor

        age_days = (datetime.now(timezone.utc) - listing.published_at).days
        if age_days > 365:
            base_score *= 0.9

        return min(base_score, 1.0)

    def verify_developer_signature(self, data: bytes, signature: str, developer_id: str) -> bool:
        if developer_id not in self.verification_keys:
            logger.error("No verification key registered for developer %s", developer_id)
            return False

        try:
            public_key = serialization.load_pem_public_key(self.verification_keys[developer_id])
        except Exception as exc:
            logger.error(
                "Verification key for %s is not a parseable PEM public key: %s",
                developer_id,
                type(exc).__name__,
            )
            return False

        try:
            signature_bytes = bytes.fromhex(signature)
        except ValueError:
            logger.error("Signature for %s is not hexadecimal", developer_id)
            return False

        try:
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
        except InvalidSignature:
            logger.warning("RSA-PSS signature mismatch for developer %s", developer_id)
            return False
        except Exception as exc:
            logger.error(
                "Signature verification error for %s: %s",
                developer_id,
                type(exc).__name__,
            )
            return False

    def register_developer_key(self, developer_id: str, public_key: bytes) -> None:
        if b"..." in public_key or b"official marketplace public key" in public_key.lower():
            raise ValueError(
                f"Refusing placeholder key material for developer {developer_id}"
            )
        try:
            serialization.load_pem_public_key(public_key)
        except Exception as exc:
            raise ValueError(
                f"Developer key for {developer_id} is not a PEM public key: {type(exc).__name__}"
            ) from exc
        self.verification_keys[developer_id] = public_key
        if developer_id not in self.developer_scores:
            self.developer_scores[developer_id] = 0.8


class RegistryClient:
    def __init__(
        self,
        config: MarketplaceConfig,
        cache: Optional[Dict[str, Tuple[datetime, Any]]] = None,
        trust_system: Optional[TrustSystem] = None,
    ):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        # The cache is owned by PluginMarketplace and shared across clients so
        # cache_duration_hours can outlive a single `async with` block.
        self.cache: Dict[str, Tuple[datetime, Any]] = cache if cache is not None else {}
        self.trust_system = trust_system

    def registry_base(self, provider: Optional[MarketplaceProvider]) -> str:
        selected = provider or MarketplaceProvider.OFFICIAL
        urls = {
            MarketplaceProvider.OFFICIAL: self.config.official_registry_url,
            MarketplaceProvider.COMMUNITY: self.config.community_registry_url,
            MarketplaceProvider.ENTERPRISE: self.config.enterprise_registry_url,
            MarketplaceProvider.PRIVATE: self.config.private_registry_url,
        }
        return (urls.get(selected) or "").rstrip("/")

    def _require_network(self, provider: Optional[MarketplaceProvider]) -> str:
        if not self.config.network_enabled:
            raise MarketplaceNetworkDisabled(
                "Marketplace network path is disabled. Set network_enabled and an "
                "explicit registry URL. Default hostnames were removed because this "
                "repository does not control them."
            )
        base = self.registry_base(provider)
        if not base:
            name = (provider or MarketplaceProvider.OFFICIAL).value
            raise MarketplaceNetworkDisabled(
                f"No registry URL configured for provider {name}"
            )
        return base
        
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
        
        if not self.config.network_enabled:
            listings = self._search_local(query, category, provider, channel)
            start = max(0, (page - 1) * limit)
            page_items = listings[start:start + limit]
            self._cache_result(cache_key, page_items)
            return page_items

        try:
            base = self._require_network(provider)
        except MarketplaceNetworkDisabled as exc:
            logger.error("%s", exc)
            return []

        url = f"{base}/api/v1/plugins/search"
        
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
        
        if not self.config.network_enabled:
            listing = self._local_listing(plugin_id, version)
            if listing is not None:
                self._cache_result(cache_key, listing)
            return listing

        try:
            base = self._require_network(None)
        except MarketplaceNetworkDisabled as exc:
            logger.error("%s", exc)
            return None

        url = f"{base}/api/v1/plugins/{plugin_id}"
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
        if not self.config.network_enabled:
            listing = self._local_listing(plugin_id, None)
            if listing is None:
                return []
            return [listing.manifest.version]

        try:
            base = self._require_network(None)
        except MarketplaceNetworkDisabled as exc:
            logger.error("%s", exc)
            return []

        url = f"{base}/api/v1/plugins/{plugin_id}/versions"
        
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('versions', [])
            else:
                return []
    
    async def download_plugin(self, listing: PluginListing, target_path: Path, 
                            progress_callback: Optional[callable] = None) -> bool:
        local_artifact = self._resolve_local_path(listing.download_url)
        byte_cap = self.config.max_download_size_mb * 1024 * 1024

        if local_artifact is not None:
            size = local_artifact.stat().st_size
            if size > byte_cap:
                logger.error("Plugin too large: %s bytes", size)
                return False
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local_artifact, target_path)
            if progress_callback:
                progress_callback(DownloadProgress(
                    plugin_id=listing.plugin_id,
                    total_bytes=size,
                    downloaded_bytes=size,
                    speed_bps=0,
                    eta_seconds=0,
                    status="completed",
                ))
            return True

        if not self.config.network_enabled:
            logger.error("Refusing network download while marketplace network is disabled")
            return False
        if self.session is None:
            logger.error("Registry session is not open")
            return False

        async with self.session.get(listing.download_url) as response:
            if response.status != 200:
                logger.error(f"Download failed: {response.status}")
                return False
            
            total_size = int(response.headers.get('Content-Length', 0))
            
            if total_size > byte_cap:
                logger.error(f"Plugin too large: {total_size} bytes")
                return False
            
            downloaded = 0
            start_time = datetime.now()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    downloaded += len(chunk)
                    if downloaded > byte_cap:
                        logger.error(
                            "Download exceeded cap after %s bytes (Content-Length was %s)",
                            downloaded,
                            total_size,
                        )
                        f.close()
                        target_path.unlink(missing_ok=True)
                        return False
                    f.write(chunk)
                    
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
                total_bytes=downloaded,
                downloaded_bytes=downloaded,
                speed_bps=0,
                eta_seconds=0,
                status="completed"
            ))
        
        return True
    
    async def verify_download(self, listing: PluginListing, file_path: Path) -> bool:
        """Authenticate an artifact with RSA-PSS.

        A same-origin SHA-256 comparison is not a signature. When signature
        verification is required, absence of a signature document fails closed
        unless `allow_unsigned_plugins` is set. A declared signature that
        cannot be loaded also fails closed — it is not treated as unsigned.
        """
        file_data = file_path.read_bytes()
        digest = hashlib.sha256(file_data).hexdigest()

        if not self.config.verify_signatures:
            listing.signature_verified = False
            return True

        if not listing.signature_url:
            listing.signature_verified = False
            return bool(self.config.allow_unsigned_plugins)

        try:
            signature_data = await self._load_signature_document(listing)
        except Exception as exc:
            logger.error("Signature document load failed: %s", type(exc).__name__)
            listing.signature_verified = False
            return False

        if signature_data is None:
            listing.signature_verified = False
            return False

        claimed_hash = signature_data.get("content_sha256")
        if claimed_hash and claimed_hash != digest:
            logger.error("Artifact hash does not match the signature document")
            listing.signature_verified = False
            return False

        algorithm = str(signature_data.get("algorithm", "")).lower().replace("-", "_")
        if algorithm != "rsa_pss_sha256":
            logger.error(
                "Algorithm %s does not authenticate the artifact; sha256 checksums are integrity only",
                algorithm or "<missing>",
            )
            listing.signature_verified = False
            return False

        if self.trust_system is None:
            logger.error("RSA signature present but no trust system is bound")
            listing.signature_verified = False
            return False

        signature = str(signature_data.get("signature", ""))
        if ":" in signature:
            signature = signature.split(":", 1)[1]
        developer_id = str(signature_data.get("developer_id") or listing.manifest.author)
        verified = self.trust_system.verify_developer_signature(file_data, signature, developer_id)
        listing.signature_verified = verified
        return verified

    async def _load_signature_document(self, listing: PluginListing) -> Optional[Dict[str, Any]]:
        local_signature = self._resolve_local_path(listing.signature_url or "")
        if local_signature is not None:
            with open(local_signature, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None

        if not self.config.network_enabled:
            logger.error("Signature URL is remote and the marketplace network is disabled")
            return None
        if self.session is None or not listing.signature_url:
            return None

        async with self.session.get(listing.signature_url) as response:
            if response.status != 200:
                return None
            data = await response.json()
            return data if isinstance(data, dict) else None

    def _resolve_local_path(self, url: str) -> Optional[Path]:
        if not url:
            return None
        if url.startswith("file://"):
            candidate = Path(url[7:])
        elif "://" in url:
            return None
        else:
            candidate = Path(url)
        if candidate.is_file():
            return candidate
        return None

    def _local_root(self) -> Optional[Path]:
        if not self.config.local_registry_root:
            return None
        root = Path(self.config.local_registry_root)
        if not root.is_dir():
            return None
        return root

    def _iter_local_plugins(self) -> List[Path]:
        root = self._local_root()
        if root is None:
            return []
        found: List[Path] = []
        for manifest_path in root.rglob("manifest.json"):
            if any(part.startswith(".") for part in manifest_path.relative_to(root).parts):
                continue
            found.append(manifest_path.parent)
        return found

    def _search_local(
        self,
        query: str,
        category: Optional[str],
        provider: Optional[MarketplaceProvider],
        channel: DistributionChannel,
    ) -> List[PluginListing]:
        matches: List[PluginListing] = []
        needle = query.lower().strip()
        for plugin_dir in self._iter_local_plugins():
            listing = self._listing_from_directory(plugin_dir)
            if listing is None:
                continue
            if provider and listing.provider != provider:
                continue
            if listing.channel != channel and channel != DistributionChannel.PUBLIC:
                continue
            if category and category not in listing.manifest.tags:
                continue
            haystack = " ".join([
                listing.plugin_id,
                listing.manifest.name,
                listing.manifest.description,
                listing.manifest.author,
            ]).lower()
            if needle and needle not in haystack:
                continue
            matches.append(listing)
        return matches

    def _local_listing(self, plugin_id: str, version: Optional[str]) -> Optional[PluginListing]:
        for plugin_dir in self._iter_local_plugins():
            listing = self._listing_from_directory(plugin_dir)
            if listing is None:
                continue
            if listing.plugin_id != plugin_id and listing.manifest.name != plugin_id:
                continue
            if version and listing.manifest.version != version:
                continue
            return listing
        return None

    def _listing_from_directory(self, plugin_dir: Path) -> Optional[PluginListing]:
        manifest_path = plugin_dir / "manifest.json"
        if not manifest_path.is_file():
            return None
        try:
            manifest = PluginManifest.from_file(manifest_path)
        except Exception as exc:
            logger.error("Local manifest %s rejected: %s", manifest_path, exc)
            return None

        artifact = plugin_dir / "artifact.zip"
        if not artifact.is_file():
            for candidate in plugin_dir.glob("*.zip"):
                artifact = candidate
                break
        signature = plugin_dir / "signature.json"
        provider_name = plugin_dir.parent.name if plugin_dir.parent != self._local_root() else "private"
        try:
            provider = MarketplaceProvider(provider_name)
        except ValueError:
            provider = MarketplaceProvider.PRIVATE

        return PluginListing(
            plugin_id=manifest.name,
            manifest=manifest,
            provider=provider,
            status=ListingStatus.APPROVED,
            channel=DistributionChannel.PUBLIC,
            download_url=str(artifact) if artifact.is_file() else "",
            signature_url=str(signature) if signature.is_file() else None,
            published_at=datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=timezone.utc),
            updated_at=datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=timezone.utc),
            trust_score=0.0,
        )
    
    async def submit_rating(self, plugin_id: str, rating: PluginRating) -> bool:
        try:
            base = self._require_network(None)
        except MarketplaceNetworkDisabled as exc:
            logger.error("%s", exc)
            return False

        url = f"{base}/api/v1/plugins/{plugin_id}/ratings"
        
        data = {
            'rating': rating.rating,
            'review': rating.review,
            'version': rating.version
        }
        
        async with self.session.post(url, json=data) as response:
            return response.status == 200
    
    async def report_plugin(self, plugin_id: str, reason: str, details: str) -> bool:
        try:
            base = self._require_network(None)
        except MarketplaceNetworkDisabled as exc:
            logger.error("%s", exc)
            return False

        url = f"{base}/api/v1/plugins/{plugin_id}/report"
        
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
            status=ListingStatus(data.get('status', 'approved')),
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
            trust_score=0.0,
            server_asserted_trust=float(data.get('trust_score', 0.0) or 0.0),
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
    def __init__(
        self,
        plugin_manager,
        security_manager: SecurityManager,
        config: MarketplaceConfig,
        trust_system: Optional[TrustSystem] = None,
        registry_cache: Optional[Dict[str, Tuple[datetime, Any]]] = None,
    ):
        self.plugin_manager = plugin_manager
        self.security_manager = security_manager
        self.config = config
        self.trust_system = trust_system or TrustSystem()
        self.registry_cache = registry_cache if registry_cache is not None else {}
        self.temp_dir = Path(tempfile.gettempdir()) / "morpheus_plugin_installs"
        self.temp_dir.mkdir(exist_ok=True)

    def _registry(self) -> RegistryClient:
        return RegistryClient(self.config, cache=self.registry_cache, trust_system=self.trust_system)
        
    async def install_from_marketplace(self, plugin_id: str, version: Optional[str] = None,
                                     progress_callback: Optional[callable] = None) -> Tuple[bool, str]:
        
        async with self._registry() as client:
            listing = await client.get_plugin_details(plugin_id, version)
            if not listing:
                return False, f"Plugin {plugin_id} not found in marketplace"
            
            return await self.install_from_listing(listing, progress_callback)
    
    async def install_from_listing(self, listing: PluginListing, 
                                 progress_callback: Optional[callable] = None) -> Tuple[bool, str]:
        temp_file = self.temp_dir / f"{listing.plugin_id}_{listing.manifest.version}.zip"
        trust_floor = self.config.trust_level_threshold / 5.0

        try:
            async with self._registry() as client:
                success = await client.download_plugin(listing, temp_file, progress_callback)
                if not success:
                    return False, "Download failed"

                if not await client.verify_download(listing, temp_file):
                    return False, "Download verification failed"

            listing.trust_score = self.trust_system.calculate_trust_score(listing)
            if listing.trust_score < trust_floor:
                return False, (
                    f"Plugin trust score too low: {listing.trust_score:.3f} "
                    f"(floor {trust_floor:.3f}). Server-asserted score "
                    f"{listing.server_asserted_trust:.3f} is not accepted."
                )

            extract_dir = self.temp_dir / f"{listing.plugin_id}_extracted"
            if extract_dir.exists():
                import shutil
                shutil.rmtree(extract_dir)
            extract_dir.mkdir()
            
            from security import safe_extract_zip
            safe_extract_zip(
                temp_file,
                extract_dir,
                max_uncompressed_bytes=self.config.max_download_size_mb * 1024 * 1024,
            )
            
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
            discovery = getattr(self.plugin_manager, "discovery", None)
            if discovery is not None and hasattr(discovery, "scan_plugin_directory"):
                await discovery.scan_plugin_directory(target_dir)

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
            from security import safe_extract_zip
            safe_extract_zip(
                archive_path,
                extract_dir,
                max_uncompressed_bytes=self.config.max_download_size_mb * 1024 * 1024,
            )
            
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
            discovery = getattr(self.plugin_manager, "discovery", None)
            if discovery is not None and hasattr(discovery, "scan_plugin_directory"):
                await discovery.scan_plugin_directory(target_dir)

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
        
        async with self.installer._registry() as client:
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
        self.registry_cache: Dict[str, Tuple[datetime, Any]] = {}
        self.installer = PluginInstaller(
            plugin_manager,
            security_manager,
            self.config,
            trust_system=self.trust_system,
            registry_cache=self.registry_cache,
        )
        self.update_manager = UpdateManager(plugin_manager, self.installer, self.config)
        self.download_progress: Dict[str, DownloadProgress] = {}
        self.installation_history: List[Dict[str, Any]] = []

    def _client(self) -> RegistryClient:
        return RegistryClient(
            self.config,
            cache=self.registry_cache,
            trust_system=self.trust_system,
        )

    async def search_plugins(self, query: str = "", **filters) -> List[PluginListing]:
        async with self._client() as client:
            listings = await client.search_plugins(query, **filters)
            
            for listing in listings:
                listing.trust_score = self.trust_system.calculate_trust_score(listing)
            
            listings.sort(key=lambda x: x.trust_score, reverse=True)
            return listings
    
    async def get_plugin_details(self, plugin_id: str, version: Optional[str] = None) -> Optional[PluginListing]:
        async with self._client() as client:
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
        
        async with self._client() as client:
            return await client.submit_rating(plugin_id, rating_obj)
    
    async def report_plugin(self, plugin_id: str, reason: str, details: str) -> bool:
        async with self._client() as client:
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
                'trust_level_threshold': self.config.trust_level_threshold,
                'network_enabled': self.config.network_enabled,
                'official_registry_configured': bool(self.config.official_registry_url),
                'community_registry_configured': bool(self.config.community_registry_url),
            },
            'stats': {
                'active_downloads': len(self.download_progress),
                'installation_history_count': len(self.installation_history),
                'developer_trust_scores': len(self.trust_system.developer_scores),
                'cached_entries': len(self.registry_cache),
                'registered_developer_keys': len(self.trust_system.verification_keys),
            }
        }


async def create_marketplace(plugin_manager, security_manager: SecurityManager, 
                           config: Optional[MarketplaceConfig] = None) -> PluginMarketplace:
    """Build a marketplace with no embedded trust root.

    Keys are loaded only from `SOMNUS_MARKETPLACE_TRUST_KEYS`, a directory of
    PEM public keys named `<developer_id>.pem`. Nothing in this repository is
    a trust anchor. The network path stays off unless the supplied config
    enables it.
    """
    marketplace = PluginMarketplace(plugin_manager, security_manager, config)
    keys_dir = os.environ.get("SOMNUS_MARKETPLACE_TRUST_KEYS")
    if keys_dir:
        root = Path(keys_dir)
        if root.is_dir():
            for pem_path in sorted(root.glob("*.pem")):
                marketplace.trust_system.register_developer_key(
                    pem_path.stem,
                    pem_path.read_bytes(),
                )
                logger.info("Registered marketplace trust key for %s", pem_path.stem)
        else:
            logger.error("SOMNUS_MARKETPLACE_TRUST_KEYS is not a directory")
    return marketplace