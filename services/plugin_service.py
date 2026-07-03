"""Opt-in plugin loader skeleton.

There is intentionally no filesystem scanning or automatic startup loading.
"""

from importlib import import_module
from types import ModuleType
from typing import Iterable


class PluginService:
    """Track explicitly imported plugin modules without activating them."""

    def __init__(self) -> None:
        self._loaded: dict[str, ModuleType] = {}

    @property
    def loaded_plugins(self) -> tuple[str, ...]:
        return tuple(self._loaded)

    def load(self, module_names: Iterable[str] = ()) -> tuple[str, ...]:
        """Import only the supplied modules and return their plugin names."""
        loaded_now = []
        for module_name in module_names:
            module_name = str(module_name).strip()
            if not module_name:
                continue

            module = import_module(module_name)
            plugin_name = str(
                getattr(module, "PLUGIN_NAME", module_name)
            ).strip()
            if not plugin_name:
                raise ValueError(f"Plugin name is empty: {module_name}")

            self._loaded[plugin_name] = module
            loaded_now.append(plugin_name)
        return tuple(loaded_now)

    def get(self, plugin_name: str) -> ModuleType | None:
        return self._loaded.get(plugin_name)
