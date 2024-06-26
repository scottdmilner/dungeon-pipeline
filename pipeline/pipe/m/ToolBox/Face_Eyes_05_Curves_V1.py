# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds

# This script will create the first set of curves.
# Run the toolbox again and mark which locators you wish to have the main controls on
#    as well as the secondary controls
# Corners will be automatically marked based on the first and last loc in each group
#    however this should be correct based on previous selections


# High Res Curve Creation


# This is the high Res Curve
def create_curve_from_locators_highRes(group_name):
    # Get locators in the specified group
    locators = cmds.ls(group_name + "|*", type="transform")

    if not locators:
        cmds.warning("No locators found in the specified group: {}".format(group_name))
        return

    # Extract positions
    positions = [
        cmds.xform(loc, query=True, translation=True, worldSpace=True)
        for loc in locators
    ]

    # Create a curve
    curve = cmds.curve(degree=1, point=positions)

    # Name the curve
    curve_name = group_name.replace("_LOCS", "_HighRes_CRV")
    cmds.rename(curve, curve_name)

    # Convert selection to vertices
    cmds.ConvertSelectionToVertices()
    cmds.setToolTo("moveSuperContext")


# List of group names containing locators
group_names = [
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]  # Add more group names as needed

# Iterate over each group and create curve from locators
for group_name in group_names:
    create_curve_from_locators_highRes(group_name)


# Low Res Curve Creation


def create_curve_from_locators_lowRes(group_name):
    # Get locators in the specified group
    locators = cmds.ls(group_name + "|*", type="transform")

    if not locators:
        cmds.warning("No locators found in the specified group: {}".format(group_name))
        return

    # Filter locators by name endings
    locators = [
        loc
        for loc in locators
        if loc.endswith("_Corner")
        or loc.endswith("_Secondary")
        or loc.endswith("_Center")
    ]

    if not locators:
        cmds.warning(
            "No locators with valid endings found in the specified group: {}".format(
                group_name
            )
        )
        return

    # Extract positions
    positions = [
        cmds.xform(loc, query=True, translation=True, worldSpace=True)
        for loc in locators
    ]

    # Create an EP cubic curve
    curve = cmds.curve(degree=3, point=positions)

    # Snap curve edit points to locator positions (optional)
    for i, loc in enumerate(locators):
        cmds.move(
            positions[i][0],
            positions[i][1],
            positions[i][2],
            curve + ".cv[{}]".format(i),
            absolute=True,
        )

    # Name the curve
    curve_name = group_name.replace("_LOCS", "_LowRes_CRV")
    cmds.rename(curve, curve_name)

    # Convert selection to vertices (optional)
    cmds.ConvertSelectionToVertices()
    cmds.setToolTo("moveSuperContext")


# List of group names containing locators
group_names = [
    "l_upper_Eyelid_LOCS",
    "l_lower_Eyelid_LOCS",
    "r_upper_Eyelid_LOCS",
    "r_lower_Eyelid_LOCS",
]  # Add more group names as needed

# Iterate over each group and create curve from locators
for group_name in group_names:
    create_curve_from_locators_lowRes(group_name)


# Grouping the first set of curves

# Create the empty group
Eyelid_CRVS_FirstSet = cmds.group(empty=True, name="Eyelid_CRVS")


# Create a list I want to be grouped
l_first_curves_Group = [
    "l_upper_Eyelid_HighRes_CRV",
    "l_lower_Eyelid_HighRes_CRV",
    "l_upper_Eyelid_LowRes_CRV",
    "l_lower_Eyelid_LowRes_CRV",
]
# Create the empty group
l_Eyelid_CRVS_FirstSet = cmds.group(empty=True, name="l_Eyelid_CRVS")
# Parent the objects in my list to my group
for obj in l_first_curves_Group:
    cmds.parent(obj, l_Eyelid_CRVS_FirstSet)


r_first_curves_Group = [
    "r_upper_Eyelid_HighRes_CRV",
    "r_lower_Eyelid_HighRes_CRV",
    "r_upper_Eyelid_LowRes_CRV",
    "r_lower_Eyelid_LowRes_CRV",
]
r_Eyelid_CRVS_FirstSet = cmds.group(empty=True, name="r_Eyelid_CRVS")
for obj in r_first_curves_Group:
    cmds.parent(obj, r_Eyelid_CRVS_FirstSet)

cmds.parent(r_Eyelid_CRVS_FirstSet, "Eyelid_CRVS")
cmds.parent(l_Eyelid_CRVS_FirstSet, "Eyelid_CRVS")


l_Eyelid_crvs_High_GRP = cmds.group(
    "r_upper_Eyelid_HighRes_CRV",
    "r_lower_Eyelid_HighRes_CRV",
    name="r_Eyelid_crvs_High",
)
l_Eyelid_crvs_Low_GRP = cmds.group(
    "r_upper_Eyelid_LowRes_CRV", "r_lower_Eyelid_LowRes_CRV", name="r_Eyelid_crvs_Low"
)

l_Eyelid_crvs_High_GRP = cmds.group(
    "l_upper_Eyelid_HighRes_CRV",
    "l_lower_Eyelid_HighRes_CRV",
    name="l_Eyelid_crvs_High",
)
l_Eyelid_crvs_Low_GRP = cmds.group(
    "l_upper_Eyelid_LowRes_CRV", "l_lower_Eyelid_LowRes_CRV", name="l_Eyelid_crvs_Low"
)
