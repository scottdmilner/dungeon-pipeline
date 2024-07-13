import maya.cmds as cmds
from importlib import reload

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

    cmds.button(label="Update_Robin_Locators", command=Button_updateLocators)
    cmds.button(label="Eyeslids", command=Button_eyelids)
    cmds.button(label="Eyesockets", command=Button_eyesockets)

    cmds.showWindow(window)  # Show the window


createUI()
