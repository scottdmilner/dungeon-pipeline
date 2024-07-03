import maya.cmds as cmds
import maya.mel as mel

selected_objects = []


def add_to_selection_list():
    global selected_objects
    clear_selection_list()  # Clear the list before adding new objects
    selected_objects.extend(cmds.ls(selection=True, long=True))


def clear_selection_list():
    global selected_objects
    selected_objects = []


# Function to select all descendants of a group
def select_all_in_group(group_name):
    descendants = (
        cmds.listRelatives(group_name, allDescendents=True, fullPath=True) or []
    )
    if descendants:
        cmds.select(descendants, replace=True)


def select_children_in_group(group_name):
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []
    if children:
        cmds.select(children, replace=True)
    else:
        cmds.warning("No direct descendants found for {}.".format(group_name))


# Function to select descendants matching a name pattern in a group
def select_from_group(group_name, name_pattern):
    descendants = (
        cmds.listRelatives(group_name, allDescendents=True, fullPath=True) or []
    )
    if descendants:
        matching_descendants = [
            descendant
            for descendant in descendants
            if cmds.objectType(descendant) == "transform" and name_pattern in descendant
        ]
        if matching_descendants:
            cmds.select(matching_descendants, replace=True)


# Function to delete selected objects
def delete_selected():
    cmds.delete(cmds.ls(selection=True))


# Function to select a specific numerical child of a group
def select_numerical_child_of_group(group_name, specificChild):
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []
    if not children:
        print(f"No children found under group '{group_name}'.")
        return

    selected_child = children[specificChild]
    cmds.select(selected_child, replace=True)
    return selected_child


def create_joints_from_list(joint_radius, name_for_joint):
    selected_objects = cmds.ls(selection=True)  # Get currently selected objects
    index = 1  # Initialize index for numbering

    for obj in selected_objects:
        joint_name = f"{name_for_joint}_{index:02}"  # Append index to the joint name
        cmds.select(obj)
        cmds.joint(radius=joint_radius, name=joint_name)
        index += 1
        selected_objects.remove(obj)


def find_suffix(node_name):
    last_underscore_index = node_name.rfind("_")
    if last_underscore_index != -1:
        result = node_name[last_underscore_index + 1 :]
        return result
    else:
        return node_name


def find_prefix(node_name):
    parts = node_name.split("_", 1)

    if len(parts) > 1:
        prefix = parts[0] + "_"
        return prefix
    else:
        return ""


def delete_existing_nodes(node_type, node_name):
    existing_nodes = cmds.ls(type=node_type)
    for node in existing_nodes:
        if node_name in node:
            cmds.delete(node)


def create_square_control(control_name, length1, length2, normalDirection):
    if normalDirection == "x":
        normal_value = (1, 0, 0)
    elif normalDirection == "y":
        normal_value = (0, 1, 0)
    elif normalDirection == "z":
        normal_value = (0, 0, 1)

    square_Control = cmds.nurbsSquare(
        center=(0, 0, 0),
        name=control_name,
        normal=normal_value,
        sideLength1=length1,
        sideLength2=length2,
        spansPerSide=1,
        degree=3,
        constructionHistory=1,
    )

    cmds.select("right" + control_name + "Shape", r=True)
    cmds.select("bottom" + control_name + "Shape", add=True)
    cmds.select("left" + control_name + "Shape", add=True)
    cmds.select("top" + control_name + "Shape", add=True)
    cmds.select(control_name, add=True)

    cmds.parent(relative=True, shape=True)

    cmds.select("top" + control_name, r=True)
    cmds.select("left" + control_name, add=True)
    cmds.select("bottom" + control_name, add=True)
    cmds.select("right" + control_name, add=True)
    cmds.delete()

    cmds.group(square_Control, name=control_name + "_OFST")


