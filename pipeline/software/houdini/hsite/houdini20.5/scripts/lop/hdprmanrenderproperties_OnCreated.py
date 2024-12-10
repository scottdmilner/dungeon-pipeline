import hou

try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    resolutionx = me.parm("resolutionx")
    resolutiony = me.parm("resolutiony")
    aspectRatioConformPolicy = me.parm("aspectRatioConformPolicy")
    assert resolutionx is not None
    assert resolutiony is not None
    assert aspectRatioConformPolicy is not None
    resolutionx.set(1920)
    resolutiony.set(816)
    aspectRatioConformPolicy.set("cropAperture")
except Exception:  # in case this is created as a locked node
    pass
