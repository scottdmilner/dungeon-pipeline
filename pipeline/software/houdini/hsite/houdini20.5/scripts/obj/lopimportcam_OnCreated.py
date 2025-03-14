import hou

try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    resx = me.parm("resx")
    resy = me.parm("resy")
    assert resx is not None
    assert resy is not None
    # set the default resolution
    resx.set(1920)
    resy.deleteAllKeyframes()  # remove the expression
    resy.set(816)
except Exception:  # in case this is created as a locked node
    pass
