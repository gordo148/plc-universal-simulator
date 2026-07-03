from types import ModuleType

from services import plugin_service


def test_plugin_loader_loads_nothing_by_default(monkeypatch):
    imported = []
    monkeypatch.setattr(
        plugin_service,
        "import_module",
        lambda name: imported.append(name),
    )
    service = plugin_service.PluginService()

    assert service.load() == ()
    assert service.loaded_plugins == ()
    assert imported == []


def test_plugin_loader_imports_only_explicit_modules(monkeypatch):
    module = ModuleType("plugins.example_plugin")
    module.PLUGIN_NAME = "example-plugin"
    monkeypatch.setattr(
        plugin_service,
        "import_module",
        lambda name: module,
    )
    service = plugin_service.PluginService()

    assert service.load(["plugins.example_plugin"]) == ("example-plugin",)
    assert service.loaded_plugins == ("example-plugin",)
    assert service.get("example-plugin") is module
