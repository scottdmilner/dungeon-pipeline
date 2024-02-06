import maya.cmds as cmds
import json

config_file = "G:\\shrineflow\\pipeline\\pipeline\\software\\maya\\pipe\\camera_location_config.txt"
ninja_cam_name = "cam_ninja1"
kitsune_cam_name = "cam_kitsune1"
ninja_rig_name = "Ninja_Rig:Ninja_Rig"
# ninja_rig_name = "Ninja_Rig"
kitsune_rig_name = "Kitsune_Rig:Kitsune_Rig"
# kitsune_rig_name = "Kitsune_Rig"

# TODO:
# - 

# move the camera to transform (and lock everything)
def check_camera(nk):
    camera_name = ninja_cam_name if nk else kitsune_cam_name
    # Use ls command to list objects with the specified name and type
    cameras = cmds.ls(camera_name, type='camera')

    # Check if any cameras were found
    if cameras:
        return cameras[0][0]  # Return the first found camera
    else:
        return create_camera(camera_name)  # Return None if no camera with the specified name was found


def create_camera(camera_name):
    # Create a new perspective camera
    new_camera = cmds.camera(name=camera_name, position=(0, 0, 0), rotation=(0, 0, 0), horizontalFieldOfView=90.0)

    # # Set the camera as the active view
    # cmds.lookThru(new_camera)
    return new_camera[0]

def lock_camera(nk, camera_name):
    # camera_name = ninja_cam_name if nk else kitsune_cam_name
    cmds.setAttr(f'{camera_name}.translateX', lock=True)
    cmds.setAttr(f'{camera_name}.translateY', lock=True)
    cmds.setAttr(f'{camera_name}.translateZ', lock=True)

    # Lock rotation attributes (rx, ry, rz)
    cmds.setAttr(f'{camera_name}.rotateX', lock=True)
    cmds.setAttr(f'{camera_name}.rotateY', lock=True)
    cmds.setAttr(f'{camera_name}.rotateZ', lock=True)

    # Lock scale attributes (sx, sy, sz)
    cmds.setAttr(f'{camera_name}.scaleX', lock=True)
    cmds.setAttr(f'{camera_name}.scaleY', lock=True)
    cmds.setAttr(f'{camera_name}.scaleZ', lock=True)

def import_data(nk):
    imported_data = None
    try:
        with open(config_file, "r") as file:
            imported_data = json.load(file)
    except FileNotFoundError:
        print("Error: Config file not found.")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return

    # get data based on ninja or kitsune
    data = None
    if nk:
        data = imported_data.get("ninja")
    else:
        data = imported_data.get("kitsune")

    if not data:
        print("Error: Data not found for the specified character.")
        return

    return data

def move_camera(nk, camera_name, height=0, scale=1):
    # camera_name = ninja_cam_name if nk else kitsune_cam_name
    data = import_data(nk)

    

    # # Get the active 3D view panel
    # active_panel = cmds.getPanel(withFocus=True)
    # if cmds.getPanel(typeOf=active_panel) != "modelPanel":
    #     print("Error: The active panel is not a 3D view.")
    #     return

    # # Get the active camera in the panel
    # active_camera = cmds.modelPanel(active_panel, query=True, camera=True)

    # # Get the camera transform node
    # camera_transform = cmds.listRelatives(active_camera, parent=True, fullPath=True)

    # if not active_camera or not camera_transform:
    #     print("Error: Unable to retrieve active camera or its transform.")
    #     return

    # Set the target coordinates
    target_coordinates = (-data.get("try", 0) * scale, (data.get("trz", 0) * scale) + (height / 2), data.get("trx", 0) * scale)
    # target_coordinates = (data.get("trx", 0), data.get("try", 0), data.get("trz", 0))
    target_rotation = (data.get("roty", 0), data.get("rotz", 0) + 180.0, data.get("rotx", 0))

    # Move the camera to the specified coordinates
    cmds.xform(camera_name, translation=target_coordinates, rotation=target_rotation, worldSpace=True)
    # cmds.xform(camera_transform, translation=target_coordinates, rotation=target_rotation, worldSpace=True)

# move_active_camera_to_coordinates(True)

def get_scale_and_height(nk):
    # THIS IS ASSUMING THAT THE NINJA OR KITSUNE RIG IS ALREADY IN THE EDITOR
    data = import_data(nk)
    rig_name = None
    rig_name = ninja_rig_name if nk else kitsune_rig_name
    # float[]	xmin, ymin, zmin, xmax, ymax, zmax.
    bb = cmds.exactWorldBoundingBox(rig_name)
    height = bb[4]
    # height = bb[4] - bb[1] # uhhh i guess the character will always be on the floor, so just max y should be fine?
    scale = height / data.get("height")
    return scale, height



def run(nk):
    # cam_name = ninja_cam_name if nk else kitsune_cam_name  
    scale, height = get_scale_and_height(nk)
    camera_name = check_camera(nk)
    move_camera(nk,camera_name, height, scale)
    lock_camera(nk, camera_name)

    # check for existing camera (depending)
    # if exist, grab that camera
    # else, make that camera


# import maya.cmds as cmds
# import json

# config_file = "G:\\shrineflow\\pipeline\\pipeline\\software\\maya\\pipe\\camera_location_config.txt"

# # struct coordinates:

# def move_active_camera_to_coordinates(nk):
#     file = open(config_file,"r")
#     imported_data = json.loads(file.read())
#     # data = json.loads(file.readline())
#     print(imported_data)

#     # get data based on ninja or kitsune
#     data = None
#     if nk:
#         data = imported_data.get("ninja") 
#     else:
#         data = imported_data.get("kitsune")
    
#     # Get the active 3D view
#     active_panel = cmds.getPanel(withFocus=True)

#     # Get the active camera in the panel
#     active_camera = cmds.modelPanel(active_panel, query=True, camera=True)

#     # Get the camera transform node
#     camera_transform = cmds.listRelatives(active_camera, parent=True, fullPath=True)[0]

#     # Set the target coordinates
#     target_coordinates = (data.get("x"), data.get("y"), data.get("z"))

#     # Move the camera to the specified coordinates
#     cmds.xform(camera_transform, translation=target_coordinates, worldSpace=True)
