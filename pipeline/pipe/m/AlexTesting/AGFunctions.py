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


def makeCurve(edges, name):
    cmds.select(edges)
    cmds.polyToCurve()
    cmds.rename(cmds.ls(selection=True), name)


def snapTo(startingLocation, endLocation):
    wS = cmds.xform(endLocation, query=True, rotatePivot=True, worldSpace=True)
    cmds.xform(startingLocation, ws=True, t=(wS[0], wS[1], wS[2]))


def snapJointTo(listGroup, jntSize):
    jointList = []
    for each in listGroup:
        if cmds.objectType(each) == "joint":
            wS = cmds.xform(str(each), query=True, rotatePivot=True, worldSpace=True)
            Joint = cmds.joint(p=(wS[0], wS[1], wS[2]), rad=jntSize)
            jointList.append(Joint)
            cmds.select(cl=True)

        if cmds.objectType(each) == "mesh":
            wS = cmds.pointPosition(each)
            Joint = cmds.joint(p=(wS[0], wS[1], wS[2]), rad=jntSize)
            jointList.append(Joint)
            cmds.select(cl=True)
    return jointList


def JointFollicleSnapper(fGroup):
    for each in fGroup:
        wS = cmds.xform(str(each), query=True, rotatePivot=True, worldSpace=True)
        Joint = cmds.joint(p=(wS[0], wS[1], wS[2]), rad=0.25)
        cmds.parent(cmds.ls(selection=True)[0], each)

        Circle = cmds.circle(nr=(0, 0, 1), c=(0, 0, 0), r=0.25)
        cmds.xform(t=(wS[0], wS[1], wS[2]))
        cmds.parent(cmds.ls(selection=True)[0], each)
        cmds.parentConstraint(Circle, Joint)
        ###ADD in parent to group and parent constraaint

        cmds.select(clear=True)


def searchFor(object, type):
    everythingInFollicle = cmds.listRelatives(object, ad=True)
    typeList = []

    for each in everythingInFollicle:
        if cmds.objectType(each) == type:
            typeList.append(each)

    return typeList


def jawControllerLinker(controls=cmds.ls(sl=1)):
    # Written by AntCGI

    jawJoint = "jaw_JNT"
    jawControl = "jaw_ctrl"

    # controlList = cmds.ls(sl=1)
    controlList = controls

    cmds.shadingNode("multiplyDivide", au=1, n=controlList[0] + "_multi")
    cmds.shadingNode("remapValue", au=1, n=controlList[0] + "_remap")

    cmds.connectAttr(jawJoint + ".rotate", controlList[0] + "_multi.input1", f=1)

    cmds.connectAttr(
        jawControl + ".Lip Influence", controlList[0] + "_remap.inputValue", f=1
    )

    cmds.connectAttr(
        controlList[0] + "_remap.outValue", controlList[0] + "_multi.input2X", f=1
    )
    cmds.connectAttr(
        controlList[0] + "_remap.outValue", controlList[0] + "_multi.input2Y", f=1
    )
    cmds.connectAttr(
        controlList[0] + "_remap.outValue", controlList[0] + "_multi.input2Z", f=1
    )

    cmds.connectAttr(
        controlList[0] + "_multi.output", controlList[0] + "_driver.rotate", f=1
    )

    if len(controlList) > 1:
        cmds.connectAttr(
            controlList[0] + "_multi.output", controlList[1] + "_driver.rotate", f=1
        )


def offsetGroupMaker(thingToOffset):
    cmds.parent(thingToOffset, world=True)
    emptyGroup = cmds.group(empty=True)
    snapTo(emptyGroup, thingToOffset)
    cmds.parent(thingToOffset, emptyGroup)
    return emptyGroup
