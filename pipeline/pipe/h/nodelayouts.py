# mypy: disable-error-code="union-attr"
import hou
import loptoolutils  # type: ignore[import-not-found]

from typing import Optional

"""Scripts for building node setups. Called by lnd_nodelayouts.hdanc in Interactive > Shelf Tools"""


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
    out.parm("variantlayers").set(True)
    out.parm("lopoutput").set('$HIP/export/`chs("filename")`')
    out.parm("thumbnailmode").set(2)
    out.parm("renderer").set("RenderMan RIS")
    out.parm("thumbnailscenesource").set(1)
    out.parm("thumbnailinputcamera").set("/lookdev/cam")

    # Set Geometry as last selected
    geo.setSelected(True, clear_all_selected=True)

    return out
