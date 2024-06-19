# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds


def select_objects_with_suffix(group_names, suffix):
    selected_objects = []
    for group_name in group_names:
        objects_in_group = cmds.ls(group_name, dag=True, type="transform")
        for obj in objects_in_group:
            if obj.endswith(suffix):
                selected_objects.append(obj)
                # Check if the object is in an "_upper_" group
                if "_upper_" in group_name:
                    cmds.addAttr(
                        obj,
                        longName="blinkHeight",
                        attributeType="float",
                        defaultValue=0.2,
                        minValue=0,
                        maxValue=1,
                        keyable=True,
                    )
                    cmds.addAttr(
                        obj,
                        longName="blink",
                        attributeType="float",
                        defaultValue=0,
                        minValue=0,
                        maxValue=1,
                        keyable=True,
                    )
                if "_lower_" in group_name:
                    cmds.addAttr(
                        obj,
                        longName="blink",
                        attributeType="float",
                        defaultValue=0,
                        minValue=0,
                        maxValue=1,
                        keyable=True,
                    )
    cmds.select(selected_objects, replace=True)
    # Adding Enum attribute "SMART_BLINK" to each selected object
    for obj in selected_objects:
        cmds.addAttr(
            obj,
            longName="SMART_BLINK",
            attributeType="enum",
            enumName="_____",
            keyable=True,
        )


# List of group names to search through
group_names = [
    "l_upper_Eyelid_CTRLS",
    "l_lower_Eyelid_CTRLS",
    "r_upper_Eyelid_CTRLS",
    "r_lower_Eyelid_CTRLS",
]

# Suffix to filter objects by
suffix = "_Center"

select_objects_with_suffix(group_names, suffix)


# Duplicating curves to get the blink curves
cmds.select("r_upper_Eyelid_LowRes_CRV", replace=True)
cmds.select("l_upper_Eyelid_LowRes_CRV", add=True)
duplicated_objects = cmds.duplicate(returnRootsOnly=True)
for obj in duplicated_objects:
    new_name = obj.replace("_upper_", "_blink_")
    new_name = new_name[:-1] if new_name.endswith("1") else new_name
    cmds.rename(obj, new_name)


def create_blendshape(prefix):
    # Selecting target and blend shapes
    cmds.select(prefix + "upper_Eyelid_LowRes_CRV", replace=True)
    cmds.select(prefix + "lower_Eyelid_LowRes_CRV", add=True)
    cmds.select(prefix + "blink_Eyelid_LowRes_CRV", add=True)
    cmds.blendShape()

    # Renaming blendShape node
    cmds.select(cl=True)
    cmds.select(prefix + "blink_Eyelid_LowRes_CRV", replace=True)
    cmds.select("blendShape1", add=True)
    cmds.rename("blendShape1", prefix + "blink_Eyelid_LowRes_BLEND")


# Create blendShapes for both sides
create_blendshape("r_")
create_blendshape("l_")


def connect_blendshape_to_height(prefix):
    # Selecting objects
    cmds.select(prefix + "upper_Eyelid_CTRL_07_Center", replace=True)
    cmds.select(prefix + "blink_Eyelid_LowRes_CRV", replace=True)
    cmds.select(prefix + "blink_Eyelid_LowRes_BLEND", add=True)

    # Connecting attributes
    cmds.connectAttr(
        prefix + "upper_Eyelid_CTRL_07_Center.blinkHeight",
        prefix + "blink_Eyelid_LowRes_BLEND." + prefix + "upper_Eyelid_LowRes_CRV",
        force=True,
    )

    # Creating reverse node
    reverse_node = cmds.shadingNode("reverse", asUtility=True)

    # Connecting attributes to reverse node
    cmds.connectAttr(
        prefix + "upper_Eyelid_CTRL_07_Center.blinkHeight",
        reverse_node + ".inputX",
        force=True,
    )

    # Connecting reverse node to blendShape
    cmds.connectAttr(
        reverse_node + ".outputX",
        prefix + "blink_Eyelid_LowRes_BLEND." + prefix + "lower_Eyelid_LowRes_CRV",
        force=True,
    )


