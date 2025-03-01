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
    import ld_write_node  # type: ignore[import-not-found]

    ld_write_node.main()


def import_render_layers():
    import render_layer_selector  # type: ignore[import-not-found]

    render_layer_selector.run()


def choose_shot():
    import open_shot  # type: ignore[import-not-found]

    open_shot.run()


################################### Nungeon buttons (Sidebar) ###################################
toolbar = nuke.menu("Nodes")
m = toolbar.addMenu("Nungeon", icon="nungeonIcon.png")

# lens node
m.addCommand("Lens", "nuke.createNode('Lens')", icon="nungeonIcon.png")
print(
    f"nuke.nodePaste({str(get_pipe_path() / 'software/nuke/tools/NungeonTools/toolsets/shotTemplate.nk')})"
)
m.addCommand(
    "Template",
    f"nuke.nodePaste(\"{str(get_pipe_path() / 'software/nuke/tools/NungeonTools/toolsets/shotTemplate.nk')}\")",
    icon="nungeonIcon.png",
)
m.addCommand("FrameBurn", "nuke.createNode('FrameBurn')", icon="nungeonIcon.png")

m.addCommand("L&D Write Node", "make_ld_write_node()", icon="nungeonIcon.png")


################################### Nungeon Shelf Tool Buttons ###################################
menu = nuke.menu("Nuke")
menu.addCommand("Choose Shot", "choose_shot()")
menu.addCommand("Import Render Layers", "import_render_layers()")
