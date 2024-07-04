"""Initialize Maya environment on startup"""

import maya.cmds as mc


def main():
    plugins = [
        "AbcExport",
        "mayaUsdPlugin",
    ]
    pluginInfo = mc.pluginInfo(q=True, listPlugins=True)

    for plugin in plugins:
        if plugin not in pluginInfo:
            mc.loadPlugin(plugin)

    import pipe

    mc.workspace(str(pipe.util.get_production_path().parent), openWorkspace=True)


if not mc.about(batch=True):
    mc.evalDeferred(main)
