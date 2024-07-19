# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds
from maya import mel
from pipe.m.AlexTesting import AGFunctions


tempList = []

cmds.spaceLocator(n="head_JNT_temp")
cmds.xform(t=(0, 151.177, -4.038))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="jaw_JNT_temp")
cmds.xform(t=(0, 148.835, -0.835))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="upperTeeth_JNT_temp")
cmds.xform(t=(0, 149.432, 5.857))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="lowerTeeth_JNT_temp")
cmds.xform(t=(0, 147.52, 5.738))
tempList.append(cmds.ls(selection=True)[0])

cmds.parent("upperTeeth_JNT_temp", "jaw_JNT_temp")
cmds.parent("lowerTeeth_JNT_temp", "jaw_JNT_temp")
cmds.parent("jaw_JNT_temp", "head_JNT_temp")


AGFunctions.locToJoint("head_JNT_temp")


if cmds.about(nt=True):
    cmds.file(
        "G:\dungeons\character\Rigging\Rigs\RobinFace\Controls\RobinGlobalMouthControls.ma",
        i=True,
    )
if cmds.about(os=True) == "linux64":
    cmds.file(
        "/groups/dungeons/character/Rigging/Rigs/RobinFace/Controls/RobinGlobalMouthControls.ma",
        i=True,
    )


cmds.addAttr("jaw_ctrl", ln="LipInfluence", k=True, dv=1, min=0, max=2, at="double")

cmds.parentConstraint("jaw_ctrl", "jaw_JNT")


upperLipEdges1 = cmds.ls(
    "FaceAtOrigin.e[15857]",
    "FaceAtOrigin.e[15899]",
    "FaceAtOrigin.e[15934]",
    "FaceAtOrigin.e[15863]",
    "FaceAtOrigin.e[15870]",
    "FaceAtOrigin.e[15873]",
    "FaceAtOrigin.e[15957]",
    "FaceAtOrigin.e[15874]",
    "FaceAtOrigin.e[1115]",
    "FaceAtOrigin.e[1204]",
    "FaceAtOrigin.e[1110]",
    "FaceAtOrigin.e[1107]",
    "FaceAtOrigin.e[1099]",
    "FaceAtOrigin.e[1177]",
    "FaceAtOrigin.e[1144]",
    "FaceAtOrigin.e[1098]",
    "FaceAtOrigin.e[1088]",
    "FaceAtOrigin.e[15852]",
)
upperLipEdges2 = cmds.ls(
    "FaceAtOrigin.e[15972]",
    "FaceAtOrigin.e[15865]",
    "FaceAtOrigin.e[15975]",
    "FaceAtOrigin.e[15985]",
    "FaceAtOrigin.e[15897]",
    "FaceAtOrigin.e[15856]",
    "FaceAtOrigin.e[15937]",
    "FaceAtOrigin.e[15955]",
    "FaceAtOrigin.e[15881]",
    "FaceAtOrigin.e[1120]",
    "FaceAtOrigin.e[1201]",
    "FaceAtOrigin.e[1182]",
    "FaceAtOrigin.e[1105]",
    "FaceAtOrigin.e[1218]",
    "FaceAtOrigin.e[1223]",
    "FaceAtOrigin.e[1232]",
    "FaceAtOrigin.e[1140]",
    "FaceAtOrigin.e[1092]",
)
bottomLipEdges1 = cmds.ls(
    "FaceAtOrigin.e[16019]",
    "FaceAtOrigin.e[1239]",
    "FaceAtOrigin.e[1245]",
    "FaceAtOrigin.e[1251]",
    "FaceAtOrigin.e[1261]",
    "FaceAtOrigin.e[1267]",
    "FaceAtOrigin.e[1328]",
    "FaceAtOrigin.e[1353]",
    "FaceAtOrigin.e[1362]",
    "FaceAtOrigin.e[1365]",
    "FaceAtOrigin.e[15990]",
    "FaceAtOrigin.e[15998]",
    "FaceAtOrigin.e[16005]",
    "FaceAtOrigin.e[16011]",
    "FaceAtOrigin.e[16019]",
    "FaceAtOrigin.e[16072]",
    "FaceAtOrigin.e[16098]",
    "FaceAtOrigin.e[16108]",
    "FaceAtOrigin.e[16110]",
)
bottomLipEdges2 = cmds.ls(
    "FaceAtOrigin.e[16021]",
    "FaceAtOrigin.e[1242]",
    "FaceAtOrigin.e[1248]",
    "FaceAtOrigin.e[1255]",
    "FaceAtOrigin.e[1265]",
    "FaceAtOrigin.e[1269]",
    "FaceAtOrigin.e[1332]",
    "FaceAtOrigin.e[1348]",
    "FaceAtOrigin.e[1360]",
    "FaceAtOrigin.e[1367]",
    "FaceAtOrigin.e[15994]",
    "FaceAtOrigin.e[16001]",
    "FaceAtOrigin.e[16009]",
    "FaceAtOrigin.e[16015]",
    "FaceAtOrigin.e[16021]",
    "FaceAtOrigin.e[16077]",
    "FaceAtOrigin.e[16095]",
    "FaceAtOrigin.e[16106]",
    "FaceAtOrigin.e[16113]",
)


