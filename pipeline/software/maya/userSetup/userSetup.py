"""Initialize Maya environment on startup"""

import maya.cmds as mc
import pipe.util


def main():
    if "mayaUsdPlugin" not in mc.pluginInfo(q=True, listPlugins=True):
        mc.loadPlugin("mayaUsdPlugin")


if not mc.about(batch=True):
    mc.evalDeferred(main)

mc.workspace(str(pipe.util.get_production_path().parent), openWorkspace=True)
