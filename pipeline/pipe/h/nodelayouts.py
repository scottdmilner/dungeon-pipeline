from __future__ import annotations
# mypy: disable-error-code="union-attr"

import hou
import loptoolutils  # type: ignore[import-not-found]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


"""Scripts for building node setups. Called by lnd_nodelayouts.hdanc in Interactive > Shelf Tools, also make sure to check a network context in the context tab"""
def lnd_clustersetup(kwargs: dict, parent: Optional[hou.Node] = None) -> hou.Node:
    out: hou.LopNode = loptoolutils.genericTool(kwargs, "componentoutput")
    out.setColor(hou.Color((0.616, 0.871, 0.769)))

    out_pos = out.position()

    #This is the context within the out node exists, which should be the stage context
    p = out.parent() 

    #fetches the other nodes
    ldv = p.createNode("sdm223::dev::LnD_Lookdev")
    prim = p.createNode("primitive")
    graft = p.createNode("graftstages")
    env = p.createNode("fetch")
    err = p.createNode("error")

    #Establishes Connections
    out.setInput(0, graft)
    graft.setInput(0, err)
    err.setInput(0,prim)
    ldv.setInput(0, out)
    out.setInput(1, env)

    # Arrange nodes in "Y" shape
    err_move = hou.Vector2(-1.22,2.3)
    prim_move = hou.Vector2(-1.22, 3.5)
    graft_move = hou.Vector2(0.0, 1.0)
    ldv_move = hou.Vector2(0.0, -1.0)
    env_move = hou.Vector2(1.5, 0.5)
    prim.setPosition(prim_move + out_pos)
    err.setPosition(err_move + out_pos)
    graft.setPosition(graft_move + out_pos)
    ldv.setPosition(ldv_move + out_pos)
    env.setPosition(env_move + out_pos)

    # Configure environment fetch
    env.parm("loppath").set(f"../{ldv.name()}/OUT_ENV")

    # Configure Component Output node
    out.parm("mode").set(1)
    graft.parm("destpath").set("/")
    prim.parm("primpath").set("$OS")
    out.parm("rootprim").set("`lopinputprim('.', 0)`")
    err.parm("errormsg1").set("Please name your primitive node")
    err.parm("severity1").set("error")

    error_expression = "import re\nrgx = re.compile(\"primitive[0-9]+\")\nreturn any(rgx.match(node.name()) for node in hou.pwd().inputAncestors())"
    err.parm("enable1").setExpression(error_expression, language=hou.exprLanguage.Python)

    #Set the Component Output as Selected
    out.setCurrent(True)
    out.setSelected(True, clear_all_selected=True)

    return out


def lnd_componentgeometry(kwargs: dict, parent: Optional[hou.Node] = None) -> hou.Node:
    if parent:
        cgeo = parent.createNode("componentgeometry")
    else:
        cgeo = loptoolutils.genericTool(kwargs, "componentgeometry")

    # Set up nodes inside of Component Geometry
    geo_sop = cgeo.node("./sopnet/geo")
    geo_sop.loadItemsFromFile(
        hou.hscriptStringExpression("$HSITE") + "/sop/component.cpio"
    )
    for name in ["default", "proxy", "simproxy"]:
        geo_sop.node(f"./{name}").setInput(0, geo_sop.node(f"./OUT_{name}"))

    # Configure Component Geometry node
    cgeo.parm("dogeommodelapi").set(True)
    cgeo.parm("attribs").set("P uv")
    cgeo.parm("indexattribs").set("texset")

    cgeo.setColor(hou.Color((0.616, 0.871, 0.769)))

    return cgeo


