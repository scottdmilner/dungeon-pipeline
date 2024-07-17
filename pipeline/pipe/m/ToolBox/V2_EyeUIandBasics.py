import maya.cmds as cmds
import maya.mel as mel


#    print("Check........................")
#    for obj in selected_objects:
#        print(obj)
#    print("End..........................")
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
        cmds.addAttr(obj,longName="face_bind_joint", attributeType="bool", defaultValue=True, keyable=False,
        )
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


def One_rayden_eyelidCurves(*args):
    print("Executing One_rayden_eyelidCurves function...")
    cmds.group(empty=True, name="eyelid_rayden_Curves")

    def turn_edges_to_curve(edgelist, curveName):
        if not edgelist:
            print("Edge list is empty. Please provide valid edges.")
            return

        cmds.select(edgelist, replace=True)  # Select the edges
        curve = cmds.polyToCurve(
            form=2,
            degree=1,
            conformToSmoothMeshPreview=0,
            constructionHistory=False,
            name=curveName,
        )[0]
        cmds.parent(curve, "eyelid_rayden_Curves")

    def loft_curves(curveOne, curveTwo, loftSurfaceName):
        surface = cmds.loft(curveOne, curveTwo, name=loftSurfaceName)[
            0
        ]  # loft command returns a list, so we take the first item
        return surface

    l_rayden_outer_edges = [
        "FaceAtOrigin.e[18619]",
        "FaceAtOrigin.e[18580]",
        "FaceAtOrigin.e[18583]",
        "FaceAtOrigin.e[18586]",
        "FaceAtOrigin.e[18589]",
        "FaceAtOrigin.e[18592]",
        "FaceAtOrigin.e[18595]",
        "FaceAtOrigin.e[18598]",
        "FaceAtOrigin.e[18601]",
        "FaceAtOrigin.e[18604]",
        "FaceAtOrigin.e[18607]",
        "FaceAtOrigin.e[18610]",
        "FaceAtOrigin.e[18613]",
        "FaceAtOrigin.e[18616]",
        "FaceAtOrigin.e[18619]",
        "FaceAtOrigin.e[18622]",
        "FaceAtOrigin.e[18625]",
        "FaceAtOrigin.e[18628]",
        "FaceAtOrigin.e[18631]",
        "FaceAtOrigin.e[18634]",
        "FaceAtOrigin.e[18637]",
        "FaceAtOrigin.e[18640]",
        "FaceAtOrigin.e[18643]",
        "FaceAtOrigin.e[18646]",
        "FaceAtOrigin.e[18649]",
        "FaceAtOrigin.e[18652]",
        "FaceAtOrigin.e[18655]",
        "FaceAtOrigin.e[18658]",
        "FaceAtOrigin.e[18661]",
    ]

    l_rayden_inner_edges = [
        "FaceAtOrigin.e[18615]",
        "FaceAtOrigin.e[18578]",
        "FaceAtOrigin.e[18582]",
        "FaceAtOrigin.e[18585]",
        "FaceAtOrigin.e[18588]",
        "FaceAtOrigin.e[18591]",
        "FaceAtOrigin.e[18594]",
        "FaceAtOrigin.e[18597]",
        "FaceAtOrigin.e[18600]",
        "FaceAtOrigin.e[18603]",
        "FaceAtOrigin.e[18606]",
        "FaceAtOrigin.e[18609]",
        "FaceAtOrigin.e[18612]",
        "FaceAtOrigin.e[18615]",
        "FaceAtOrigin.e[18618]",
        "FaceAtOrigin.e[18621]",
        "FaceAtOrigin.e[18624]",
        "FaceAtOrigin.e[18627]",
        "FaceAtOrigin.e[18630]",
        "FaceAtOrigin.e[18633]",
        "FaceAtOrigin.e[18636]",
        "FaceAtOrigin.e[18639]",
        "FaceAtOrigin.e[18642]",
        "FaceAtOrigin.e[18645]",
        "FaceAtOrigin.e[18648]",
        "FaceAtOrigin.e[18651]",
        "FaceAtOrigin.e[18654]",
        "FaceAtOrigin.e[18657]",
        "FaceAtOrigin.e[18660]",
    ]

    r_rayden_outer_edges = [
        "FaceAtOrigin.e[3962]",
        "FaceAtOrigin.e[3919]",
        "FaceAtOrigin.e[3923]",
        "FaceAtOrigin.e[3926]",
        "FaceAtOrigin.e[3929]",
        "FaceAtOrigin.e[3932]",
        "FaceAtOrigin.e[3935]",
        "FaceAtOrigin.e[3938]",
        "FaceAtOrigin.e[3941]",
        "FaceAtOrigin.e[3944]",
        "FaceAtOrigin.e[3947]",
        "FaceAtOrigin.e[3950]",
        "FaceAtOrigin.e[3953]",
        "FaceAtOrigin.e[3956]",
        "FaceAtOrigin.e[3959]",
        "FaceAtOrigin.e[3962]",
        "FaceAtOrigin.e[3965]",
        "FaceAtOrigin.e[3968]",
        "FaceAtOrigin.e[3971]",
        "FaceAtOrigin.e[3974]",
        "FaceAtOrigin.e[3977]",
        "FaceAtOrigin.e[3980]",
        "FaceAtOrigin.e[3983]",
        "FaceAtOrigin.e[3986]",
        "FaceAtOrigin.e[3989]",
        "FaceAtOrigin.e[3992]",
        "FaceAtOrigin.e[3995]",
        "FaceAtOrigin.e[3998]",
        "FaceAtOrigin.e[4000]",
    ]

    r_rayden_inner_edges = [
        "FaceAtOrigin.e[3960]",
        "FaceAtOrigin.e[3921]",
        "FaceAtOrigin.e[3924]",
        "FaceAtOrigin.e[3927]",
        "FaceAtOrigin.e[3930]",
        "FaceAtOrigin.e[3933]",
        "FaceAtOrigin.e[3936]",
        "FaceAtOrigin.e[3939]",
        "FaceAtOrigin.e[3942]",
        "FaceAtOrigin.e[3945]",
        "FaceAtOrigin.e[3948]",
        "FaceAtOrigin.e[3951]",
        "FaceAtOrigin.e[3954]",
        "FaceAtOrigin.e[3957]",
        "FaceAtOrigin.e[3960]",
        "FaceAtOrigin.e[3963]",
        "FaceAtOrigin.e[3966]",
        "FaceAtOrigin.e[3969]",
        "FaceAtOrigin.e[3972]",
        "FaceAtOrigin.e[3975]",
        "FaceAtOrigin.e[3978]",
        "FaceAtOrigin.e[3981]",
        "FaceAtOrigin.e[3984]",
        "FaceAtOrigin.e[3987]",
        "FaceAtOrigin.e[3990]",
        "FaceAtOrigin.e[3993]",
        "FaceAtOrigin.e[3996]",
        "FaceAtOrigin.e[3999]",
        "FaceAtOrigin.e[4001]",
    ]

    cmds.select(clear=True)

    # Convert edges to curves
    turn_edges_to_curve(l_rayden_outer_edges, "l_eyelid_outer_CRV")
    turn_edges_to_curve(l_rayden_inner_edges, "l_eyelid_inner_CRV")
    turn_edges_to_curve(r_rayden_outer_edges, "r_eyelid_outer_CRV")
    turn_edges_to_curve(r_rayden_inner_edges, "r_eyelid_inner_CRV")


