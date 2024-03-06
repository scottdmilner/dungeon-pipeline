import maya.cmds as mc
import os
import pipe.util


def publish(file_name):
    dir_path = pipe.util.get_rigging_path() / file_name / "RigVersions"
    link_dir_path = pipe.util.get_anim_path() / "rigs"

    # search directory for all versions and determine new version number
    ls_dir = dir_path.iterdir()
    latest_version = 0

    for item in ls_dir:
        version = int(item.split(".")[-2])
        if version > latest_version:
            latest_version = version

    v_string = str(latest_version + 1).zfill(3)

    # save file to path
    full_name = dir_path / f"{file_name}.{v_string}.mb"
    mc.file(rename=full_name)
    saved = mc.file(s=True, f=True, typ="mayaBinary")

    print(f"File saved to '{saved}'")

    # create symlink
    temp_name = f"/{link_dir_path}/tmp"
    os.symlink(full_name, temp_name)
    os.rename(temp_name, f"{link_dir_path}/{file_name}.mb")

    print(f"Link to file created or updated at '{link_dir_path}/{file_name}.mb'\n")


# crappy little UI
def rig_publish_UI():
    window_id = "rig_pub"
    if mc.window(window_id, exists=True):
        mc.deleteUI(window_id)

    mc.window(window_id, title="Rig Publish", sizeable=False, resizeToFitChildren=True)

    # need to create an attr to tie the enum to. gets deleted on finishing publish.
    if mc.objExists("rig_pub"):
        mc.delete("rig_pub")
    mc.createNode("condition", name="rig_pub")
    mc.addAttr("rig_pub", ln="publish")

    rigs = [
        (0, "Robin"),
        (1, "Rayden"),
        (2, "Crossbow"),
        (3, "Loot Bag"),
        (4, "Door"),
        (5, "test"),
    ]

    mc.columnLayout()
    sel = mc.attrEnumOptionMenuGrp(l="Rig Name", at="rig_pub.publish", ei=rigs)

    # confirm dialog to avoid overwriting the incorrect files
    def onPress():
        fn = rigs[int(mc.getAttr("rig_pub.publish"))][1]
        conf = mc.confirmDialog(
            title="WARNING",
            message=f'Are you sure you want to publish this rig for "{fn}"? A mistake will mean you need to go fix things by hand!',
            button=["Yes", "No"],
            defaultButton="No",
            cancelButton="No",
            dismissString="No",
            backgroundColor=[255, 0, 0],
        )

        mc.delete("rig_pub")
        if conf == "Yes":
            publish(fn)
        mc.deleteUI("rig_pub")

    mc.button(label="Publish", command=lambda _: onPress())

    mc.showWindow()


def run():
    rig_publish_UI()