# Connect blendShapes to height for both sides
connect_blendshape_to_height("l_")
connect_blendshape_to_height("r_")


# Duplicating curves to get the blink curves
def duplicate_and_rename_curves(prefixes):
    duplicated_objects = []
    for prefix in prefixes:
        cmds.select(prefix + "upper_Eyelid_HighRes_CRV", replace=True)
        cmds.select(prefix + "lower_Eyelid_HighRes_CRV", add=True)
        duplicated_objects += cmds.duplicate(rr=True)

    for obj in duplicated_objects:
        new_name = obj.replace("_HighRes", "_HighRes_Blink")
        new_name = new_name[:-1] if new_name.endswith("1") else new_name
        cmds.rename(obj, new_name)


duplicate_and_rename_curves(["r_", "l_"])  # Duplicating curves for both sides


cmds.setAttr(
    "l_upper_Eyelid_CTRL_07_Center.blinkHeight", 1
)  # Setting the attributes for the high wire
cmds.setAttr("r_upper_Eyelid_CTRL_07_Center.blinkHeight", 1)

cmds.wire(
    "r_upper_Eyelid_HighRes_Blink_CRV",
    wire="r_blink_Eyelid_LowRes_CRV",
    groupWithBase=False,
    envelope=1.0,
    crossingEffect=0.0,
    localInfluence=0.0,
    name="r_upper_Eyelid_HighRes_Blink_Wire",
)  # Creating Wires that follow the blinkHeight
cmds.setAttr("r_upper_Eyelid_HighRes_Blink_Wire.scale[0]", 0)
cmds.parent("r_blink_Eyelid_LowRes_CRVBaseWire", "r_Eyelid_crvs_BaseWires")

cmds.wire(
    "l_upper_Eyelid_HighRes_Blink_CRV",
    wire="l_blink_Eyelid_LowRes_CRV",
    groupWithBase=False,
    envelope=1.0,
    crossingEffect=0.0,
    localInfluence=0.0,
    name="l_upper_Eyelid_HighRes_Blink_Wire",
)
cmds.setAttr("l_upper_Eyelid_HighRes_Blink_Wire.scale[0]", 0)
cmds.parent("l_blink_Eyelid_LowRes_CRVBaseWire", "l_Eyelid_crvs_BaseWires")


cmds.setAttr("l_upper_Eyelid_CTRL_07_Center.blinkHeight", 0)
cmds.setAttr("r_upper_Eyelid_CTRL_07_Center.blinkHeight", 0)

cmds.wire(
    "r_lower_Eyelid_HighRes_Blink_CRV",
    wire="r_blink_Eyelid_LowRes_CRV",
    groupWithBase=False,
    envelope=1.0,
    ce=0.0,
    li=0.0,
    n="r_lower_Eyelid_HighRes_Blink_Wire",
)
cmds.setAttr("r_lower_Eyelid_HighRes_Blink_Wire.scale[0]", 0)
cmds.parent("r_blink_Eyelid_LowRes_CRVBaseWire1", "r_Eyelid_crvs_BaseWires")

cmds.wire(
    "l_lower_Eyelid_HighRes_Blink_CRV",
    wire="l_blink_Eyelid_LowRes_CRV",
    groupWithBase=False,
    envelope=1.0,
    ce=0.0,
    li=0.0,
    n="l_lower_Eyelid_HighRes_Blink_Wire",
)
cmds.setAttr("l_lower_Eyelid_HighRes_Blink_Wire.scale[0]", 0)
cmds.parent("l_blink_Eyelid_LowRes_CRVBaseWire1", "l_Eyelid_crvs_BaseWires")


# Creating the blends
cmds.blendShape(
    "r_upper_Eyelid_HighRes_Blink_CRV",
    "r_upper_Eyelid_HighRes_CRV",
    before=True,
    n="r_upper_Eyelid_HighRes_Blink_BLEND",
)
cmds.blendShape(
    "l_upper_Eyelid_HighRes_Blink_CRV",
    "l_upper_Eyelid_HighRes_CRV",
    before=True,
    n="l_upper_Eyelid_HighRes_Blink_BLEND",
)