AGFunctions.makeCurve(upperLipEdges1, "upperLipCurve1")
AGFunctions.makeCurve(upperLipEdges2, "upperLipCurve2")
AGFunctions.makeCurve(bottomLipEdges1, "bottomLipCurve1")
AGFunctions.makeCurve(bottomLipEdges2, "bottomLipCurve2")


cmds.loft("upperLipCurve1", "upperLipCurve2")
cmds.rename(cmds.ls(selection=True), "upperLipRibbon")

cmds.loft("bottomLipCurve1", "bottomLipCurve2")
cmds.rename(cmds.ls(selection=True), "bottomLipRibbon")
cmds.reverseSurface("bottomLipRibbon")

cmds.select("upperLipRibbon")
mel.eval("createHair 1 19 10 0 0 1 1 5 0 1 1 1;")

cmds.select("bottomLipRibbon")
mel.eval("createHair 1 19 10 0 0 1 1 5 0 1 1 1;")

FollicleGroup1 = cmds.listRelatives("hairSystem1Follicles")
FollicleGroup2 = cmds.listRelatives("hairSystem2Follicles")


AGFunctions.JointFollicleSnapper(FollicleGroup1)
AGFunctions.JointFollicleSnapper(FollicleGroup2)

cmds.delete("hairSystem1", "hairSystem2", "pfxHair1", "pfxHair2", "nucleus1")
cmds.delete(
    "bottomLipRibbonFollicle5044",
    "bottomLipRibbonFollicle5055",
    "bottomLipRibbonFollicle5066",
    "bottomLipRibbonFollicle5033",
    "bottomLipRibbonFollicle5022",
    "bottomLipRibbonFollicle5077",
    "bottomLipRibbonFollicle5099",
    "bottomLipRibbonFollicle5088",
    "bottomLipRibbonFollicle5011",
    "bottomLipRibbonFollicle5000",
)
cmds.delete(
    "upperLipRibbonFollicle5044",
    "upperLipRibbonFollicle5055",
    "upperLipRibbonFollicle5066",
    "upperLipRibbonFollicle5033",
    "upperLipRibbonFollicle5022",
    "upperLipRibbonFollicle5077",
    "upperLipRibbonFollicle5099",
    "upperLipRibbonFollicle5088",
    "upperLipRibbonFollicle5011",
    "upperLipRibbonFollicle5000",
)

jointNaming = AGFunctions.searchFor("hairSystem1Follicles", "joint")

