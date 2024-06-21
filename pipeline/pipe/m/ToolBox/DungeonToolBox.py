import maya.cmds as cmds

# Function to execute when the button is pressed
def button_pressed(*args):
    print("You pressed it!")

# Function to create the UI window
def create_ui():
    window_name = "PressMeWindow"
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
    
    cmds.window(window_name, title="Press Me Button", widthHeight=(200, 100))
    cmds.columnLayout(adjustableColumn=True)
    
    cmds.button(label="Press Me", command=button_pressed)
    
    cmds.showWindow(window_name)

# Create the UI
create_ui()
