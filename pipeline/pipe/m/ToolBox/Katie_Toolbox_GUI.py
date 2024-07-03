import maya.cmds as cmds
from importlib import reload


def test_button(*args):
    import pipe.m.ToolBox.V2_EyeUIandBasics

    reload(
        pipe.m.ToolBox.V2_EyeUIandBasics
    )  # Optional: Reload the module if it has changed
    pipe.m.ToolBox.V2_EyeUIandBasics.createUI()


def createUI():
    if cmds.window(
        "Katies_Toolbox", exists=True
    ):  # Check if the window already exists and delete it if true
        cmds.deleteUI("Katies_Toolbox")

    window = cmds.window(
        "Katies_Toolbox", title="Katies_Toolbox", widthHeight=(200, 100)
    )  # Create a new window

    cmds.columnLayout(adj=True)  # Create a layout for UI elements

    cmds.button(label="1. Eyes", command=test_button)  # Create a button to build curves

    cmds.showWindow(window)  # Show the window


createUI()
