import maya.cmds as cmds


def add_joints(*args):
    # Get a list of selected objects
    selection = cmds.ls(selection=True)

    # Iterate over each selected object and add the boolean attribute
    for obj in selection:
        cmds.addAttr(
            obj,
            longName="face_bind_joint",
            attributeType="bool",
            defaultValue=True,
            keyable=False,
        )
