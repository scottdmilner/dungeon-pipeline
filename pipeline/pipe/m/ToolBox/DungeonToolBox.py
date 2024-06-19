import maya.cmds as cmds
import os

from importlib import reload

import pipe.m.ToolBox.Face_Eyes_02_Joints_V1 as joints

reload(joints)


# My Toolbox!

DEFAULT_SCRIPT_DIR = (
    "/users/animation/jonesk15/MyResources/Rigging/RiggingScripts/MyToolbox"
)


def createUI():
    print("Hello!")

    if cmds.window(
        "DungeonToolbox", exists=True
    ):  # Check if the window already exists, if so, delete it
        cmds.deleteUI("DungeonToolbox")

    window = cmds.window(
        "DungeonToolbox", title="My Dungeon Toolbox", widthHeight=(200, 100)
    )  # Create the window

    cmds.columnLayout(adjustableColumn=True)  # Create a layout for the UI elements

    # Create buttons
    # WELCOME
    cmds.button(label="Welcome to my Toolbox!", command=buttonCallback)
    cmds.separator(height=10, style="none")

    # GENERAL
    cmds.button(label="Swap Names", command=swap_names)
    cmds.button(label="Sort Group", command=reorder_group)
    cmds.separator(height=10, style="none")

    # FACE
    # 1. Structure Locators
    cmds.text(label="    Base Facial Construction:", align="left")
    cmds.button(
        "FaceOneToggleButton",
        label="1. Face Build - Locators",
        command=Face_One_toggleOptions,
    )
    # OneFaceOptions = cmds.button(
    #     "FaceOneOptions1",
    #     label="1. Face Build - Locators",
    #     backgroundColor=(0.2, 0.2, 0.2),
    #     visible=False,
    #     command=lambda *args: create_all_locators(),
    # )

    # 2. Structure Joints
    cmds.button(label="2. Face Build - Joints", command=Face_Builder_JNTS)
    cmds.separator(height=10, style="none")

    cmds.text(label="    Character Specific:", align="left")
    cmds.button(label="1. Robin Face Build - Locators", command=Face_Builder_LOCS)
    cmds.button(
        label="Update Robin Face Locator Positions (Optional)",
        command=update_script_button,
    )
    cmds.separator(height=10, style="none")

    # EYES
    # 1. Eyelid Placement
    cmds.button("toggleButton", label="1. Eye Build Placement", command=toggleOptions)
    cmds.separator(height=10, style="none")

    # additionalOptions = cmds.button(
    #     "additionalOptions8",
    #     label="View r_Lower",
    #     backgroundColor=(0.2, 0.2, 0.2),
    #     visible=False,
    #     command=lambda *args: selectStored("storedSelection_r_lower_eyelid"),
    # )

    # 2.button
    cmds.button(label="2. Eye Build Joints", command=eye_build_part_02)
    cmds.separator(height=10, style="none")

    # 3.button
    cmds.button(label="3. Eye Build Joints", command=eye_build_part_03)
    cmds.separator(height=10, style="none")

    cmds.button(label="Mark as Main/Center", command=markAsMainCenter)
    cmds.button(label="Mark as Secondary", command=markAsSecondary)
    cmds.button(label="Remove from Main/Secondary", command=removeFromMainSecondary)
    cmds.separator(height=10, style="none")

    cmds.showWindow(window)  # Show the window


def find_script_file(start_dir, script_filename):
    for root, dirs, files in os.walk(start_dir):
        if script_filename in files:
            return os.path.join(root, script_filename)
    return None


def buttonCallback(*args):
    print("Welcome!")


def swap_names(*args):
    selection = cmds.ls(selection=True)
    if len(selection) != 2:
        if len(selection) < 2:
            cmds.warning("Please select two objects.")
        else:
            cmds.warning("Please select only two objects.")
        return
    obj1_name = selection[0]
    obj2_name = selection[1]
    cmds.rename(obj1_name, "temp_name")
    cmds.rename(obj2_name, obj1_name)
    cmds.rename("temp_name", obj2_name)
    print("Names swapped successfully!")


def reorder_group(*args):
    selection = cmds.ls(selection=True)
    if not selection:
        cmds.warning("Please select a group to reorder.")
        return
    group = selection[0]
    children = cmds.listRelatives(group, children=True, fullPath=True) or []
    sorted_children = sorted(children)
    sorted_children.reverse()
    for index, child in enumerate(sorted_children):
        cmds.reorder(child, front=True)


def Face_Builder_LOCS(*args):
    SCRIPT_RELATIVE_PATH = "Character/Face/Robin_Face_Locators.py"
    script_path = os.path.join(DEFAULT_SCRIPT_DIR, SCRIPT_RELATIVE_PATH)
    print("Script path:", script_path)

    if os.path.exists(script_path):
        print("Script file found at:", script_path)
        exec(open(script_path).read())

        path = "/users/animation/jonesk15/MyResources/Rigging/RiggingScripts/MyToolbox/Character/Face/Face_Builder_LOCS.py"
        cmds.file(path, i=True)

    else:
        cmds.warning("Script file not found!")


