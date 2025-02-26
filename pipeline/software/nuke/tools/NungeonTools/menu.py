import nuke
from shared.util import get_pipe_path

nuke.pluginAddPath("./gizmos")
nuke.pluginAddPath("./icons")
nuke.pluginAddPath("./images")
nuke.pluginAddPath("./nk_files")
nuke.pluginAddPath("./toolsets")
nuke.pluginAddPath("./scripts")


# Nungeon buttons
toolbar = nuke.menu("Nodes")
m = toolbar.addMenu("Nungeon", icon="nungeonIcon.png")
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


# aspect ratio
nuke.addFormat("1920 816 Love_and_Dungeons_aspect_ratio")


# Shelf Tools
def import_render_layers():
    import render_layer_selector  # type: ignore[import-not-found]

    render_layer_selector.run()


def choose_shot():
    import open_shot  # type: ignore[import-not-found]

    open_shot.run()


menu = nuke.menu("Nuke")
menu.addCommand("Choose Shot", "choose_shot()")
menu.addCommand("Import Render Layers", "import_render_layers()")


print("Nungeon loaded successfully")
print(
    "Isaac is a robot. If you train him the same way you train an AI model you will get good results."
)
