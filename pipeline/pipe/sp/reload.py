import substance_painter_plugins as spp
from pipe.util import reload_pipe as _reload_pipe


def reload_pipe() -> None:
    sp_plugins = [
        spp.plugins["export"],
        spp.plugins["shelf"],
    ]
    _reload_pipe(sp_plugins)

    for plugin in sp_plugins:
        plugin.close_plugin()
        plugin.start_plugin()
