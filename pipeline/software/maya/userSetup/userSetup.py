"""Initialize Maya environment on startup"""

import maya.cmds as mc


def main():
    # Enable required plugins
    plugins = [
        "mayaUsdPlugin",
    ]
    pluginInfo = mc.pluginInfo(q=True, listPlugins=True)
    for plugin in plugins:
        if plugin not in pluginInfo:
            mc.loadPlugin(plugin)

    from shared.util import get_production_path

    # set workspace
    mc.workspace(str(get_production_path().parent), openWorkspace=True)

    # enable timeline-marker plugin
    from timeline_marker import install  # type: ignore[import-not-found]

    install.execute()

    # register USD Export chaser
    import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]
    from pipe.m.usdchaser import ExportChaser

    mayaUsdLib.ExportChaser.Register(ExportChaser, ExportChaser.ID)


if not mc.about(batch=True):
    mc.evalDeferred(main)
