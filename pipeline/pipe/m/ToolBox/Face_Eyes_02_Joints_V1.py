# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds
import re


# Run after toolbox to select the upper and the lower eyelids.
# This script takes in a selection of vertices and builds a joint for each of them.

cmds.group(em=True, name="Eyelids")
cmds.group(em=True, name="Eyelid_JNTS")

cmds.group(em=True, name="Eyelid_LOCS")
cmds.parent("Eyelid_LOCS", "Eyelids")

cmds.group(em=True, name="r_Eyelid_JNTS")
cmds.group(em=True, name="r_upper_Eyelid_JNTS")
cmds.group(em=True, name="r_lower_Eyelid_JNTS")

cmds.group(em=True, name="l_Eyelid_JNTS")
cmds.group(em=True, name="l_upper_Eyelid_JNTS")
cmds.group(em=True, name="l_lower_Eyelid_JNTS")


# Function to create joints from selected vertices
def create_joints_from_selection(center, eyeGroups):
    created_joints = []  # Store the created joints in a list
    created_center_joints = []  # Store the created joints in a list
    # List all selected vertices
    vertex = cmds.ls(sl=True, fl=True)

    # Go through all vertices
    for v in vertex:
        # Joint on vertex (End Joints)
        cmds.select(cl=True)
        jnt = cmds.joint(radius=0.2)
        pos = cmds.xform(v, q=True, ws=True, t=True)
        cmds.xform(jnt, ws=True, t=pos)
        created_joints.append(
            (jnt, pos[0])
        )  # Add the created joint and its x-axis position to the list

        # Parent joint on eye center
        cmds.select(cl=True)
        jntCenter = cmds.joint(radius=0.2)
        posCenter = cmds.xform(center, q=True, ws=True, t=True)
        cmds.xform(jntCenter, ws=True, t=posCenter)
        created_center_joints.append(jntCenter)

        # Parent joints accordingly
        cmds.parent(jnt, jntCenter)
        cmds.parent(jntCenter, eyeGroups)

        # Orient center joint
        cmds.joint(
            jntCenter, e=True, oj="xyz", secondaryAxisOrient="yup", ch=True, zso=True
        )

    # Sort the created joints based on their x-axis position
    created_joints.sort(key=lambda x: abs(x[1]))

    return (
        created_joints,
        created_center_joints,
    )  # Return the list of created joints and center joints


cmds.select(cl=True)


def l_eyeLid_joints():
    cmds.select(cl=True)
    # Eye center joint
    center = "eye_l_bind_JNT"

    # l_upper_lid_selection
    eyeGroups = "l_upper_Eyelid_JNTS"
    selectStored("storedSelection_l_upper_eyelid")  # noqa: F821
    # Run the joint builder
    l_upper_joints, l_upper_center_joints = create_joints_from_selection(
        center, eyeGroups
    )
    for i, (jnt, _) in enumerate(l_upper_joints):
        cmds.rename(
            jnt, "l_upper_Eyelid_JNT_END_{:02d}".format(i + 1)
        )  # Rename the joints
    for i, jnt in enumerate(l_upper_center_joints):
        cmds.rename(
            jnt, "l_upper_Eyelid_JNT_{:02d}".format(i + 1)
        )  # Rename the center joints

    # l_lower_lid_selection
    eyeGroups = "l_lower_Eyelid_JNTS"
    selectStored("storedSelection_l_lower_eyelid")  # noqa: F821
    # Run the joint builder
    l_lower_joints, l_lower_center_joints = create_joints_from_selection(
        center, eyeGroups
    )
    for i, (jnt, _) in enumerate(l_lower_joints):
        cmds.rename(
            jnt, "l_lower_Eyelid_JNT_END_{:02d}".format(i + 2)
        )  # Rename the joints starting from "02"
    for i, jnt in enumerate(l_lower_center_joints):
        cmds.rename(
            jnt, "l_lower_Eyelid_JNT_{:02d}".format(i + 2)
        )  # Rename the center joints starting from "02"