def lnd_componentmaterial(kwargs: dict, parent: Optional[hou.Node] = None) -> hou.Node:
    MAT_ROOT = "/ASSET/mtl/MAT_"
    TS_PRIMVAR = "texset"

    if parent:
        cmat = parent.createNode("componentmaterial")
    else:
        cmat = loptoolutils.genericTool(kwargs, "componentmaterial")

    # configure component material node
    cmat.parm("variantname").set("`chs(opinputpath('.', 1)/mat_var)`")

    # set up primvar-based material assignment
    edit = cmat.node("./edit")
    assign = edit.createNode("assignmaterial")
    assign.setInput(0, edit.indirectInputs()[0])
    edit.node("./output0").setInput(0, assign)
    assign.parm("primpattern1").set(
        "%descendants(`lopinputprims('.', 0)`) & %type:Mesh"
    )
    assign.parm("matspecmethod1").set("vexpr")
    assign.parm("matspecvexpr1").set(
        f"return '{MAT_ROOT}' + usd_primvarelement(0, @primpath, '{TS_PRIMVAR}', usd_primvarindices(0, @primpath, '{TS_PRIMVAR}')[@elemnum]);"
    )
    assign.parm("geosubset1").set(True)

    cmat.setColor(hou.Color((0.616, 0.871, 0.769)))

    return cmat


def lnd_componentsetup(kwargs: dict) -> hou.Node:
    out: hou.LopNode = loptoolutils.genericTool(kwargs, "componentoutput")
    out.setColor(hou.Color((0.616, 0.871, 0.769)))

    out_pos = out.position()
    p = out.parent()
    geo = lnd_componentgeometry(kwargs, parent=p)
    mtl = lnd_componentmaterial(kwargs, parent=p)
    lib = p.createNode("sdm223::main::LnD_MatLib")
    cnf = p.createNode("sdm223::lnd_componentconfig")
    ldv = p.createNode("sdm223::dev::LnD_Lookdev")
    env = p.createNode("fetch")
    out.setInput(0, cnf)
    out.setInput(1, env)
    cnf.setInput(0, mtl)
    mtl.setInput(0, geo)
    mtl.setInput(1, lib)
    ldv.setInput(0, out)

    # Arrange nodes in "Y" shape
    geo_move = hou.Vector2(-1.22, 3.5)
    mtl_move = hou.Vector2(0.0, 2.0)
    lib_move = hou.Vector2(1.22, 3.0)
    cnf_move = hou.Vector2(0.0, 1.0)
    ldv_move = hou.Vector2(0.0, -1.0)
    env_move = hou.Vector2(1.5, 0.5)
    geo.setPosition(geo_move + out_pos)
    mtl.setPosition(mtl_move + out_pos)
    lib.setPosition(lib_move + out_pos)
    cnf.setPosition(cnf_move + out_pos)
    ldv.setPosition(ldv_move + out_pos)
    env.setPosition(env_move + out_pos)

    # Configure environment fetch
    env.parm("loppath").set(f"../{ldv.name()}/OUT_ENV")

    # Configure Component Output node
    asset_name = hou.hscriptStringExpression("$HIP").split("/")[-1]
    out.parm("rootprim").set("/" + asset_name)
    out.parm("localize").set(False)
    out.parm("lopoutput").set('$HIP/export/`chs("filename")`')
    out.parm("thumbnailmode").set(2)
    out.parm("renderer").set("RenderMan RIS")
    out.parm("thumbnailscenesource").set(1)
    out.parm("thumbnailinputcamera").set("/lookdev/cam")

    # Set Geometry as last selected
    geo.setSelected(True, clear_all_selected=True)

    return out


def _hide_contextoptions_folders(node: hou.Node) -> None:
    ptg = node.parmTemplateGroup()
    for f in ("Basic Options", "Time Based Options", "Pattern Matching Options"):
        ptg.hideFolder(f, True)
    node.setParmTemplateGroup(ptg)


