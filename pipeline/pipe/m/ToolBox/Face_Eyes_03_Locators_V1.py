# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds

# This Creates the locators based on the joints and point constrains the joints to the locators

# Up vector object
upObject = "l_eyeLidUpVector_loc"

# List of joint groups to process
joint_groups = [
    "r_upper_Eyelid_JNTS",
    "r_lower_Eyelid_JNTS",
    "l_upper_Eyelid_JNTS",
    "l_lower_Eyelid_JNTS",
]  # Add more groups as needed

for joint_group in joint_groups:
    # Get all children of the joint group
    children = cmds.listRelatives(joint_group, ad=True, type="joint") or []

    # Select only joints ending with "_END_{:02d}"
    selection = [
        child
        for child in children
        if child.endswith("_END_{:02d}".format(int(child[-2:])))
    ]

    # Create a group for locators
    loc_group = cmds.group(empty=True, name=joint_group.replace("_JNTS", "_LOCS"))

    # For each joint
    start_index = 1
    if "lower" in joint_group:
        start_index = 2  # Change start index to 2 for lower group
    for index, eachItem in enumerate(selection, start=start_index):
        # Create locator and put it in position
        loc = cmds.spaceLocator()[0]
        cmds.scale(0.2, 0.2, 0.2, loc)
        pos = cmds.xform(eachItem, q=True, ws=True, t=True)
        cmds.xform(loc, ws=True, t=pos)

        # Get the parent of each joint selected
        itemParent = cmds.listRelatives(eachItem, p=True)[0]

        # Create an aim constraint to the locator
        cmds.aimConstraint(
            loc,
            itemParent,
            mo=True,
            weight=1,
            aimVector=(1, 0, 0),
            upVector=(0, 1, 0),
            worldUpType="object",
            worldUpObject=upObject,
        )

        # Rename the locator to match the group it's in
        loc_name = "{}_LOC_{:02d}".format(joint_group.replace("_JNTS", ""), index)
        loc = cmds.rename(loc, loc_name)

        # Parent the locator under the loc_group
        cmds.parent(loc, loc_group)

# Grouping left eyelid locators
cmds.group(em=True, name="l_Eyelid_LOCS")
cmds.parent("l_Eyelid_LOCS", "Eyelid_LOCS")

# Grouping right eyelid locators
cmds.group(em=True, name="r_Eyelid_LOCS")
cmds.parent("r_Eyelid_LOCS", "Eyelid_LOCS")

# Parenting each eyelid locators group to their respective side group
cmds.parent("r_upper_Eyelid_LOCS", "r_Eyelid_LOCS")
cmds.parent("r_lower_Eyelid_LOCS", "r_Eyelid_LOCS")

cmds.parent("l_upper_Eyelid_LOCS", "l_Eyelid_LOCS")
cmds.parent("l_lower_Eyelid_LOCS", "l_Eyelid_LOCS")


# Renames the components based on their order along the x-axis (use after creating the locators for each joint.)
# Also reorders the outliner properly so they go from lowest to highest


def bubble_sort(group):
    # Get the list of spheres in the group
    spheres = cmds.listRelatives(group, children=True, type="transform")

    # Flag to indicate whether a swap has occurred
    swapped = True

    # Perform bubble sort
    while swapped:
        swapped = False
        for i in range(len(spheres) - 1):
            # Get the x-axis positions of the current and next sphere
            current_pos = abs(
                cmds.xform(spheres[i], query=True, translation=True, worldSpace=True)[0]
            )
            next_pos = abs(
                cmds.xform(
                    spheres[i + 1], query=True, translation=True, worldSpace=True
                )[0]
            )

            # Swap names if the next sphere is further from 0 on the x-axis
            if current_pos > next_pos:
                # Get current and next sphere names
                current_name = cmds.ls(spheres[i], shortNames=True)[0]
                next_name = cmds.ls(spheres[i + 1], shortNames=True)[0]

                # Swap names
                cmds.rename(current_name, "temp_name")
                cmds.rename(next_name, current_name)
                cmds.rename("temp_name", next_name)

                # Set the flag to indicate a swap occurred
                swapped = True


# List of four groups
group_names = [
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]

# Call the function for each group
for group in group_names:
    bubble_sort(group)


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
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]

# Call the function for each group
for group in group_names:
    reorder_group(group)


#####Also creates the locators for the bottom corners...#####


def create_locator_at_position(object_name, group_name, suffix=""):
    # Get the position of the object
    position = cmds.xform(object_name, query=True, translation=True, worldSpace=True)

    # Extract the new name without 'S' at the end of 'LOCS'
    new_group_name = group_name[:-1] if group_name.endswith("S") else group_name

    # Create a locator at the position
    new_name = new_group_name.replace("_upper_", "_lower_") + suffix
    locator = cmds.spaceLocator(name=new_name)[0]
    cmds.scale(0.3, 0.3, 0.3, locator)

    cmds.xform(locator, translation=position, worldSpace=True)

    # Parent the locator under the corresponding group
    if new_name.startswith("l_"):
        cmds.parent(locator, "l_lower_Eyelid_LOCS")
    else:
        cmds.parent(locator, "r_lower_Eyelid_LOCS")


def select_first_and_last_elements_and_create_locators(group_name):
    # Get the list of children under the group
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []

    # Check if there are at least two children in the group
    if len(children) >= 2:
        # Select the first and last children
        cmds.select(children[0], children[-1], replace=True)

        # Create locators at the positions of the first and last children
        create_locator_at_position(children[0], group_name, "_01")
        create_locator_at_position(children[-1], group_name, "_02")


# Groups
group_names = ["r_upper_Eyelid_LOCS", "l_upper_Eyelid_LOCS"]

# Call the function for each group name
for group_name in group_names:
    select_first_and_last_elements_and_create_locators(group_name)


# List of four groups
group_names = [
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]

# Call the function for each group
for group in group_names:
    reorder_group(group)


# Select and mark the corners...

group_names = [
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]


def select_first_and_last_children(group_name):
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []
    if children:
        cmds.select(children[0], children[-1], add=True)


def add_corner_suffix(objects):
    for obj in objects:
        new_name = obj + "_Corner"
        cmds.rename(obj, new_name)


for group_name in group_names:
    select_first_and_last_children(group_name)

selected_objects = cmds.ls(selection=True) or []
add_corner_suffix(selected_objects)
