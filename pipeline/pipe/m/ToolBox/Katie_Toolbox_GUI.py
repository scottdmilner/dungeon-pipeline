import maya.cmds as cmds
from importlib import reload


def grab_face_bind_joints(*args):
    import pipe.m.ToolBox.select_face_bind_joints

    reload(
        pipe.m.ToolBox.select_face_bind_joints
    )  # Optional: Reload the module if it has changed
    pipe.m.ToolBox.select_face_bind_joints.face_bind_selection()


def mark_face_bind_joints(*args):
    import pipe.m.ToolBox.add_bind_joint_attribute

    reload(
        pipe.m.ToolBox.add_bind_joint_attribute
    )  # Optional: Reload the module if it has changed
    pipe.m.ToolBox.add_bind_joint_attribute.add_joints()


def Button_updateLocators(*args):
    import pipe.m.ToolBox.Updating_Scripts

    reload(
        pipe.m.ToolBox.Updating_Scripts
    )  # Optional: Reload the module if it has changed
    pipe.m.ToolBox.Updating_Scripts.create_gui()


def Button_eyelids(*args):
    import pipe.m.ToolBox.V2_EyeUIandBasics

    reload(
        pipe.m.ToolBox.V2_EyeUIandBasics
    )  # Optional: Reload the module if it has changed
    pipe.m.ToolBox.V2_EyeUIandBasics.createUI()


def Button_eyesockets(*args):
    import pipe.m.ToolBox.EyeSocket_V1_01

    reload(
        pipe.m.ToolBox.EyeSocket_V1_01
    )  # Optional: Reload the module if it has changed
    pipe.m.ToolBox.EyeSocket_V1_01.eyesocket()


def createUI():
    import pipe.util as pu

    pu.reload_pipe()

    if cmds.window(
        "Katies_Toolbox", exists=True
    ):  # Check if the window already exists and delete it if true
        cmds.deleteUI("Katies_Toolbox")

    window = cmds.window(
        "Katies_Toolbox", title="Katies_Toolbox", widthHeight=(200, 100)
    )  # Create a new window

    cmds.columnLayout(adj=True)  # Create a layout for UI elements

    cmds.button(label="Mark as face bind joint", command=mark_face_bind_joints)
    cmds.button(label="Select face bind joints", command=grab_face_bind_joints)
    cmds.separator(height=10, style="none")  # Separate
    cmds.button(label="Base Locators", command=Button_updateLocators)
    cmds.button(label="Eyeslids", command=Button_eyelids)
    cmds.button(label="Eyesockets", command=Button_eyesockets)

    cmds.showWindow(window)  # Show the window


createUI()
