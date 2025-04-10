import nuke
from shared.util import get_pipe_path

nuke.pluginAddPath("./gizmos")
nuke.pluginAddPath("./icons")
nuke.pluginAddPath("./images")
nuke.pluginAddPath("./nk_files")
nuke.pluginAddPath("./toolsets")
nuke.pluginAddPath("./scripts")

# aspect ratio
nuke.addFormat("1920 816 Love_and_Dungeons_aspect_ratio")


def make_ld_write_node():
    import ld_write_node_v2  # type: ignore[import-not-found]

    ld_write_node_v2.main()


def import_render_layers():
    import render_layer_selector  # type: ignore[import-not-found]

    render_layer_selector.run()


def import_USD_cam():
    import import_usd_camera  # type: ignore[import-not-found]

    import_usd_camera.run()


def choose_shot():
    import open_shot  # type: ignore[import-not-found]

    open_shot.run()


def set_frameRange_and_aspectRatio():
    import set_frameRange_and_aspectRatio  # type: ignore[import-not-found]

    set_frameRange_and_aspectRatio.run()


################################### Nungeon buttons (Sidebar) ###################################
toolbar = nuke.menu("Nodes")
m = toolbar.addMenu("Nungeon", icon="nungeonIcon.png")


m.addCommand(
    "Template",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/shotTemplate.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Depth Fog",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/depth_fog.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Deep Fog",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/deep_fog.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Relight",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/relight_template.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Eye Light",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/eyelights.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Sky Dome (Basic)",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/ld_skydome.nk")}")',
    icon="nungeonIcon.png",
)

#m.addCommand("FrameBurn", "nuke.createNode('FrameBurn')", icon="nungeonIcon.png")
m.addCommand("Grade_AOV", "nuke.createNode('grade_AOV')", icon="nungeonIcon.png")
m.addCommand("luma Distort", "nuke.createNode('lumaDistort')", icon="nungeonIcon.png")
m.addCommand("Roughen Edges", "nuke.createNode('roughenEdges')", icon="nungeonIcon.png")
# lens node
m.addCommand("Lens", "nuke.createNode('Lens')", icon="nungeonIcon.png")
print(
    f"nuke.nodePaste({str(get_pipe_path() / 'software/nuke/tools/NungeonTools/toolsets/shotTemplate.nk')})"
)
m.addCommand("L&D Write Node", "make_ld_write_node()", icon="nungeonIcon.png")


################################### Nungeon Shelf Tool Buttons ###################################
menu = nuke.menu("Nuke")
menu.addCommand("[Choose Shot]", "choose_shot()")
menu.addCommand("[Import Render Layers]", "import_render_layers()")
menu.addCommand("[Import USD Camera]", "import_USD_cam()")
menu.addCommand("[Set Project Settings]", "set_frameRange_and_aspectRatio()")
