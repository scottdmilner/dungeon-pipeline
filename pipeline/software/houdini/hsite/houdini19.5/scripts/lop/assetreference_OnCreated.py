import hou

from pathlib import Path

from shared.util import get_production_path

"""This OnCreated hook runs whenever an Asset Reference node is created and 
   ensures that the filepath is always relative to $JOB"""


def update_filepath(
    node: hou.Node, parm_tuple: hou.ParmTuple, event_type: hou.nodeEventType, **kwargs
) -> None:
    if parm_tuple.name() != "filepath":
        return
    # this callback only needs to run once
    node.removeEventCallback([event_type], callback=update_filepath)  # type: ignore[list-item]

    path = Path(parm_tuple.evalAsStrings()[0])
    ppth = get_production_path()

    if not path.is_relative_to(ppth):
        if ppth.anchor == "G:\\":
            path = Path("G:/") / path.relative_to("/groups")
        else:
            path = Path("/groups") / path.relative_to("G:/")

    parm_tuple.set(("$JOB/" + str(path.relative_to(ppth)).replace("\\", "/"),))


def update_destination_prim(
    node: hou.Node, parm_tuple: hou.ParmTuple, event_type: hou.nodeEventType, **kwargs
) -> None:
    if parm_tuple.name() != "primpath":
        return
    # this callback only needs to run once
    node.removeEventCallback([event_type], callback=update_destination_prim)  # type: ignore[list-item]

    primpath = parm_tuple.evalAsStrings()[0]
    parm_tuple.set((f"`@PATH`{primpath}",))


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    for callback in (update_filepath, update_destination_prim):
        me.addEventCallback([hou.nodeEventType.ParmTupleChanged], callback=callback)
except Exception:  # in case this is created as a locked node
    pass
