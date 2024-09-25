import nuke

nuke.pluginAddPath("./gizmos")
nuke.pluginAddPath("./icons")
nuke.pluginAddPath("./images")
nuke.pluginAddPath("./nk_files")
nuke.pluginAddPath("./toolsets")

# Nungeon buttons
toolbar = nuke.menu("Nodes")
m = toolbar.addMenu("Nungeon", icon="nungeonIcon.png")
m.addCommand("Lens", "nuke.createNode('Lens')", icon="nungeonIcon.png")
m.addCommand(
    "Template",
    "nuke.nodePaste('/groups/dungeons/pipeline/software/nuke/tools/NungeonTools/toolsets/shotTemplate.nk')",
    icon="nungeonIcon.png",
)


# asoect ratio
nuke.addFormat("2048 870 Love_and_Dungeons_aspect_ratio")
nuke.knobDefault("Root.format", "Love_and_Dungeons_aspect_ratio")

print("Nungeon loaded successfully")
