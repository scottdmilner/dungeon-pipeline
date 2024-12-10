import hou

try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    tabmenumask = me.parm("tabmenumask")
    assert tabmenumask is not None
    tabmenumask.set("risnet USD  ^hmtlx* MaterialX collect parameter subnet")
except Exception:  # in case this is created as a locked node
    pass