cmds.blendShape(
    "r_lower_Eyelid_HighRes_Blink_CRV",
    "r_lower_Eyelid_HighRes_CRV",
    before=True,
    n="r_lower_Eyelid_HighRes_Blink_BLEND",
)
cmds.blendShape(
    "l_lower_Eyelid_HighRes_Blink_CRV",
    "l_lower_Eyelid_HighRes_CRV",
    before=True,
    n="l_lower_Eyelid_HighRes_Blink_BLEND",
)


cmds.connectAttr(
    "l_upper_Eyelid_CTRL_07_Center.blink",
    "l_upper_Eyelid_HighRes_Blink_BLEND.l_upper_Eyelid_HighRes_Blink_CRV",
    force=True,
)
cmds.connectAttr(
    "r_upper_Eyelid_CTRL_07_Center.blink",
    "r_upper_Eyelid_HighRes_Blink_BLEND.r_upper_Eyelid_HighRes_Blink_CRV",
    force=True,
)

cmds.connectAttr(
    "l_lower_Eyelid_CTRL_07_Center.blink",
    "l_lower_Eyelid_HighRes_Blink_BLEND.l_lower_Eyelid_HighRes_Blink_CRV",
    force=True,
)
cmds.connectAttr(
    "r_lower_Eyelid_CTRL_07_Center.blink",
    "r_lower_Eyelid_HighRes_Blink_BLEND.r_lower_Eyelid_HighRes_Blink_CRV",
    force=True,
)


# Select the object
cmds.select("Look_CTRL", r=True)
# Add 'Follow' attribute to the selected object
cmds.addAttr(
    "Eyes_look_OFST|Look_CTRL",
    longName="Follow",
    attributeType="enum",
    enumName="___:Blue:",
)
cmds.setAttr("Eyes_look_OFST|Look_CTRL.Follow", keyable=True)

# Add 'eyeLidsFollow' attribute to the selected object
cmds.addAttr(
    "Eyes_look_OFST|Look_CTRL",
    longName="eyeLidsFollow",
    attributeType="double",
    minValue=0,
    maxValue=1,
    defaultValue=0.2,
)
cmds.setAttr("Eyes_look_OFST|Look_CTRL.eyeLidsFollow", keyable=True)


# Cleaning up and Organizing
cmds.parent("r_Eyelid_JNTS", "eye_r_bind_JNT")
cmds.parent("l_Eyelid_JNTS", "eye_l_bind_JNT")

cmds.parentConstraint("eyeSocket_r_bind_JNT", "r_Eyelid_CRVS", mo=True)
cmds.parentConstraint("eyeSocket_l_bind_JNT", "l_Eyelid_CRVS", mo=True)

cmds.parentConstraint("eye_r_bind_JNT", "r_upper_Eyelid_CTRLS", mo=True)
cmds.parentConstraint("eye_r_bind_JNT", "r_lower_Eyelid_CTRLS", mo=True)
cmds.parentConstraint("eye_l_bind_JNT", "l_upper_Eyelid_CTRLS", mo=True)
cmds.parentConstraint("eye_l_bind_JNT", "l_lower_Eyelid_CTRLS", mo=True)

cmds.setAttr("r_upper_Eyelid_LowRes_CRV.inheritsTransform", 0)
cmds.setAttr("r_lower_Eyelid_LowRes_CRV.inheritsTransform", 0)

cmds.setAttr("l_upper_Eyelid_LowRes_CRV.inheritsTransform", 0)
cmds.setAttr("l_lower_Eyelid_LowRes_CRV.inheritsTransform", 0)

cmds.setAttr(
    "r_blink_Eyelid_LowRes_CRV.inheritsTransform", 0
)  # This was not in the tutorial...I added it, so it may need changing later
cmds.setAttr("l_blink_Eyelid_LowRes_CRV.inheritsTransform", 0)


cmds.parent("Joints", "faceRoot_JNT")
cmds.parent("Locators", "F_RIG")
cmds.parent("Eyelids", "F_RIG")
cmds.parent("Eyelid_CTRLS", "Eyelids")
cmds.parent("Eyelid_CTRL_JNTS", "Eyelid_JNTS")
cmds.parent("Eyelid_CRVS", "Eyelids")