# Function for right eyelid joints
def r_eyeLid_joints():
    cmds.select(cl=True)
    # Eye center joint
    center = "eye_r_bind_JNT"

    # r_upper_lid_selection
    eyeGroups = "r_upper_Eyelid_JNTS"
    selectStored("storedSelection_r_upper_eyelid")  # noqa: F821
    # Run the joint builder
    r_upper_joints, r_upper_center_joints = create_joints_from_selection(
        center, eyeGroups
    )
    for i, (jnt, _) in enumerate(r_upper_joints):
        cmds.rename(
            jnt, "r_upper_Eyelid_JNT_END_{:02d}".format(i + 1)
        )  # Rename the joints
    for i, jnt in enumerate(r_upper_center_joints):
        cmds.rename(
            jnt, "r_upper_Eyelid_JNT_{:02d}".format(i + 1)
        )  # Rename the center joints

    # r_lower_lid_selection
    eyeGroups = "r_lower_Eyelid_JNTS"
    selectStored("storedSelection_r_lower_eyelid")  # noqa: F821
    # Run the joint builder
    r_lower_joints, r_lower_center_joints = create_joints_from_selection(
        center, eyeGroups
    )
    for i, (jnt, _) in enumerate(r_lower_joints):
        cmds.rename(
            jnt, "r_lower_Eyelid_JNT_END_{:02d}".format(i + 2)
        )  # Rename the joints starting from "02"
    for i, jnt in enumerate(r_lower_center_joints):
        cmds.rename(
            jnt, "r_lower_Eyelid_JNT_{:02d}".format(i + 2)
        )  # Rename the center joints starting from "02"


# Call the functions
l_eyeLid_joints()
r_eyeLid_joints()

cmds.parent("r_Eyelid_JNTS", "Eyelid_JNTS")
cmds.parent("l_Eyelid_JNTS", "Eyelid_JNTS")

cmds.parent("l_upper_Eyelid_JNTS", "l_Eyelid_JNTS")
cmds.parent("l_lower_Eyelid_JNTS", "l_Eyelid_JNTS")

cmds.parent("r_upper_Eyelid_JNTS", "r_Eyelid_JNTS")
cmds.parent("r_lower_Eyelid_JNTS", "r_Eyelid_JNTS")

cmds.parent("Eyelid_JNTS", "Eyelids")

# Creating up Locators
cmds.spaceLocator(position=(3.842, 159, 4))
cmds.rename("locator1", "l_eyeLidUpVector_loc")
cmds.parent("l_eyeLidUpVector_loc", "Eyelid_LOCS")
cmds.xform(centerPivots=True)

cmds.spaceLocator(position=(-3.842, 159, 4))
cmds.rename("locator1", "r_eyeLidUpVector_loc")
cmds.parent("r_eyeLidUpVector_loc", "Eyelid_LOCS")
cmds.xform(centerPivots=True)


# Renaming and sorting joints


def rename_parent_with_child_number_from_group(group_name):
    # Get all children of the group
    parent_joints = cmds.listRelatives(group_name, children=True, fullPath=True) or []

    if not parent_joints:
        cmds.warning("Group '{}' has no children.".format(group_name))
        return

    # Iterate through each parent joint
    for parent_joint in parent_joints:
        # Get all children of the parent joint
        children = cmds.listRelatives(parent_joint, children=True, fullPath=True) or []

        if not children:
            cmds.warning("Parent joint '{}' has no children.".format(parent_joint))
            continue

        # Iterate through each child
        for child_joint in children:
            # Extract numbers from child joint's name
            child_numbers = re.findall(r"\d+", child_joint)
            if not child_numbers:
                cmds.warning(
                    "No numbers found in child joint '{}'.".format(child_joint)
                )
                continue

            # Get the base name of the parent joint without the hierarchy
            parent_name = parent_joint.split("|")[-1]
            parent_name_no_numbers = re.sub(r"\d+", "", parent_name)

            # Create a temporary name for the parent joint
            temp_name = parent_name_no_numbers + "_temp"

            # Rename parent joint to temporary name
            cmds.rename(parent_joint, temp_name)

            # Create the new name for the parent joint by appending the child number
            new_parent_name = parent_name_no_numbers + child_numbers[-1]

            # Rename parent joint to final name
            cmds.rename(temp_name, new_parent_name)


# Example usage
group_name = "r_upper_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)

group_name = "r_lower_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)

group_name = "l_upper_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)

group_name = "l_lower_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)

group_name = "r_upper_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)

group_name = "r_lower_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)

group_name = "l_upper_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)

group_name = "l_lower_Eyelid_JNTS"
rename_parent_with_child_number_from_group(group_name)


# This script will reorder any group in the outliner based on the names of the children


def reorder_group(group):
    # Get children of the group
    children = cmds.listRelatives(group, children=True, fullPath=True) or []

    # Sort children alphabetically
    sorted_children = sorted(children)

    # Reverse the sorted list to reorder from lowest to highest
    sorted_children.reverse()

    # Reorder children in the outliner
    for index, child in enumerate(sorted_children):
        cmds.reorder(child, front=True)


# List of four groups
group_names = [
    "r_upper_Eyelid_JNTS",
    "r_lower_Eyelid_JNTS",
    "l_upper_Eyelid_JNTS",
    "l_lower_Eyelid_JNTS",
]

# Call the function for each group
for group in group_names:
    reorder_group(group)