def lnd_layoutgroup(kwargs: dict) -> hou.Node:
    contextoptions: hou.LopNode = loptoolutils.genericTool(kwargs, "editcontextoptions")

    pos = contextoptions.position()
    p = contextoptions.parent()
    beginblock = p.createNode("begincontextoptionsblock")
    groupprim = p.createNode("primitive")

    if old_inputs := contextoptions.inputs():
        beginblock.setInput(0, old_inputs[0])
    contextoptions.setInput(0, groupprim)
    contextoptions.parm("createoptionsblock").set(True)
    groupprim.setInput(0, beginblock)

    for n in (beginblock, groupprim, contextoptions):
        n.setColor(hou.Color(0.565, 0.494, 0.863))

    groupprim.setUserData("nodeshape", "chevron_down")
    contextoptions.setUserData("nodeshape", "chevron_up")

    beginblock.setName("beginlayoutgroup", True)
    groupprim.setName("layoutprim", True)
    contextoptions.setName("layoutgroup", True)

    groupprim.parm("primpath").set("`@PATH`")
    groupprim.parm("primkind").set("Group")
    groupprim.parm("parentprimtype").set("Scope")

    contextoptions.addSpareParmTuple(
        hou.StringParmTemplate(
            name="group", label="Group Name", num_components=1, default_value=("$OS",)
        )
    )
    contextoptions.parm("optioncount").insertMultiParmInstance(0)
    contextoptions.parm("optionname1").set("GROUP")
    contextoptions.parm("optionstrvalue1").set('`chs("./group")`')
    contextoptions.parm("optionname2").set("PATH")
    contextoptions.parm("optionstrvalue2").set(
        '/environment/`@ASSEMBLY`/`chs("./group")`'
    )

    contextoptions.parm("createoptionsblock").hide(True)
    _hide_contextoptions_folders(contextoptions)

    beginblock_move = hou.Vector2(0, 2.0)
    groupprim_move = hou.Vector2(0, 1.5)
    beginblock.setPosition(beginblock_move + pos)
    groupprim.setPosition(groupprim_move + pos)

    return contextoptions


def lnd_layout(kwargs: dict) -> hou.Node:
    contextoptions: hou.Node = loptoolutils.genericTool(kwargs, "editcontextoptions")

    pos = contextoptions.position()
    p = contextoptions.parent()
    envprim = p.createNode("primitive")
    layoutprim = p.createNode("primitive")
    merge = p.createNode("merge")

    contextoptions.setInput(0, merge)
    merge.setInput(0, layoutprim)
    layoutprim.setInput(0, envprim)

    contextoptions.setName("layout_name", True)
    envprim.setName("environment_xform", True)
    layoutprim.setName("assembly_prim", True)

    for n in (contextoptions, envprim, layoutprim, merge):
        n.setColor(hou.Color(0.188, 0.529, 0.45))

    envprim.setUserData("nodeshape", "chevron_down")
    layoutprim.setUserData("nodeshape", "chevron_down")
    contextoptions.setUserData("nodeshape", "chevron_up")

    envprim.parm("primpath").set("/environment")
    envprim.parm("parentprimtype").set("None")
    envprim.parm("primtype").set("UsdGeomXform")

    layoutprim.parm("primpath").set("`@PATH`")
    layoutprim.parm("primkind").set("Assembly")
    layoutprim.parm("parentprimtype").set("UsdGeomXform")

    contextoptions.addSpareParmTuple(
        hou.StringParmTemplate(
            name="assembly",
            label="Assembly Name",
            num_components=1,
            default_value=("$OS",),
        )
    )
    contextoptions.parm("optioncount").insertMultiParmInstance(0)
    contextoptions.parm("optionname1").set("ASSEMBLY")
    contextoptions.parm("optionstrvalue1").set('`chs("./assembly")`')
    contextoptions.parm("optionname2").set("PATH")
    contextoptions.parm("optionstrvalue2").set('/environment/`chs("./assembly")`')

    contextoptions.parm("createoptionsblock").hide(True)
    _hide_contextoptions_folders(contextoptions)

    envprim_move = hou.Vector2(0, 6.7)
    layoutprim_move = hou.Vector2(0, 6.0)
    merge_move = hou.Vector2(0, 1.0)
    envprim.setPosition(envprim_move + pos)
    layoutprim.setPosition(layoutprim_move + pos)
    merge.setPosition(merge_move + pos)

    return contextoptions