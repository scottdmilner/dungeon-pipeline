import hou

try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    res_mode = me.parm("res_mode")
    resolution1 = me.parm("resolution1")
    resolution2 = me.parm("resolution2")
    aspectRatioConformPolicy = me.parm("aspectRatioConformPolicy")
    assert res_mode is not None
    assert resolution1 is not None
    assert resolution2 is not None
    assert aspectRatioConformPolicy is not None
    res_mode.set("manual")
    resolution1.set(1920)
    resolution2.set(816)
    aspectRatioConformPolicy.set("cropAperture")
except Exception:  # in case this is created as a locked node
    pass
