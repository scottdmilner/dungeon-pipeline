"""Initialize Maya environment on startup"""

import maya.cmds as mc


def main():
    if "mayaUsdPlugin" not in mc.pluginInfo(q=True, listPlugins=True):
        mc.loadPlugin("mayaUsdPlugin")


if not mc.about(batch=True):
    mc.evalDeferred(main)
