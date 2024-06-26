# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds
import pipe.m.ToolBox.getUParam as getUParam

# This connects the Locators to the high res curve
# It also creates the first set of wire deformers
#    These are used to have the low res drive the high res curves


def connect_to_curve(curveName, selection):
    for eachItem in selection:
        # get position of locator
        pos = cmds.xform(eachItem, q=True, ws=True, t=True)

        # get parameter U on curve from locator
        u = getUParam(pos, curveName)

        # create point on curve info node
        nodeName = eachItem.replace("_loc", "_pci")
        pci = cmds.createNode("pointOnCurveInfo", name=nodeName)

        # connect curve to the pointOnCurveInfo node
        cmds.connectAttr(curveName + ".worldSpace", pci + ".inputCurve")

        # set parameter to U value
        cmds.setAttr(pci + ".parameter", u)

        # connect PCI to locator
        cmds.connectAttr(pci + ".position", eachItem + ".translate")


curveName = "l_upper_Eyelid_HighRes_CRV"
# Selecting children of the "l_lower_Eyelid_LOCS" group
selection = (
    cmds.listRelatives("l_upper_Eyelid_LOCS", children=True, fullPath=True) or []
)

connect_to_curve(curveName, selection)


curveName = "l_lower_Eyelid_HighRes_CRV"
# Selecting children of the "l_lower_Eyelid_LOCS" group
selection = (
    cmds.listRelatives("l_lower_Eyelid_LOCS", children=True, fullPath=True) or []
)

connect_to_curve(curveName, selection)


curveName = "r_upper_Eyelid_HighRes_CRV"
# Selecting children of the "l_lower_Eyelid_LOCS" group
selection = (
    cmds.listRelatives("r_upper_Eyelid_LOCS", children=True, fullPath=True) or []
)

connect_to_curve(curveName, selection)


curveName = "r_lower_Eyelid_HighRes_CRV"
# Selecting children of the "l_lower_Eyelid_LOCS" group
selection = (
    cmds.listRelatives("r_lower_Eyelid_LOCS", children=True, fullPath=True) or []
)

connect_to_curve(curveName, selection)


# Let's also create the first wires in this script

# Create a wire deformer between the low-resolution and high-resolution curves
wire_deformer_r_upper = cmds.wire(
    "r_upper_Eyelid_HighRes_CRV",
    wire="r_upper_Eyelid_LowRes_CRV",
    name="r_upper_Eyelid_HighRes_Wire",
    en=1.0,
    ce=0.0,
    li=0.0,
)[0]  # type: ignore[index]


wire_deformer_r_lower = cmds.wire(
    "r_lower_Eyelid_HighRes_CRV",
    wire="r_lower_Eyelid_LowRes_CRV",
    name="r_lower_Eyelid_HighRes_Wire",
    en=1.0,
    ce=0.0,
    li=0.0,
)[0]  # type: ignore[index]


wire_deformer_l_upper = cmds.wire(
    "l_upper_Eyelid_HighRes_CRV",
    wire="l_upper_Eyelid_LowRes_CRV",
    name="l_upper_Eyelid_HighRes_Wire",
    en=1.0,
    ce=0.0,
    li=0.0,
)[0]  # type: ignore[index]


wire_deformer_l_lower = cmds.wire(
    "l_lower_Eyelid_HighRes_CRV",
    wire="l_lower_Eyelid_LowRes_CRV",
    name="l_lower_Eyelid_HighRes_Wire",
    en=1.0,
    ce=0.0,
    li=0.0,
)[0]  # type: ignore[index]


# Grouping the base wires appripriately

r_Eyelid_crvs_BaseWires = cmds.group(
    "r_upper_Eyelid_LowRes_CRVBaseWire",
    "r_lower_Eyelid_LowRes_CRVBaseWire",
    name="r_Eyelid_crvs_BaseWires",
)
l_Eyelid_crvs_BaseWires = cmds.group(
    "l_upper_Eyelid_LowRes_CRVBaseWire",
    "l_lower_Eyelid_LowRes_CRVBaseWire",
    name="l_Eyelid_crvs_BaseWires",
)

cmds.parent(r_Eyelid_crvs_BaseWires, "r_Eyelid_CRVS")
cmds.parent(l_Eyelid_crvs_BaseWires, "l_Eyelid_CRVS")
