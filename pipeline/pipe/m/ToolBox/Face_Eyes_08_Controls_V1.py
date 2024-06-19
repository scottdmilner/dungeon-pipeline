# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds

# Creating the eyelid controls

eyelid_ctrl_group = cmds.group(empty=True, name="Eyelid_CTRLS")

LOC_Groups = [
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]

for eachGroup in LOC_Groups:
    group_objects = cmds.ls(eachGroup, dag=True)

    # Create a group for the eyelid control group
    group_ctrl_name = eachGroup.replace("_LOCS", "_CTRLS")
    cmds.group(empty=True, name=group_ctrl_name)

    for obj in group_objects:
        # Check if the object is a direct child of the group and ends with "Center" or "Secondary"
        if cmds.listRelatives(obj, parent=True) == [eachGroup] and obj.endswith(
            ("Center", "Secondary")
        ):
            circle_radius = 0.20  # Adjust the radius as needed
            circle_ctrl = cmds.circle(radius=circle_radius, normal=[1, 0, 0])[0]  # type: ignore[index]

            # Name the circle control after the object in the group
            circle_name = obj.replace("_LOC", "_CTRL")
            cmds.rename(circle_ctrl, circle_name)

            # Create a group for this individual control
            ctrl_group_name = circle_name.replace("_CTRL", "_OFST")
            cmds.group(empty=True, name=ctrl_group_name)

            # Parent the control to its individual group
            cmds.parent(circle_name, ctrl_group_name)
            cmds.parent(ctrl_group_name, group_ctrl_name)

            constraint = cmds.parentConstraint(obj, ctrl_group_name)
            cmds.delete(constraint)

            cmds.setAttr(
                circle_name + ".overrideEnabled", 1
            )  # Ensure override is enabled
            cmds.setAttr(
                circle_name + ".overrideColor", 17
            )  # Set control color to yellow
            cv_list = cmds.ls(circle_name + ".cv[0:7]")

# Creating the corner Controls
LOC_Groups = ["l_upper_Eyelid_LOCS", "r_upper_Eyelid_LOCS"]

for eachGroup in LOC_Groups:
    group_objects = cmds.ls(eachGroup, dag=True)

    # Create a group for the eyelid control group
    group_ctrl_name = eachGroup.replace("_LOCS", "_CTRLS")
    # cmds.group(empty=True, name=group_ctrl_name)

    for obj in group_objects:
        # Check if the object is a direct child of the group and ends with "Center" or "Secondary"
        if cmds.listRelatives(obj, parent=True) == [eachGroup] and obj.endswith(
            ("Corner")
        ):
            circle_radius = 0.20  # Adjust the radius as needed
            circle_ctrl = cmds.circle(radius=circle_radius, normal=[1, 0, 0])[0]  # type: ignore[index]

            # Name the circle control after the object in the group
            circle_name = obj.replace("_LOC", "_CTRL")
            cmds.rename(circle_ctrl, circle_name)

            # Create a group for this individual control
            ctrl_group_name = circle_name.replace("_CTRL", "_OFST")
            cmds.group(empty=True, name=ctrl_group_name)

            # Parent the control to its individual group
            cmds.parent(circle_name, ctrl_group_name)
            cmds.parent(ctrl_group_name, group_ctrl_name)

            constraint = cmds.parentConstraint(obj, ctrl_group_name)
            cmds.delete(constraint)

            cmds.setAttr(
                circle_name + ".overrideEnabled", 1
            )  # Ensure override is enabled
            cmds.setAttr(
                circle_name + ".overrideColor", 17
            )  # Set control color to yellow
            cv_list = cmds.ls(circle_name + ".cv[0:7]")

cmds.parent("l_upper_Eyelid_CTRLS", "Eyelid_CTRLS")
cmds.parent("l_lower_Eyelid_CTRLS", "Eyelid_CTRLS")
cmds.parent("r_upper_Eyelid_CTRLS", "Eyelid_CTRLS")
cmds.parent("r_lower_Eyelid_CTRLS", "Eyelid_CTRLS")


# Order the outliner
def reorder_group(group):
    children = cmds.listRelatives(group, children=True, fullPath=True) or []
    sorted_children = sorted(children)
    sorted_children.reverse()
    for index, child in enumerate(sorted_children):
        cmds.reorder(child, front=True)


group_names = [
    "l_upper_Eyelid_CTRLS",
    "l_lower_Eyelid_CTRLS",
    "r_lower_Eyelid_CTRLS",
    "r_lower_Eyelid_LOCS",
]
for group in group_names:
    reorder_group(group)


# Linking up the low res curves to the controls
# Creates Control joints for the locators that have been marked for controls


LOC_Groups = [
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]

# Create a group for all eyelid control joints
eyelid_ctrl_joints_group = cmds.group(empty=True, name="Eyelid_CTRL_JNTS")


def controlPlacement():
    for eachGroup in LOC_Groups:
        group_objects = cmds.ls(eachGroup, dag=True)

        # Create a group for the eyelid joint group
        group_joint_name = eachGroup.replace("_LOCS", "_CTRL_JNTS")
        cmds.group(empty=True, name=group_joint_name)

        for obj in group_objects:
            # Check if the object is a direct child of the group and ends with "Center", "Secondary", or "Corner" (if group contains "_upper")
            if cmds.listRelatives(obj, parent=True) == [eachGroup] and (
                obj.endswith(("Center", "Secondary"))
                or (eachGroup.find("_upper") != -1 and obj.endswith("Corner"))
            ):
                joint_name = obj.replace("_LOC", "_CTRL_JNT")
                cmds.select(clear=True)
                cmds.joint(name=joint_name, radius=0.2)
                constraint = cmds.pointConstraint(obj, joint_name)
                cmds.delete(constraint)

                # Parent the joint to the joint group
                cmds.parent(joint_name, group_joint_name)

        # Parent the group_joint_name to the main eyelid control joints group
        cmds.parent(group_joint_name, eyelid_ctrl_joints_group)