def create_locator(name, x, y, z):
    locator = cmds.spaceLocator(name=name)[0]
    cmds.move(x, y, z, locator)


def get_locator_position(locator_name):
    pos = cmds.xform(locator_name, query=True, translation=True, worldSpace=True)
    return pos


def update_script():
    SCRIPT_RELATIVE_PATH = "Character/Face/Robin_Face_Locators.py"
    script_path = os.path.join(DEFAULT_SCRIPT_DIR, SCRIPT_RELATIVE_PATH)

    with open(script_path, "w") as file:
        file.write("# Building the Face\n# Locators\n\n")
        file.write('cmds.group(em=True, name="Locators")\n\n')

        file.write("def create_locator(name, x, y, z):\n")
        file.write("    locator = cmds.spaceLocator(name=name)[0]\n")
        file.write("    cmds.move(x, y, z, locator)\n")
        for locator_name in locator_names:
            pos = get_locator_position(locator_name)
            file.write(
                f'create_locator("{locator_name}", {pos[0]}, {pos[1]}, {pos[2]})\n'
            )
            file.write(f'cmds.parent("{locator_name}", "Locators")\n\n')
    locator_positions = create_all_locators()
    for locator_name, position in locator_positions.items():
        create_locator(locator_name, *position)
        cmds.parent(locator_name, "Locators")


def Face_Builder_JNTS(*args):
    SCRIPT_RELATIVE_PATH = "Character/Face/Face_Builder_Joints.py"
    script_path = os.path.join(DEFAULT_SCRIPT_DIR, SCRIPT_RELATIVE_PATH)
    print("Script path:", script_path)

    if os.path.exists(script_path):
        print("Script file found at:", script_path)
        exec(open(script_path).read())
    else:
        cmds.warning("Script file not found!")


def update_script_button(*args):
    update_script()


# Toggles
def toggleOptions(*args):
    buttonLabel = cmds.button(
        "toggleButton", query=True, label=True
    )  # Get the label of the toggle button

    if (
        buttonLabel == "1. Eye Build Placement"
    ):  # Toggle the label and behavior of the toggle button
        cmds.button("toggleButton", edit=True, label="1. Hide Options")
        showHideAdditionalOptions(True)

    else:
        cmds.button("toggleButton", edit=True, label="1. Eye Build Placement")
        showHideAdditionalOptions(False)


def showHideAdditionalOptions(visibility):
    for i in range(1, 9):
        cmds.button("additionalOptions{}".format(i), edit=True, visible=visibility)


cmds.window(title="Toggle Options", widthHeight=(300, 100))
cmds.columnLayout(adjustableColumn=True)

# Create additional options buttons
for i in range(1, 9):
    cmds.button(
        "additionalOptions{}".format(i),
        label="Option {}".format(i),
        backgroundColor=(0.2, 0.2, 0.2),
        visible=False,
    )


def Face_One_toggleOptions(*args):
    buttonLabel = cmds.button(
        "FaceOneToggleButton", query=True, label=True
    )  # Get the label of the toggle button

    if (
        buttonLabel == "1. Face Build - Locators"
    ):  # Toggle the label and behavior of the toggle button
        cmds.button("FaceOneToggleButton", edit=True, label="1. Hide Options")
        cmds.button("FaceOneOptions", edit=True, visible=True)
        for i in range(1, 2):
            cmds.button("FaceOneOptions{}".format(i), edit=True, visible=True)

    else:
        cmds.button("FaceOneToggleButton", edit=True, label="1. Eye Build Placement")
        cmds.button("FaceOneOptions", edit=True, visible=False)
        for i in range(1, 2):
            cmds.button("FaceOneOptions{}".format(i), edit=True, visible=False)


def addOrUpdateSelection(optionVarName):
    selected_objects = (
        cmds.ls(selection=True) or []
    )  # Get current selection or an empty list
    selection_string = ";".join(
        selected_objects
    )  # Convert list to a single string with ";" separator
    cmds.optionVar(stringValue=[optionVarName, selection_string])  # Store selection


def selectStored(optionVarName):
    selection_string = cmds.optionVar(
        query=optionVarName
    )  # Retrieve stored selection string
    if selection_string:
        stored_selection = selection_string.split(
            ";"
        )  # Split string back into list of objects
        cmds.select(stored_selection, replace=True)  # Select stored objects


def markAsMainCenter(*args):
    selection = cmds.ls(selection=True)
    if selection:
        for obj in selection:
            newName = obj + "_Center"
            if not cmds.objExists(newName):
                cmds.rename(obj, newName)
            else:
                cmds.warning("Object with suffix already exists: " + newName)
    else:
        cmds.warning("No objects selected!")


