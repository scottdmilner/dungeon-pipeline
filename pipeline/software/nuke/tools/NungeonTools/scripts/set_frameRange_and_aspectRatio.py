import nuke
from pipe.db import DB
from env_sg import DB_Config
import os

project_file = nuke.root()["name"].value()


def get_project_name():
    project_name = ""
    if project_file:
        project_name_with_ext = os.path.basename(project_file)
        project_name, ext = os.path.splitext(project_name_with_ext)
    else:
        project_name = "Unsaved Project"
    return project_name


def get_frame_range(project_name):
    conn = DB.Get(DB_Config)
    shot_info = conn.get_shot_by_code(project_name)
    return [shot_info.cut_in, shot_info.cut_out]


def set_frame_range(frame_in, frame_out):
    nuke.root()["first_frame"].setValue(frame_in)
    nuke.root()["last_frame"].setValue(frame_out)
    nuke.root()["lock_range"].setValue(True)


def set_full_frame_size(root_node):
    root_node["format"].setValue("Love_and_Dungeons_aspect_ratio")


def set_frame_rate(root_node):
    root_node["fps"].setValue(24)


def run():
    project_name = get_project_name()
    root_node = nuke.root()
    set_full_frame_size(root_node)

    # set frame range if the file is saved
    if project_name == "Unsaved Project":
        return
    else:
        frame_in, frame_out = get_frame_range(project_name)
        print("Frame out: " + str(frame_out))
        set_frame_range(frame_in, frame_out)
        set_frame_rate(root_node)


# run()
