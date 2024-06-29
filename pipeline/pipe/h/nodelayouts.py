# mypy: disable-error-code="union-attr"
import hou
import loptoolutils  # type: ignore[import-not-found]

from typing import Optional

"""Scripts for building node setups. Called by lnd_nodelayouts.hdanc in Interacter > Shelf Tools"""


def lnd_componentgeometry(kwargs: dict, parent: Optional[hou.Node] = None) -> hou.Node:
    if parent:
        cgeo = parent.createNode("componentgeometry")
    else:
        cgeo = loptoolutils.genericTool(kwargs, "componentgeometry")

    # Set up nodes inside of Component Geometry
    geo_sop = hou.node(cgeo.path() + "/sopnet/geo")
    geo_sop.loadItemsFromFile(
        hou.hscriptStringExpression("$HSITE") + "/sop/component.cpio"
    )
    gsp = geo_sop.path()
    for name in ["default", "proxy", "simproxy"]:
        hou.node(gsp + "/" + name).setInput(0, hou.node(gsp + "/OUT_" + name))

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
    edit = hou.node(cmat.path() + "/edit")
    assign = edit.createNode("assignmaterial")
    assign.setInput(0, edit.indirectInputs()[0])
    hou.node(edit.path() + "/output0").setInput(0, assign)
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
    # err = p.createNode("error")
    out.setInput(0, mtl)
    mtl.setInput(0, geo)
    mtl.setInput(1, lib)
    # err.setInput(0, mtl)

    # Arrange nodes in "Y" shape
    geo_move = hou.Vector2(-1.22, 2.5)
    mtl_move = hou.Vector2(0, 1.0)
    lib_move = hou.Vector2(1.22, 2.0)
    # err_move = hou.Vector2(0, 1.0)
    mtl.setPosition(mtl_move + out_pos)
    lib.setPosition(lib_move + out_pos)
    geo.setPosition(geo_move + out_pos)
    # err.setPosition(err_move + out_pos)

    # Channel Reference the root prim to the material library
    lib_prefix_parm = hou.node(lib.path() + "/Material_Library").parm("matpathprefix")
    lib_prefix_parm.set("/ASSET/mtl/")

    # # Configure Error node
    # err.parm("errormsg1").set("Please ensure all Component Geometry nodes are named based off of their variant!")
    # err.parm("serverity1").set("error")
    # err.parm("enable1").setExpression("any('componentgeometry' in node.name() for node in hou.pwd().inputAncestors())", hou.exprLanguage.Python)

    # Configure Component Output node
    asset_name = hou.hscriptStringExpression("$HIP").split("/")[-1]
    out.parm("rootprim").set("/" + asset_name)
    out.parm("localize").set(False)
    out.parm("variantlayers").set(True)
    out.parm("lopoutput").set('$HIP/export/`chs("filename")`')

    # Set Geometry as last selected
    geo.setSelected(True, clear_all_selected=True)

    return out
