"""v12 Plugin Manager.

Enables third-party extensibility through a Python entry-point based plugin system.
Plugins can extend: intelligence sources, social platforms, payment gateways,
logistics providers, and custom AI agents.
"""

from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class PluginCategory(Enum):
    INTELLIGENCE_SOURCE = "intelligence_source"
    SOCIAL_PLATFORM = "social_platform"
    PAYMENT_GATEWAY = "payment_gateway"
    LOGISTICS_PROVIDER = "logistics_provider"
    AI_AGENT = "ai_agent"
    CONTENT_GENERATOR = "content_generator"
    ANALYTICS = "analytics"
    CUSTOM = "custom"


@dataclass
class PluginManifest:
    name: str
    version: str
    category: PluginCategory
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class IPlugin(Protocol):
    """Protocol that all plugins must implement."""

    @property
    def manifest(self) -> PluginManifest: ...

    def initialize(self, config: dict[str, Any]) -> bool: ...

    def health_check(self) -> dict[str, Any]: ...

    def shutdown(self) -> None: ...


class BasePlugin(ABC):
    """Base class for plugins with sensible defaults."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._initialized = False

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        ...

    def initialize(self, config: dict[str, Any]) -> bool:
        self._config = config
        self._initialized = True
        logger.info("Plugin '%s' v%s initialized", self.manifest.name, self.manifest.version)
        return True

    def health_check(self) -> dict[str, Any]:
        return {
            "name": self.manifest.name,
            "status": "healthy" if self._initialized else "not_initialized",
            "version": self.manifest.version,
        }

    def shutdown(self) -> None:
        self._initialized = False
        logger.info("Plugin '%s' shut down", self.manifest.name)


class PluginManager:
    """Central registry and lifecycle manager for all plugins."""

    def __init__(self, plugin_dir: str | Path = "backend/plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, IPlugin] = {}
        self._by_category: dict[PluginCategory, list[str]] = {
            cat: [] for cat in PluginCategory
        }

    def register(self, plugin: IPlugin) -> bool:
        """Register a plugin instance."""
        name = plugin.manifest.name
        if name in self._plugins:
            logger.warning("Plugin '%s' already registered, replacing", name)
        self._plugins[name] = plugin
        self._by_category[plugin.manifest.category].append(name)
        logger.info("Plugin registered: %s (category: %s)", name, plugin.manifest.category.value)
        return True

    def initialize_all(self, configs: dict[str, dict[str, Any]] | None = None) -> dict[str, bool]:
        """Initialize all registered plugins."""
        configs = configs or {}
        results: dict[str, bool] = {}
        for name, plugin in self._plugins.items():
            try:
                cfg = configs.get(name, {})
                results[name] = plugin.initialize(cfg)
            except Exception as exc:
                logger.exception("Failed to initialize plugin '%s': %s", name, exc)
                results[name] = False
        return results

    def get_plugin(self, name: str) -> IPlugin | None:
        return self._plugins.get(name)

    def list_plugins(self, category: PluginCategory | None = None) -> list[PluginManifest]:
        if category:
            return [self._plugins[n].manifest for n in self._by_category.get(category, [])]
        return [p.manifest for p in self._plugins.values()]

    def health_check_all(self) -> dict[str, dict[str, Any]]:
        return {name: plugin.health_check() for name, plugin in self._plugins.items()}

    def shutdown_all(self) -> None:
        for name, plugin in self._plugins.items():
            try:
                plugin.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down plugin '%s': %s", name, exc)

    def discover_from_directory(self) -> int:
        """Auto-discover plugins from the plugin directory."""
        count = 0
        if not self.plugin_dir.exists():
            return count

        for item in self.plugin_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                try:
                    module_name = f"backend.plugins.{item.name}"
                    module = importlib.import_module(module_name)
                    if hasattr(module, "create_plugin"):
                        plugin = module.create_plugin()
                        self.register(plugin)
                        count += 1
                except Exception as exc:
                    logger.warning("Failed to load plugin from '%s': %s", item.name, exc)
        return count

    def discover_from_entry_points(self, group: str = "global_intelligence.plugins") -> int:
        """Discover plugins via Python entry_points."""
        count = 0
        try:
            from importlib.metadata import entry_points
            for ep in entry_points(group=group):
                try:
                    factory = ep.load()
                    plugin = factory()
                    self.register(plugin)
                    count += 1
                except Exception as exc:
                    logger.warning("Failed to load entry_point plugin '%s': %s", ep.name, exc)
        except Exception as exc:
            logger.warning("Entry point discovery failed: %s", exc)
        return count


# Singleton
_plugin_manager: PluginManager | None = None


def get_plugin_manager(plugin_dir: str | None = None) -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager(plugin_dir or "backend/plugins")
    return _plugin_manager
