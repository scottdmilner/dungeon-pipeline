import maya.cmds as mc


def createSpaceSwitch():
    sel = mc.ls(sl=True)
    sources = sel

    target = sel[-1]
    sources.remove(target)
    sourceNames = []

    colonSourceStr = ""
    for source in sources:
        name = source.replace("_CTRL", "")
        if ":" in source:
            c = source.index(":")
            name = source[c + 1 :]
        colonSourceStr += name + ":"
        sourceNames.append(name)

    if mc.attributeQuery("spaceSwitch", node=target, exists=True):
        mc.deleteAttr(target, at="spaceSwitch")

    mc.addAttr(
        target,
        ln="spaceSwitch",
        at="enum",
        en="default:" + colonSourceStr,
        keyable=True,
    )

    mc.select(target)
    grp = target + "_OFF_GRP"

    if not mc.objExists(grp):
        grp = mc.group(
            name=target + "_OFF_GRP",
            em=True,
            parent=mc.listRelatives(target, parent=True)[0],
        )
        mc.parent(target, grp)

    if mc.listRelatives(grp, type="constraint") is not None:
        constraint = mc.listRelatives(grp, type="constraint")[0]
        mc.delete(constraint)
    pc = mc.parentConstraint(sources, grp, mo=True)[0]

    pcTrgs = mc.parentConstraint(pc, wal=True, q=True)

    defaultCond = mc.createNode("condition", n="default_COND")
    mc.connectAttr(target + ".spaceSwitch", defaultCond + ".firstTerm")
    mc.setAttr(defaultCond + ".colorIfTrueR", 0)
    mc.setAttr(defaultCond + ".colorIfFalseR", 1)
    mc.setAttr(defaultCond + ".operation", 0)

    for count, source in enumerate(sources):
        print(source)
        print(pcTrgs[count])
        cond = mc.createNode("condition", n=pcTrgs[count] + "_COND")
        mc.connectAttr(target + ".spaceSwitch", cond + ".firstTerm")
        mc.setAttr(cond + ".secondTerm", count + 1)
        mc.setAttr(cond + ".colorIfTrueR", 1)
        mc.setAttr(cond + ".colorIfFalseR", 0)
        mc.connectAttr(defaultCond + ".outColorR", cond + ".colorIfTrueR")
        mc.connectAttr(cond + ".outColorR", pc + "." + pcTrgs[count])

    mc.select(target)


def run():
    createSpaceSwitch()
