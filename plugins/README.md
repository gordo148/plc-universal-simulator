# Plugin Package

## v2.2 status

Plugin support is architectural scaffolding only. No plugins are bundled,
discovered, loaded, or activated by the desktop application.

This package is reserved for optional future extensions. The application does
not discover, import, or activate plugins during startup.

## Proposed structure

```text
plugins/
    example_plugin/
        __init__.py
        plugin.py
        README.md
```

A future plugin module should expose a stable plugin name and keep imports free
of side effects:

```python
PLUGIN_NAME = "example-plugin"


def register(application):
    """Register the plugin when explicitly activated by the application."""
```

The loader skeleton in `services/plugin_service.py` only imports module names
that are explicitly passed to it. Calling it without module names loads
nothing. Automatic discovery, lifecycle hooks, UI registration, permissions,
configuration, and plugin activation are intentionally out of scope for this
phase.

Plugins should interact with tags and runtime values through the existing
application services. They should not create independent tag databases or
bypass `PLCService`.
