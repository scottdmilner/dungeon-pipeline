import maya.cmds as cmds


# Function to create a locator at a specific position
def create_locator(name, x, y, z):
    locator = cmds.spaceLocator(name=name)[0]
    cmds.move(x, y, z, locator)


# Function to get the current position of the locator
def get_locator_position(locator_name):
    pos = cmds.xform(locator_name, query=True, translation=True, worldSpace=True)
    return pos


# Function to update the script with the new locator positions
def update_script():
    script_path = "pipe.m.toolbox.Robin_Face_Locators.py"
    with open(script_path, "w") as file:
        file.write("# Building the Face\n# Locators\n\n")
        file.write('import maya.cmds as cmds")\n\n')
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


# Function to create all locators at their specific positions
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
        "nose_l_nostril_bind_LOC": (0.495, 150.669, 8.234),
        "nose_r_nostril_bind_LOC": (-0.495, 150.669, 8.234),
        "nose_bottom_bind_LOC": (0, 150.425, 8.533),
        "nose_l_outer_nostril_bind_LOC": (1.451, 150.847, 7.997),
        "nose_r_outer_nostril_bind_LOC": (-1.451, 150.847, 7.997),
    }

    for locator_name, position in locator_positions.items():
        create_locator(locator_name, *position)
        cmds.parent(locator_name, "Locators")


# Function to create the GUI window
def create_gui():
    if cmds.window("locatorToolWindow", exists=True):
        cmds.deleteUI("locatorToolWindow", window=True)

    window = cmds.window(
        "locatorToolWindow", title="Locator Tool", widthHeight=(200, 100)
    )

    cmds.columnLayout(adjustableColumn=True)
    cmds.text(label="Create Locators:")
    cmds.button(
        label="Create Generic Locators", command=lambda *args: create_all_locators()
    )

    cmds.text(label="Update Script:")
    cmds.button(label="Update Robins Locator Positions", command=update_script_button)

    cmds.showWindow(window)


# Function to update the script with the new locator positions
def update_script_button(*args):
    update_script()


# Global variable to store locator names
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
    "nose_l_nostril_bind_LOC",
    "nose_r_nostril_bind_LOC",
    "nose_bottom_bind_LOC",
    "nose_l_outer_nostril_bind_LOC",
    "nose_r_outer_nostril_bind_LOC",
]

# Create the GUI
create_gui()
