import hou

try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    primpath = me.parm("primpath")
    assert primpath is not None
    primpath.set("`@PATH`/$OS")
except Exception:  # in case this is created as a locked node
    pass