def eyesocket():
    
    def loft_curves(curveOne, curveTwo, loftSurfaceName):
        surface = cmds.loft(
            curveOne,
            curveTwo,
            name=loftSurfaceName,
            constructionHistory=False,
            uniform=True,
            degree=3,
            sectionSpans=1,
            range=False,
            polygon=False,
            reverseSurfaceNormals=True,
        )[0]  # loft command returns a list, so we take the first item
        return surface

    loft_curves("l_eyesocket_outer_CRV", "l_eyesocket_inner_CRV", "l_eyesocket_ribbon_surface")
    loft_curves("r_eyesocket_outer_CRV", "r_eyesocet_inner_CRV", "r_eyesocket_ribbon_surface")
    
    def add_follicles_to_surface(Loft_Surface):
        cmds.select(Loft_Surface)
        mel.eval("createHair 29 1 10 0 0 1 0 5 0 1 2 1;")

    add_follicles_to_surface("l_eyesocket_ribbon_surface")
    add_follicles_to_surface("r_eyesocket_ribbon_surface")        

    def Two_CleanupFollicles():
        cmds.rename("hairSystem1Follicles", "l_eyesocketFollicles")
        cmds.rename("hairSystem2Follicles", "r_eyesocketFollicles")
        cmds.delete("hairSystem1")
        cmds.delete("hairSystem2")
        cmds.delete("pfxHair1")
        cmds.delete("pfxHair2")
        cmds.delete("nucleus1")

        select_from_group("l_eyesocketFollicles", "curve")
        delete_selected()
        select_from_group("r_eyesocketFollicles", "curve")
        delete_selected()

        select_numerical_child_of_group("l_eyesocketFollicles", -1)
        delete_selected()

        select_numerical_child_of_group("r_eyesocketFollicles", -1)
        delete_selected()

        clear_selection_list()  # Ensure selected_objects list is cleared before reusing it

        select_all_in_group("l_eyesocketFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "l_eyesocket_JNT")
        clear_selection_list()

        select_all_in_group("r_eyesocketFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "r_eyesocket_JNT")
        clear_selection_list()

    Two_CleanupFollicles()   
    
    def Two_eyesocket_controls():
        l_eyesocket_control_placement = [
            "l_eyesocket_JNT_01",
            "l_eyesocket_JNT_03",
            "l_eyesocket_JNT_05",
            "l_eyesocket_JNT_07",
            "l_eyesocket_JNT_09",
            "l_eyesocket_JNT_11",
            "l_eyesocket_JNT_13",
            "l_eyesocket_JNT_15",
            "l_eyesocket_JNT_17",
            "l_eyesocket_JNT_19",
            "l_eyesocket_JNT_21",
            "l_eyesocket_JNT_23",
            "l_eyesocket_JNT_25",
            "l_eyesocket_JNT_27",
        ]

        r_eyesocket_control_placement = [
            "r_eyesocket_JNT_01",
            "r_eyesocket_JNT_03",
            "r_eyesocket_JNT_05",
            "r_eyesocket_JNT_07",
            "r_eyesocket_JNT_09",
            "r_eyesocket_JNT_11",
            "r_eyesocket_JNT_13",
            "r_eyesocket_JNT_15",
            "r_eyesocket_JNT_17",
            "r_eyesocket_JNT_19",
            "r_eyesocket_JNT_21",
            "r_eyesocket_JNT_23",
            "r_eyesocket_JNT_25",
            "r_eyesocket_JNT_27",
        ] 
        
        cmds.group(empty=True, name="l_socket_ctrl_jnts_GRP")
        cmds.select(l_eyesocket_control_placement)
        cmds.duplicate()
        cmds.select("l_socket_ctrl_jnts_GRP", add=True)
        cmds.parent()

        cmds.group(empty=True, name="r_socket_ctrl_jnts_GRP")
        cmds.select(r_eyesocket_control_placement)
        cmds.duplicate()
        cmds.select("r_socket_ctrl_jnts_GRP", add=True)
        cmds.parent()  
        
    Two_eyesocket_controls()  # Call the function here (correct indentation)

    def eyesocket_control_placement(control_joint_group, sorting_group, eyeball_center_joint):
        select_all_in_group(control_joint_group)
        add_to_selection_list()
        for index, obj in enumerate(selected_objects):
            cmds.setAttr(obj + ".radius", 0.15)
            if control_joint_group.startswith("l_"):
                prefix = "l_"
            elif control_joint_group.startswith("r_"):
                prefix = "r_"
            else:
                prefix = ""

            # Offset
            offset_name = "{}eyesocket_OFST_{:02d}".format(prefix, index + 1)
            cmds.group(empty=True, name=offset_name)
            offset_placement = cmds.parentConstraint(obj, offset_name)
            cmds.delete(offset_placement)

            # Control
            eyesocket_control_name = "{}eyesocket_CTRL_{:02d}".format(prefix, index + 1)
            cmds.circle(radius=0.2, name=eyesocket_control_name)
            control_placement = cmds.parentConstraint(obj, eyesocket_control_name)
            cmds.delete(control_placement)
            
            clear_selection_list
            cv_list = cmds.ls(eyesocket_control_name + ".cv[0:7]")
            cmds.select(cv_list)
            cmds.move(0, 0, 0.25, relative=True)
            clear_selection_list
    
            cmds.select(eyesocket_control_name)
            cmds.CenterPivot()
            
            cmds.parent(eyesocket_control_name, offset_name)

            cmds.parentConstraint(eyesocket_control_name, obj, maintainOffset = True)
            cmds.parent(offset_name, sorting_group) 
            
    cmds.group(empty=True, name="l_eyesocket_ctrl_GRP")
    cmds.group(empty=True, name="r_eyesocket_ctrl_GRP")

    eyesocket_control_placement("l_socket_ctrl_jnts_GRP", "l_eyesocket_ctrl_GRP", "L_eye_JNT")
    eyesocket_control_placement("r_socket_ctrl_jnts_GRP", "r_eyesocket_ctrl_GRP", "R_eye_JNT")

    select_all_in_group("l_socket_ctrl_jnts_GRP")
    cmds.select("l_eyesocket_ribbon_surface", add=True)
    cmds.skinCluster(tsb=True)

    select_all_in_group("r_socket_ctrl_jnts_GRP")
    cmds.select("r_eyesocket_ribbon_surface", add=True)
    cmds.skinCluster(tsb=True)

eyesocket()
