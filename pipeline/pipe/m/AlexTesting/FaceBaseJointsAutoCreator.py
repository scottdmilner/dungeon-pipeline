# mypy: disable-error-code="call-arg,arg-type"
import maya.cmds as cmds


def parentChain(chainList):
    i = 1
    while i < (len(chainList)):
        cmds.parent(chainList[i], chainList[i - 1])
        i += 1


def parentAll(list):
    try:
        for each in list:
            cmds.parent(each, list[0])
    except Exception:
        print("oopsies")


def locToJoint(headLocator):
    cmds.select(cl=True)

    def recursiveHelper(callOn, parentJointName):
        if cmds.listRelatives(callOn, c=True, type="transform") is not None:
            for each in cmds.listRelatives(str(callOn), c=True, type="transform"):
                translate = cmds.xform(each, query=True, ws=True, rotatePivot=True)

                cmds.select(cl=True)

                cmds.joint(p=(translate[0], translate[1], translate[2]))

                currentJointName = cmds.rename(
                    cmds.ls(selection=True), str(each)[: (len(str(each)) - 5)]
                )

                # HEY DUMDUM YOU NEED TO GIVE THE PARENT COMMAND THE NAME OF THE JOINTS NOT THE LOCATORS.
                # YOU SHOULD ALSO CREATE THIS AS A PARAMETER TO BE FED INTO THE RECURSIVE FUNCTION

                cmds.parent(currentJointName, parentJointName)

                recursiveHelper(each, currentJointName)

    translate = cmds.xform(str(headLocator), query=True, ws=True, rotatePivot=True)
    cmds.joint(p=(translate[0], translate[1], translate[2]))
    cmds.rename(
        cmds.ls(selection=True), str(headLocator)[: (len(str(headLocator)) - 5)]
    )

    rootJointName = str(headLocator)[: (len(str(headLocator)) - 5)]

    if cmds.listRelatives(headLocator):
        recursiveHelper(headLocator, rootJointName)


# if cmds.listRelatives("head_JNT_temp"):
#    print(cmds.listRelatives("head_JNT_temp", c = True, type = "transform"))


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


locToJoint("head_JNT_temp")


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