controlPlacement()
group_names = [
    "l_upper_Eyelid_CTRLS",
    "l_lower_Eyelid_CTRLS",
    "r_lower_Eyelid_CTRLS",
    "r_lower_Eyelid_LOCS",
]
for group in group_names:
    reorder_group(group)


# Parenting the Control joints to the Controls..........


def pair_children_of_groups(group1_name, group2_name):
    # Get the groups
    group1 = cmds.ls(group1_name)[0]
    group2 = cmds.ls(group2_name)[0]

    # Get children of the groups
    children_group1 = cmds.listRelatives(group1, children=True, fullPath=True) or []
    children_group2 = cmds.listRelatives(group2, children=True, fullPath=True) or []

    # Ensure both groups have the same number of children
    if len(children_group1) != len(children_group2):
        cmds.warning("Groups do not have the same number of children!")
        return

    # Pair children of the groups
    for child1, child2 in zip(children_group1, children_group2):
        cmds.select(clear=True)

        # Select the first child
        cmds.select(child1, add=True)
        cmds.pickWalk(direction="down")
        new_child1 = cmds.ls(selection=True)[0]
        cmds.select(clear=True)

        # Select the second child
        cmds.select(child2, add=True)
        new_child2 = cmds.ls(selection=True)[0]
        cmds.select(clear=True)

        # Print the pair
        print("Pair: {} - {}".format(new_child1, new_child2))

        # Create a parent constraint between the children
        cmds.parentConstraint(new_child1, new_child2)


# Call the function for the paired groups
pair_children_of_groups("l_upper_Eyelid_CTRLS", "l_upper_Eyelid_CTRL_JNTS")
pair_children_of_groups("l_lower_Eyelid_CTRLS", "l_lower_Eyelid_CTRL_JNTS")
pair_children_of_groups("r_upper_Eyelid_CTRLS", "r_upper_Eyelid_CTRL_JNTS")
pair_children_of_groups("r_lower_Eyelid_CTRLS", "r_lower_Eyelid_CTRL_JNTS")


def select_children_of_group(joint_group_name, curve_name):
    # Ensure the group exists
    if not cmds.objExists(joint_group_name):
        cmds.warning("Group '{}' does not exist.".format(joint_group_name))
        return

    # Get children of the group
    children = cmds.listRelatives(joint_group_name, children=True, fullPath=True)

    # Select children
    if children:
        cmds.select(children)
        print("Selected children of group '{}': {}".format(joint_group_name, children))

        # add the curve selection
        cmds.select(curve_name, add=True)
        cmds.skinCluster(children, curve_name)

    else:
        cmds.warning("Group '{}' has no children.".format(joint_group_name))


# Call binding the control joints to the low res curves
select_children_of_group("l_upper_Eyelid_CTRL_JNTS", "l_upper_Eyelid_LowRes_CRV")
select_children_of_group("l_lower_Eyelid_CTRL_JNTS", "l_lower_Eyelid_LowRes_CRV")

select_children_of_group("r_upper_Eyelid_CTRL_JNTS", "r_upper_Eyelid_LowRes_CRV")
select_children_of_group("r_lower_Eyelid_CTRL_JNTS", "r_lower_Eyelid_LowRes_CRV")


# Creating the look controls

cmds.select("Eyeballs")
cluster = cmds.cluster(n="LookControlCluster")

Eyes_look = cmds.nurbsSquare(
    c=(0, 0, 0), nr=(0, 0, 1), sl1=6, sl2=16, sps=1, d=3, ch=1, n="Look_CTRL"
)
cmds.select("rightLook_CTRLShape", r=True)
cmds.select("bottomLook_CTRLShape", add=True)
cmds.select("leftLook_CTRLShape", add=True)
cmds.select("topLook_CTRLShape", add=True)
cmds.select("Look_CTRL", add=True)

cmds.parent(relative=True, shape=True)

cmds.select("rightLook_CTRL", r=True)
cmds.select("bottomLook_CTRL", add=True)
cmds.select("leftLook_CTRL", add=True)
cmds.select("topLook_CTRL", add=True)
cmds.delete(cmds.ls(selection=True))
eyes_grp = cmds.group(Eyes_look, n="Eyes_look_OFST")

eye_look_constraint = cmds.parentConstraint("LookControlClusterHandle", eyes_grp)


left_eye_look = cmds.circle(radius=2, n="l_Eye_look")[0]  # type: ignore[index]
left_eye_grp = cmds.group(left_eye_look, n="l_Eye_look_OFST")
left_eye_constraint = cmds.parentConstraint("eye_l_bind_JNT", left_eye_grp)

right_eye_look = cmds.circle(radius=2, n="r_Eye_look")[0]  # type: ignore[index]
right_eye_grp = cmds.group(right_eye_look, n="r_Eye_look_OFST")
right_eye_constraint = cmds.parentConstraint("eye_r_bind_JNT", right_eye_grp)

cmds.delete(
    left_eye_constraint, right_eye_constraint, eye_look_constraint, "LookControlCluster"
)

cmds.parent("r_Eye_look_OFST", "Look_CTRL")
cmds.parent("l_Eye_look_OFST", "Look_CTRL")

cmds.select("Eyes_look_OFST", r=True)
cmds.move(0, 0, 25, relative=True)
