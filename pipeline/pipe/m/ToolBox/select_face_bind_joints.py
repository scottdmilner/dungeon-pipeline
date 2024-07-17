import maya.cmds as cmds
def face_bind_selection(*args):
    # Get a list of all objects in the scene
    all_objects = cmds.ls(type='transform', visible=True)

    # Initialize an empty list to store objects with the attribute set to True
    selected_objects = []

    # Iterate over each object to check if it has the attribute "face_bind_joint" set to True
    for obj in all_objects:
        if cmds.attributeQuery('face_bind_joint', node=obj, exists=True):
            value = cmds.getAttr(obj + '.face_bind_joint')
            if value:
                selected_objects.append(obj)

    # Select the objects that have the attribute set to True
    if selected_objects:
        cmds.select(selected_objects)
    else:
        print("No objects found with 'face_bind_joint' attribute set to True.")
