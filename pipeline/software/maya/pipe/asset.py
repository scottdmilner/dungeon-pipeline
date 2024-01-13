import os
import platform
import shutil

import maya.cmds as mc

import pipe


def publish() -> None:
    system = platform.system()

    dialog = mc.promptDialog(
        message="Please type the name of the asset",
        title="Asset Export",
        button=["OK", "Cancel"],
        defaultButton="OK",
        cancelButton="Cancel",
        dismissString="Cancel",
    )

    if dialog != "OK":
        return

    asset_name = mc.promptDialog(query=True, text=True).rstrip(" ")
    publish_dir = pipe.util.get_asset_path() / asset_name
    publish_dir.mkdir(exist_ok=True)

    publish_path = str(publish_dir / asset_name) + ".usd"
    temp_publish_path = os.getenv("TEMP") + asset_name + ".usd"

    # save the file
    mc.file(
        publish_path if system == "Linux" else temp_publish_path,
        options=";".join(
            [
                "",
                "exportUVs=1",
                "exportSkels=none",
                "exportSkin=none",
                "exportBlendShapes=0",
                "exportDisplayColor=0",
                "exportColorSets=1",
                "exportComponentTags=1",
                "defaultMeshScheme=catmullClark",
                "animation=0",
                "eulerFilter=0",
                "staticSingleSample=0",
                "startTime=1",
                "endTime=1",
                "frameStride=1",
                "frameSample=0.0",
                "defaultUSDFormat=usdc",
                "parentScope=" + asset_name,
                "shadingMode=useRegistry",
                "convertMaterialsTo=[UsdPreviewSurface]",
                "exportInstances=1",
                "exportVisibility=0",
                "mergeTransformAndShape=1",
                "stripNamespaces=0",
                "worldspace=0",
            ]
        ),
        type="USD Export",
        preserveReferences=True,
        exportSelected=True,
    )

    # if on Windows, work around this bug: https://github.com/PixarAnimationStudios/OpenUSD/issues/849
    # TODO: check if this is still needed in Maya 2025
    if system == "Windows":
        shutil.move(temp_publish_path, publish_path)

    mc.confirmDialog(
        message=f"The selected objects have been exported to {publish_path}"
    )
