import hou

# set the default flipbook resolution
scene = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
fb_settings = scene.flipbookSettings()  # type: ignore[union-attr]
fb_settings.resolution((1920, 816))