cmds.rename(jointNaming[0], "R_Upper_Minor_Mouth_04_jnt")
cmds.rename(jointNaming[1], "R_Upper_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[2], "R_Upper_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[3], "R_Upper_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[4], "M_Upper_Minor_Mouth_jnt")
cmds.rename(jointNaming[5], "L_Upper_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[6], "L_Upper_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[7], "L_Upper_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[8], "L_Upper_Minor_Mouth_04_jnt")

jointNaming = AGFunctions.searchFor("hairSystem2Follicles", "joint")

cmds.rename(jointNaming[0], "R_Lower_Minor_Mouth_04_jnt")
cmds.rename(jointNaming[1], "R_Lower_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[2], "R_Lower_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[3], "R_Lower_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[4], "M_Lower_Minor_Mouth_jnt")
cmds.rename(jointNaming[5], "L_Lower_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[6], "L_Lower_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[7], "L_Lower_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[8], "L_Lower_Minor_Mouth_04_jnt")


mainJointLoc = [
    "M_Upper_Minor_Mouth_jnt",
    "M_Lower_Minor_Mouth_jnt",
    "R_Lower_Minor_Mouth_02_jnt",
    "L_Lower_Minor_Mouth_02_jnt",
    "L_Upper_Minor_Mouth_02_jnt",
    "R_Upper_Minor_Mouth_02_jnt",
    "FaceAtOrigin.vtx[7840]",
    "FaceAtOrigin.vtx[643]",
]

jointNaming = AGFunctions.snapJointTo(mainJointLoc, 1)

controlGroup = []

controlGroup.append(cmds.rename(jointNaming[0], "M_Upper_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[1], "M_Lower_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[2], "R_Lower_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[3], "L_Lower_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[4], "L_Upper_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[5], "R_Upper_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[6], "L_Corner_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[7], "R_Corner_Main_Mouth_jnt"))


for each in controlGroup:
    getPos = cmds.xform(each, query=True, ws=True, rp=True)

    nameBase = each[: len(each) - 4]

    Circle = cmds.circle(nr=(0, 0, 1), c=(getPos[0], getPos[1], getPos[2]), r=0.5)  # type: ignore[index]
    cmds.rename(nameBase + "_ctrl")

    # center pivot
    cmds.CenterPivot()  # type: ignore[attr-defined]

    # make offset and driver group
    cmds.group(n=nameBase + "_offset")
    cmds.CenterPivot()  # type: ignore[attr-defined]
    cmds.group(n=nameBase + "_ctrl_driver")

    getPivot = cmds.xform("jaw_JNT", query=True, ws=True, rp=True)
    cmds.move(
        getPivot[0],  # type: ignore[index]
        getPivot[1],  # type: ignore[index]
        getPivot[2],  # type: ignore[index]
        nameBase + "_ctrl_driver.scalePivot",
        nameBase + "_ctrl_driver.rotatePivot",
        ws=True,
    )

    cmds.parentConstraint(each[: len(each) - 4] + "_ctrl", each)

AGFunctions.jawControllerLinker(["M_Lower_Main_Mouth_ctrl"])
AGFunctions.jawControllerLinker(["L_Lower_Main_Mouth_ctrl", "R_Lower_Main_Mouth_ctrl"])
AGFunctions.jawControllerLinker(
    ["L_Corner_Main_Mouth_ctrl", "R_Corner_Main_Mouth_ctrl"]
)
AGFunctions.jawControllerLinker(["L_Upper_Main_Mouth_ctrl", "R_Upper_Main_Mouth_ctrl"])
AGFunctions.jawControllerLinker(["M_Upper_Main_Mouth_ctrl"])


cmds.setAttr("L_Lower_Main_Mouth_ctrl_remap.outputMax", 0.85)
cmds.setAttr("L_Corner_Main_Mouth_ctrl_remap.outputMax", 0.5)
cmds.setAttr("L_Upper_Main_Mouth_ctrl_remap.outputMax", 0.15)
cmds.setAttr("M_Upper_Main_Mouth_ctrl_remap.outputMax", 0)


cmds.group(
    "M_Upper_Main_Mouth_ctrl_driver",
    "M_Lower_Main_Mouth_ctrl_driver",
    "R_Lower_Main_Mouth_ctrl_driver",
    "L_Lower_Main_Mouth_ctrl_driver",
    "L_Upper_Main_Mouth_ctrl_driver",
    "R_Upper_Main_Mouth_ctrl_driver",
    "L_Corner_Main_Mouth_ctrl_driver",
    "R_Corner_Main_Mouth_ctrl_driver",
    n="MainMouthCtronolsGroup",
)
cmds.parent("MainMouthControlsGroup", "Mouth_Global_ctrl")


cmds.delete("upperLipRibbon", constructionHistory=True)
cmds.delete("bottomLipRibbon", constructionHistory=True)


cmds.skinCluster(
    "upperLipRibbon",
    "M_Upper_Main_Mouth_jnt",
    "L_Upper_Main_Mouth_jnt",
    "R_Upper_Main_Mouth_jnt",
    "L_Corner_Main_Mouth_jnt",
    "R_Corner_Main_Mouth_jnt",
)
cmds.skinCluster(
    "bottomLipRibbon",
    "M_Lower_Main_Mouth_jnt",
    "L_Lower_Main_Mouth_jnt",
    "R_Lower_Main_Mouth_jnt",
    "L_Corner_Main_Mouth_jnt",
    "R_Corner_Main_Mouth_jnt",
)