def Two(*args):
    def look_controls(eyeball_jnt_name):
        print("look Control build")

        if eyeball_jnt_name.startswith("L_"):
            prefix = "l_"
        elif eyeball_jnt_name.startswith("R_"):
            prefix = "r_"
        else:
            prefix = ""
        old_suffix = "_JNT"
        new_suffix = "CTRL"
        control_name = eyeball_jnt_name.rsplit(old_suffix, 1)[0] + new_suffix
        cmds.circle(radius=1, name=control_name)

        center_offset_group = cmds.group(control_name, name=prefix + "eyelook_OFST")
        placement_Constraint = cmds.parentConstraint(
            eyeball_jnt_name, center_offset_group, maintainOffset=False
        )
        cmds.delete(placement_Constraint)

        cv_list = cmds.ls(control_name + ".cv[0:7]")
        cmds.select(cv_list)
        cmds.move(0, 0, 20, relative=True)
        clear_selection_list

        cmds.select(control_name)
        cmds.CenterPivot()

    look_controls("L_eye_JNT")
    look_controls("R_eye_JNT")
    cmds.aimConstraint(
        "L_eyeCTRL",
        "L_eye_JNT",
        maintainOffset=True,
        weight=1,
        aimVector=(0, 0, 1),
        upVector=(0, 1, 0),
        worldUpType="scene",
    )
    cmds.aimConstraint(
        "R_eyeCTRL",
        "R_eye_JNT",
        maintainOffset=True,
        weight=1,
        aimVector=(0, 0, 1),
        upVector=(0, 1, 0),
        worldUpType="scene",
    )

    def main_look_control():
        eye_Center_LOC = cmds.spaceLocator(name="eye_center_placement_LOC")[0]

        cmds.parentConstraint("R_eyeCTRL", eye_Center_LOC)
        cmds.parentConstraint("L_eyeCTRL", eye_Center_LOC)

        create_square_control("Look_Control", 4, 12, "z")

        placementConstraint = cmds.parentConstraint(
            "eye_center_placement_LOC", "Look_Control_OFST"
        )
        cmds.delete(placementConstraint)
        cv_list = cmds.ls(
            "topLook_ControlShape.cv[0:3]",
            "bottomLook_ControlShape.cv[0:3]",
            "leftLook_ControlShape.cv[0:3]",
            "rightLook_ControlShape.cv[0:3]",
        )
        cmds.select(cv_list)

        cmds.parent("l_eyelook_OFST", "Look_Control")
        cmds.parent("r_eyelook_OFST", "Look_Control")

        cmds.delete(eye_Center_LOC)

    main_look_control()

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

    loft_curves("l_eyelid_outer_CRV", "l_eyelid_inner_CRV", "l_eye_ribbon_surface")
    loft_curves("r_eyelid_outer_CRV", "r_eyelid_inner_CRV", "r_eye_ribbon_surface")

    def add_follicles_to_surface(Loft_Surface):
        cmds.select(Loft_Surface)
        mel.eval("createHair 29 1 10 0 0 1 0 5 0 1 2 1;")

    add_follicles_to_surface("l_eye_ribbon_surface")
    add_follicles_to_surface("r_eye_ribbon_surface")

    def Two_CleanupFollicles():
        cmds.rename("hairSystem1Follicles", "l_eyelidFollicles")
        cmds.rename("hairSystem2Follicles", "r_eyelidFollicles")
        cmds.delete("hairSystem1")
        cmds.delete("hairSystem2")
        cmds.delete("pfxHair1")
        cmds.delete("pfxHair2")
        cmds.delete("nucleus1")

        select_from_group("l_eyelidFollicles", "curve")
        delete_selected()
        select_from_group("r_eyelidFollicles", "curve")
        delete_selected()

        select_numerical_child_of_group("l_eyelidFollicles", -1)
        delete_selected()

        select_numerical_child_of_group("r_eyelidFollicles", -1)
        delete_selected()

        clear_selection_list()  # Ensure selected_objects list is cleared before reusing it

        select_all_in_group("l_eyelidFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "l_eyelid_JNT")
        clear_selection_list()

        select_all_in_group("r_eyelidFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "r_eyelid_JNT")
        clear_selection_list()

    Two_CleanupFollicles()

    def Two_eyelid_controls():
        l_eye_control_placement = [
            "l_eyelid_JNT_01",
            "l_eyelid_JNT_03",
            "l_eyelid_JNT_05",
            "l_eyelid_JNT_07",
            "l_eyelid_JNT_09",
            "l_eyelid_JNT_11",
            "l_eyelid_JNT_13",
            "l_eyelid_JNT_15",
            "l_eyelid_JNT_17",
            "l_eyelid_JNT_19",
            "l_eyelid_JNT_21",
            "l_eyelid_JNT_23",
            "l_eyelid_JNT_25",
            "l_eyelid_JNT_27",
        ]

        r_eye_control_placement = [
            "r_eyelid_JNT_01",
            "r_eyelid_JNT_03",
            "r_eyelid_JNT_05",
            "r_eyelid_JNT_07",
            "r_eyelid_JNT_09",
            "r_eyelid_JNT_11",
            "r_eyelid_JNT_13",
            "r_eyelid_JNT_15",
            "r_eyelid_JNT_17",
            "r_eyelid_JNT_19",
            "r_eyelid_JNT_21",
            "r_eyelid_JNT_23",
            "r_eyelid_JNT_25",
            "r_eyelid_JNT_27",
        ]

        cmds.group(empty=True, name="l_ctrl_jnts_GRP")
        cmds.select(l_eye_control_placement)
        cmds.duplicate()
        cmds.select("l_ctrl_jnts_GRP", add=True)
        cmds.parent()

        cmds.group(empty=True, name="r_ctrl_jnts_GRP")
        cmds.select(r_eye_control_placement)
        cmds.duplicate()
        cmds.select("r_ctrl_jnts_GRP", add=True)
        cmds.parent()

        def eyelid_control_placement(
            control_joint_group, sorting_group, eyeball_center_joint
        ):
            cmds.setAttr("L_eye_JNT.rotateZ", 0)
            cmds.setAttr("L_eye_JNT.rotateX", 0)
            cmds.setAttr("L_eye_JNT.rotateY", 0)
            # cmds.makeIdentity("L_eye_JNT", apply=True, translate=True, rotate=True, scale=False, normal=False)

            cmds.setAttr("R_eye_JNT.rotateZ", 0)
            cmds.setAttr("R_eye_JNT.rotateX", 0)
            cmds.setAttr("R_eye_JNT.rotateY", 0)
            # cmds.makeIdentity("R_eye_JNT", apply=True, translate=True, rotate=True, scale=False, normal=False)

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

                # Driver
                driver_name = "{}eyelid_{:02d}_driver".format(prefix, index + 1)
                cmds.group(empty=True, name=driver_name)
                driver_placement = cmds.parentConstraint(
                    eyeball_center_joint, driver_name
                )
                cmds.delete(driver_placement)
                cmds.parent(driver_name, sorting_group)

                # Offset
                offset_name = "{}eyelid_OFST_{:02d}".format(prefix, index + 1)
                cmds.group(empty=True, name=offset_name)
                offset_placement = cmds.parentConstraint(obj, offset_name)
                cmds.delete(offset_placement)
                cmds.parent(offset_name, driver_name)

                # Control
                eyelid_control_name = "{}eyelid_CTRL_{:02d}".format(prefix, index + 1)
                cmds.circle(radius=0.2, name=eyelid_control_name)
                control_placement = cmds.parentConstraint(obj, eyelid_control_name)
                cmds.delete(control_placement)
                cmds.parent(eyelid_control_name, offset_name)
                cmds.parentConstraint(eyelid_control_name, obj)

        cmds.group(empty=True, name="l_eyelid_ctrl_GRP")
        cmds.group(empty=True, name="r_eyelid_ctrl_GRP")

        eyelid_control_placement("l_ctrl_jnts_GRP", "l_eyelid_ctrl_GRP", "L_eye_JNT")
        eyelid_control_placement("r_ctrl_jnts_GRP", "r_eyelid_ctrl_GRP", "R_eye_JNT")

        select_all_in_group("l_ctrl_jnts_GRP")
        cmds.select("l_eye_ribbon_surface", add=True)
        cmds.skinCluster(tsb=True)

        select_all_in_group("r_ctrl_jnts_GRP")
        cmds.select("r_eye_ribbon_surface", add=True)
        cmds.skinCluster(tsb=True)

        def adding_blink_attributes(control_name):
            cmds.addAttr(
                control_name,
                longName="Blink",
                attributeType="double",
                minValue=-1,
                maxValue=1,
                defaultValue=0,
            )
            cmds.setAttr(control_name + "." + "Blink", keyable=True)

            cmds.addAttr(
                control_name,
                longName="Blink_Height",
                attributeType="double",
                minValue=-25,
                maxValue=25,
                defaultValue=0.2,
            )
            cmds.setAttr(control_name + "." + "Blink_Height", keyable=True)

            cmds.addAttr(
                control_name,
                longName="Blink_Influence",
                attributeType="double",
                minValue=0,
                maxValue=2,
                defaultValue=1,
            )
            cmds.setAttr(control_name + "." + "Blink_Influence", keyable=True)

            cmds.addAttr(
                control_name,
                longName="Eyelid_Follow",
                attributeType="double",
                minValue=0,
                maxValue=1,
                defaultValue=0.05,
            )
            cmds.setAttr(control_name + "." + "Eyelid_Follow", keyable=True)

        adding_blink_attributes("L_eyeCTRL")
        adding_blink_attributes("R_eyeCTRL")

        def setting_up_the_node_network(
            control_driver, eyelid_control, eye_center_joint
        ):
            suffix = find_suffix(control_driver)
            prefix = find_prefix(control_driver)
            print(
                "Driver: {}, Suffix: {}, Prefix: {}".format(
                    control_driver, suffix, prefix
                )
            )

            # Delete existing nodes if they exist
            delete_existing_nodes(
                "remapValue", prefix + "eyelid_control_remap_"
            )  # + suffix)
            delete_existing_nodes(
                "multiplyDivide", prefix + "eyelid_control_multi_"
            )  # + suffix)
            delete_existing_nodes(
                "plusMinusAverage", prefix + "blink_height_plusminus_"
            )  # + suffix)
            delete_existing_nodes(
                "plusMinusAverage", prefix + "eyelidFollow_plusminus_"
            )  # + suffix)
            delete_existing_nodes(
                "multiplyDivide", prefix + "eyelid_influence_multi_"
            )  # + suffix)

            # Create nodes
            remap_node = cmds.shadingNode(
                "remapValue", asUtility=True, name=prefix + "eyelid_control_remap_01"
            )  # + suffix)
            multiply_node = cmds.shadingNode(
                "multiplyDivide",
                asUtility=True,
                name=prefix + "eyelid_control_multi_01",
            )  # + suffix)
            heightAdd_node = cmds.shadingNode(
                "plusMinusAverage",
                asUtility=True,
                name=prefix + "blink_height_plusminus_01",
            )  # + suffix)
            eyelidFollow_node = cmds.shadingNode(
                "plusMinusAverage",
                asUtility=True,
                name=prefix + "eyelidFollow_plusminus_01",
            )  # + suffix)
            eyelidFollowInfluence_multi_node = cmds.shadingNode(
                "multiplyDivide",
                asUtility=True,
                name=prefix + "eyelid_influence_multi_01",
            )  # + suffix)

            # Connect nodes
            cmds.connectAttr(
                "{}.outValue".format(remap_node),
                "{}.input2X".format(multiply_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.outValue".format(remap_node),
                "{}.input2Y".format(multiply_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.outValue".format(remap_node),
                "{}.input2Z".format(multiply_node),
                force=True,
            )
            # .............cmds.connectAttr(eye_center_joint + '.rotate', '{}.input1'.format(multiply_node), force=True)
            cmds.connectAttr(
                "{}.output".format(multiply_node),
                control_driver + ".rotate",
                force=True,
            )
            cmds.connectAttr(
                "{}.Blink_Influence".format(eyelid_control),
                "{}.inputValue".format(remap_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Blink".format(eyelid_control),
                "{}.input1X".format(multiply_node),
                force=True,
            )

            cmds.connectAttr(
                "{}.Blink_Height".format(eyelid_control),
                "{}.input1D[0]".format(heightAdd_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Blink_Height".format(eyelid_control),
                "{}.input1D[1]".format(heightAdd_node),
                force=True,
            )
            cmds.disconnectAttr(
                "{}.Blink_Height".format(eyelid_control),
                "{}.input1D[1]".format(heightAdd_node),
            )

            # eyelidsFollow
            cmds.connectAttr(
                "{}.rotate".format(eye_center_joint),
                "{}.input3D[0]".format(eyelidFollow_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.output".format(multiply_node),
                "{}.input3D[1]".format(eyelidFollow_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.output3D".format(eyelidFollow_node),
                "{}.rotate".format(control_driver),
                force=True,
            )

            # follow influence
            cmds.connectAttr(
                "{}.rotate".format(eye_center_joint),
                "{}.input1".format(eyelidFollowInfluence_multi_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.output".format(eyelidFollowInfluence_multi_node),
                "{}.input3D[0]".format(eyelidFollow_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Eyelid_Follow".format(eyelid_control),
                "{}.input2X".format(eyelidFollowInfluence_multi_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Eyelid_Follow".format(eyelid_control),
                "{}.input2Y".format(eyelidFollowInfluence_multi_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Eyelid_Follow".format(eyelid_control),
                "{}.input2Z".format(eyelidFollowInfluence_multi_node),
                force=True,
            )

            # ......................................................................
            # setting the positions of each control for the blink
            # Tops/Corners
            def setRemap(remapNode, plusMinusNode):
                # Corners Outer
                if (
                    remapNode == "l_eyelid_control_remap_08"
                    or remapNode == "r_eyelid_control_remap_08"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 0
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)
                if (
                    remapNode == "l_eyelid_control_remap_07"
                    or remapNode == "r_eyelid_control_remap_07"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 10
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_06"
                    or remapNode == "r_eyelid_control_remap_06"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_05"
                    or remapNode == "r_eyelid_control_remap_05"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 23
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_04"
                    or remapNode == "r_eyelid_control_remap_04"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = 25
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_03"
                    or remapNode == "r_eyelid_control_remap_03"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 23
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_02"
                    or remapNode == "r_eyelid_control_remap_02"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)
                    # Corners Inner
                if (
                    remapNode == "l_eyelid_control_remap_01"
                    or remapNode == "r_eyelid_control_remap_01"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 0
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                # Bottoms
                if (
                    remapNode == "l_eyelid_control_remap_09"
                    or remapNode == "r_eyelid_control_remap_09"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -10
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_10"
                    or remapNode == "r_eyelid_control_remap_10"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_11"
                    or remapNode == "r_eyelid_control_remap_11"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -17
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_12"
                    or remapNode == "r_eyelid_control_remap_12"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_13"
                    or remapNode == "r_eyelid_control_remap_13"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -10
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_14"
                    or remapNode == "r_eyelid_control_remap_14"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -5
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                cmds.connectAttr(
                    "{}.output1D".format(heightAdd_node),
                    "{}.outputMax".format(remap_node),
                    force=True,
                )

            setRemap(remap_node, heightAdd_node)

        # ......................................................................
        select_children_in_group("l_eyelid_ctrl_GRP")
        add_to_selection_list()
        for driver in selected_objects:
            setting_up_the_node_network(driver, "L_eyeCTRL", "L_eye_JNT")

        select_children_in_group("r_eyelid_ctrl_GRP")
        add_to_selection_list()
        for driver in selected_objects:
            setting_up_the_node_network(driver, "R_eyeCTRL", "R_eye_JNT")

    Two_eyelid_controls()


def createUI():
    # Check if the window already exists and delete it if true
    if cmds.window("eyesWindow", exists=True):
        cmds.deleteUI("eyesWindow")

    # Create a new window
    window = cmds.window("eyesWindow", title="Eyes", widthHeight=(200, 100))

    # Create a layout for UI elements
    cmds.columnLayout(adj=True)

    # Create a button to build curves
    cmds.button(label="1. Build Curves", command=One_rayden_eyelidCurves)
    cmds.button(label="2. Eyelid Ribbon", command=Two)

    # Show the window
    cmds.showWindow(window)


createUI()