def markAsSecondary(*args):
    selection = cmds.ls(selection=True)
    if selection:
        for obj in selection:
            newName = obj + "_Secondary"
            if not cmds.objExists(newName):
                cmds.rename(obj, newName)
            else:
                cmds.warning("Object with suffix already exists: " + newName)
    else:
        cmds.warning("No objects selected!")


def removeFromMainSecondary(*args):
    selected_items = cmds.ls(selection=True)  # Get the currently selected items
    if not selected_items:
        cmds.warning("No objects selected.")
        return

    for item in selected_items:
        if item.endswith("_Center") or item.endswith("_Secondary"):
            new_name = (
                item[: -len("_Center")]
                if item.endswith("_Center")
                else item[: -len("_Secondary")]
            )
            cmds.rename(item, new_name)
            print(f"Renamed {item} to {new_name}")
        else:
            cmds.warning(
                f"Item {item} does not end with _Center or _Secondary. Skipping..."
            )


def eye_build_part_02(*args):
    SCRIPT_RELATIVE_PATH = (
        "Character/Face/Eyes/Face_Eyes_02_Joints_V1.py"  # Adjusted relative path
    )
    script_path = os.path.join(DEFAULT_SCRIPT_DIR, SCRIPT_RELATIVE_PATH)
    print("Script path:", script_path)  # Debugging print statement

    if os.path.exists(script_path):
        print("Script file found at:", script_path)
        exec(open(script_path).read())
    else:
        cmds.warning("Script file not found!")


def eye_build_part_03(*args):
    SCRIPT_RELATIVE_PATH = (
        "Character/Face/Eyes/Face_Eyes_03_Locators_V1.py"  # Adjusted relative path
    )
    script_path = os.path.join(DEFAULT_SCRIPT_DIR, SCRIPT_RELATIVE_PATH)
    print("Script path:", script_path)


def create_all_locators():
    cmds.group(em=True, name="Locators")

    locator_positions = {
        "skull_bind_LOC": (0, 148.946, -1.415),
        "face_upper_bind_LOC": (0, 148.535, -0.646),
        "head_tip_bind_LOC": (0, 156.237, 0.066),
        "brow_inner_l_bind_LOC": (1.532247, 157.231934, 8.437251),
        "brow_main_l_bind_LOC": (4.194504, 157.582428, 7.474292),
        "brow_peak_l_bind_LOC": (6.571188, 157.360886, 5.917207),
        "brow_inner_r_bind_LOC": (-1.532247, 157.231934, 8.437251),
        "brow_main_r_bind_LOC": (-4.194504, 157.582428, 7.474292),
        "brow_peak_r_bind_LOC": (-6.571189, 157.360886, 5.917207),
        "eyeSocket_r_bind_LOC": (-3.842108, 154.854385, 4.520485),
        "eye_r_bind_LOC": (-3.842108, 154.854385, 4.520485),
        "iris_r_bind_LOC": (-3.986634, 154.847443, 7.280398),
        "pupil_r_bind_LOC": (-3.986634, 154.847443, 7.280398),
        "eyeSocket_l_bind_LOC": (3.842108, 154.854385, 4.520485),
        "eye_l_bind_LOC": (3.842108, 154.854385, 4.520485),
        "iris_l_bind_LOC": (3.986634, 154.847443, 7.280398),
        "pupil_l_bind_LOC": (3.986634, 154.847443, 7.280398),
        "face_lower_bind_LOC": (0, 154.289, -0.867),
        "face_mid_bind_LOC": (0, 147.761, -0.203),
        "nose_bridge_bind_LOC": (0, 155.019, 7.697),
        "nose_bind_LOC": (0, 151.722, 9.133),
        "jaw_bind_LOC": (0, 150.539, -4.177),
        "jaw_end_bind_LOC": (0, 144.651, 7.095),
    }
    return locator_positions


locator_names = [
    "skull_bind_LOC",
    "face_upper_bind_LOC",
    "head_tip_bind_LOC",
    "brow_inner_l_bind_LOC",
    "brow_main_l_bind_LOC",
    "brow_peak_l_bind_LOC",
    "brow_inner_r_bind_LOC",
    "brow_main_r_bind_LOC",
    "brow_peak_r_bind_LOC",
    "eyeSocket_r_bind_LOC",
    "eye_r_bind_LOC",
    "iris_r_bind_LOC",
    "pupil_r_bind_LOC",
    "eyeSocket_l_bind_LOC",
    "eye_l_bind_LOC",
    "iris_l_bind_LOC",
    "pupil_l_bind_LOC",
    "face_lower_bind_LOC",
    "face_mid_bind_LOC",
    "nose_bridge_bind_LOC",
    "nose_bind_LOC",
    "jaw_bind_LOC",
    "jaw_end_bind_LOC",
]


# Call the function to create the UI
# createUI()
