import os
import datetime
import nuke
import re
import json
from pipe.db import DB
from env_sg import DB_Config
from shared.util import get_production_path

project_file = nuke.root()["name"].value()


def make_text_nodes():
    # Text Padding
    rl_padding = 25
    tb_padding = 25
    font_size = 25
    frame_height = 816
    frame_width = 1920

    # Frame Number
    frame_num_text = nuke.createNode("Text2", "font_size 30")
    frame_num_text.knob("font_size").setValue(font_size)
    frame_num_text.knob("box").setValue(
        [rl_padding, tb_padding, frame_width - rl_padding, frame_height - tb_padding]
    )
    frame_num_text.knob("xjustify").setValue("right")
    frame_num_text.knob("yjustify").setValue("bottom")
    frame_num_text.knob("enable_background").setValue(1)
    frame_num_text.setName("Frame_Number")
    # message set below to force the font size to update

    # Department
    department_text = nuke.createNode("Text2")
    department_text.knob("font_size").setValue(font_size)
    department_text.knob("box").setValue(
        [
            rl_padding,
            tb_padding * 2 + font_size * 3,
            frame_width - rl_padding,
            frame_height,
        ]
    )
    department_text.knob("xjustify").setValue("left")
    department_text.knob("yjustify").setValue("bottom")
    department_text.knob("enable_background").setValue(1)
    department_text.setName("department_text")
    dropdown_knob = nuke.Enumeration_Knob(
        "departmentDropdown", "departmentDropdown", ["Lighting", "Compositing"]
    )
    department_text.addKnob(dropdown_knob)
    # message set below to force the font size to update

    # Shot Code
    shot_code_text = nuke.createNode("Text2")
    shot_code_text.knob("font_size").setValue(font_size)
    shot_code_text.knob("box").setValue(
        [rl_padding, tb_padding + font_size * 2, frame_width - rl_padding, frame_height]
    )
    shot_code_text.knob("xjustify").setValue("right")
    shot_code_text.knob("yjustify").setValue("bottom")
    shot_code_text.knob("enable_background").setValue(1)
    shot_code_text.setName("Shot_Code")
    # message set below to force the font size to update

    # date
    date_text = nuke.createNode("Text2")
    date_text.knob("font_size").setValue(font_size)
    date_text.knob("box").setValue(
        [rl_padding, tb_padding + font_size * 2, frame_width - rl_padding, frame_height]
    )
    date_text.knob("xjustify").setValue("left")
    date_text.knob("yjustify").setValue("bottom")
    date_text.knob("enable_background").setValue(1)
    date_text.setName("date")
    # message set below to force the font size to update

    # user name
    name_text = nuke.createNode("Text2")
    name_text.knob("font_size").setValue(font_size)
    name_text.knob("box").setValue(
        [rl_padding, tb_padding, frame_width - rl_padding, frame_height - tb_padding]
    )
    name_text.knob("xjustify").setValue("left")
    name_text.knob("yjustify").setValue("bottom")
    name_text.knob("enable_background").setValue(1)
    name_text.setName("name")
    # message set below to force the font size to update

    blur_node = nuke.createNode("Blur")
    nuke.delete(
        blur_node
    )  # What's this for? Idk why, but this makes it so the user name isn't gigantic. idk why.

    # set text node message values (because if I don't do it here, the font size won't update in time and you'll just have big massive font sizes)

    return [frame_num_text, shot_code_text, date_text, name_text, department_text]


def update_text_messages(
    frame_num_text, shot_code_text, date_text, name_text, department_text
):
    frame_num_text.knob("message").setValue("Frame: [frame]")
    shot_code_text.knob("message").setValue(get_project_name())
    date_text.knob("message").setValue(get_date())
    name_text.knob("message").setValue(str(get_users_name()))

    # department dropdown and text
    department_text.knob("message").setValue("[value departmentDropdown]")


def get_in_out():
    curr_shot = get_project_name()
    conn = DB.Get(DB_Config)
    print(str(curr_shot))
    shot_info = conn.get_shot_by_code(curr_shot)
    # print(curr_shot)
    # print(shot_info.cut_in)
    # print(shot_info.cut_out)
    return [shot_info.cut_in, shot_info.cut_out]


def get_project_name():
    project_name = ""
    if project_file:
        project_name_with_ext = os.path.basename(project_file)
        project_name, ext = os.path.splitext(project_name_with_ext)
    else:
        project_name = "Unsaved Project"
    return project_name


def get_date():
    today = datetime.date.today()
    formatted_date = today.strftime("%m/%d/%Y")
    return formatted_date


def get_users_name():
    """
    Returns the full name corresponding to the current user's login as defined in usernames.json.
    If the username is not found in the JSON file, returns None.
    """
    # Get the current login username
    username = os.getlogin()
    

    # Determine the path to the usernames.json file in the same directory as this script.
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    # json_path = "/users/animation/sblancha/dev/dungeon-pipeline/pipeline/software/nuke/tools/NungeonTools/scripts/usernames.json"

    json_path = str(get_production_path()) + "/json/usernames.json"
    # print(str(json_path))

    # Open and load the JSON file.
    with open(json_path, "r") as f:
        user_data = json.load(f)

    # Return the corresponding name for the username.
    # If the key is not found, .get() will return None.
    return user_data.get(username)


def get_output_file_info_mov():
    base_path = "/groups/dungeons/edit/shots/lighting/"
    shot_code = os.path.splitext(os.path.basename(nuke.root().name()))[0]

    # Construct the folder path
    folder_path = os.path.join(base_path, shot_code)

    # If the folder doesn't exist, default to version 001.
    if not os.path.exists(folder_path):
        new_file_name = f"{shot_code}_V001.mov"
    else:
        all_file_names = os.listdir(folder_path)
        # Extract version numbers from file names that match the pattern.
        version_numbers = [
            int(re.search(r"_V(\d+)", f).group(1))
            for f in all_file_names
            if re.search(r"_V\d+", f)
        ]
        next_version = (max(version_numbers) if version_numbers else 0) + 1
        new_file_name = f"{shot_code}_V{next_version:03d}.mov"

    return [new_file_name, folder_path]


def get_output_file_info_exr():
    base_path = "/groups/dungeons/edit/shots/comp/"

    # setting the file parameter
    file_name = os.path.splitext(os.path.basename(nuke.root().name()))[0]
    folder_path = base_path + file_name
    full_path = folder_path + "/" + file_name + ".###.exr"
    return [folder_path, full_path]


def make_MOV_node():
    new_file_name = get_output_file_info_mov()[0]
    folder_path = get_output_file_info_mov()[1]

    # Create the full file path.
    full_path = os.path.join(folder_path, new_file_name)
    # print("full file path: " + full_path)

    write_node = nuke.createNode("Write")
    write_node.setName("MOV_write")

    # Set file and file type.
    write_node["file"].setValue(full_path)
    write_node["file_type"].setValue("mov64")

    # Create directories automatically.
    write_node["create_directories"].setValue(1)

    # Other write node settings.
    write_node["colorspace"].setValue(6)  # Data (linear-rawr)
    write_node["transformType"].setValue(1)  # Display transform
    write_node["mov64_codec"].setValue(
        12
    )  # Avid DnxHr (integer value 12 for some reason)
    write_node["mov64_dnxhd_codec_profile"].setValue(1)  # DNxHD 422 10-bit 220Mbit

    # Example: touching the file after render (using the new file name)
    command = 'os.system("touch ' + os.path.join(folder_path, new_file_name) + '")'
    write_node["afterRender"].setValue(command)

    return write_node


def update_mov_node(write_node):
    # print("in the update mov node")
    write_node["mov64_codec"].setValue(
        13
    )  # option 13 should be Avid DnxHr WHY NOT 3?? Idk
    write_node["mov64_dnxhd_codec_profile"].setValue(
        0
    )  # option 1 should be 4:4:4 12 bit


def make_EXR_node():
    # folder_path = get_output_file_info_exr()[0]
    full_path = get_output_file_info_exr()[1]

    write_node = nuke.createNode("Write")
    write_node["file"].setValue(full_path)
    write_node.setName("EXR_write")

    # create directories
    write_node["create_directories"].setValue(1)

    # TODO set exr settings and stuff
    write_node["write_ACES_compliant_EXR"].setValue(1)
    write_node["colorspace"].setValue(7)  # Data (linear-rawr)
    write_node["transformType"].setValue(0)  # Display transform
    return write_node


def check_saved():
    current_script_name = os.path.splitext(os.path.basename(nuke.root().name()))[0]
    if current_script_name == "Root":
        nuke.message(
            "This nuke script isn't saved, so I don't know what shot you're wanting to write out! Please save your shot!"
        )
        return False
    else:
        return True


def makeUI(groupNode):
    # groupNode = nuke.createNode("NoOp")
    # tab 1 (mov export)
    mov_tab_name = "MOV Export"
    tab_knob = nuke.Tab_Knob(mov_tab_name)
    groupNode.addKnob(tab_knob)

    # Define the script for the PyScript_Knob.
    mov_export_script = """
group = nuke.thisNode()
# Read the frame range from the node's custom knobs.
first_frame = int(group["export_frame_in"].value())
last_frame  = int(group["export_frame_out"].value())

group.begin()  # Enter the group's internal node graph.
write_node = nuke.toNode("MOV_write")
if write_node:
    nuke.execute(write_node.name(), first_frame, last_frame, 1)
else:
    nuke.message("MOV_write node not found inside the group!")
group.end()  # Exit the group.
    """
    # render button
    mov_export_button = nuke.PyScript_Knob(
        "mov_export", "Export MOV", mov_export_script
    )

    new_file_name = get_output_file_info_mov()[0]
    folder_path = get_output_file_info_mov()[1]

    # Create the full file path.
    full_path = os.path.join(folder_path, new_file_name)

    mov_export_path = nuke.Text_Knob("mov_export_path", "")
    mov_export_path.setValue(full_path)
    # mov_export_path.clearFlag(nuke.STARTLINE)

    button_script_open_file = """
import os
import nuke

folder = "{folder_path}"
if not os.path.exists(folder):
    nuke.message("This folder does not exist yet, but it will after you export")
else:
    os.system("xdg-open '" + folder + "'")
""".format(folder_path=folder_path)

    # Create the PyScript_Knob with the script above.
    open_folder_button = nuke.PyScript_Knob(
        "open_folder", "Open Folder", button_script_open_file
    )
    open_folder_button.clearFlag(nuke.STARTLINE)

    # frame range note
    # cut_info = get_in_out()
    frame_range = nuke.Text_Knob("frame_range", "")
    frame_range.setValue(
        "Frame range is currently set to:"
    )  # + str(cut_info[0]) + "-" + str(cut_info[1]))

    # frame ranges
    frame_in = nuke.Int_Knob("export_frame_in", "")
    frame_in.setValue(get_in_out()[0])
    frame_out = nuke.Int_Knob("export_frame_out", "")
    frame_out.setValue(get_in_out()[1])
    frame_out.clearFlag(nuke.STARTLINE)

    groupNode.addKnob(mov_export_button)
    groupNode.addKnob(frame_range)
    groupNode.addKnob(frame_in)
    groupNode.addKnob(frame_out)

    # checkboxes
    checkbox1 = nuke.Boolean_Knob("disable_text", "Disable On Screen Text")

    # dividers
    divider1 = nuke.Text_Knob("divider1", "")
    divider2 = nuke.Text_Knob("divider2", "")
    divider3 = nuke.Text_Knob("divider3", "")

    # dropdown
    department_dropdown = nuke.Enumeration_Knob(
        "departmentDropdown", "", ["Lighting", "Compositing"]
    )

    # add all knobs to node
    groupNode.addKnob(divider1)
    groupNode.addKnob(department_dropdown)
    groupNode.addKnob(checkbox1)  # disable on screen text
    groupNode.addKnob(divider2)
    groupNode.addKnob(mov_export_path)
    groupNode.addKnob(open_folder_button)

    # EXR    EXR EXR EXR     EXR EXR     EXR EXR
    # tab 1 (EXR export)
    exr_tab_name = "EXR Export"
    tab_knob = nuke.Tab_Knob(exr_tab_name)
    groupNode.addKnob(tab_knob)

    exr_export_script = """
group = nuke.thisNode()
# Read the frame range from the node's custom knobs.
first_frame = int(group["export_frame_in_exr"].value())
last_frame  = int(group["export_frame_out_exr"].value())

group.begin()  # Enter the group's internal node graph.
write_node = nuke.toNode("EXR_write")
if write_node:
    nuke.execute(write_node.name(), first_frame, last_frame, 1)
else:
    nuke.message("EXR_write node not found inside the group!")
group.end()  # Exit the group.
    """

    # render button
    mov_export_button = nuke.PyScript_Knob(
        "exr_export", "Export EXR", exr_export_script
    )

    # frame range note
    frame_range = nuke.Text_Knob("frame_range_exr", "")
    frame_range.setValue(
        "Frame range is currently set to:"
    )  # + str(cut_info[0]) + "-" + str(cut_info[1]) + "\n\n")

    # frame ranges
    frame_in_exr = nuke.Int_Knob("export_frame_in_exr", "")
    frame_in_exr.setValue(get_in_out()[0])
    frame_out_exr = nuke.Int_Knob("export_frame_out_exr", "")
    frame_out_exr.setValue(get_in_out()[1])
    frame_out_exr.clearFlag(nuke.STARTLINE)

    # Exr render note
    note_exr = nuke.Text_Knob("note_exr", "")
    note_exr.setValue("\n(Please note, EXR's will NOT have text overlay)\n")
    full_path = get_output_file_info_exr()[1]
    folder_path = get_output_file_info_exr()[0]
    exr_export_path = nuke.Text_Knob("exr_export_path", "")
    exr_export_path.setValue(full_path)
    # mov_export_path.clearFlag(nuke.STARTLINE)

    button_script_open_file = """
import os
import nuke

folder = "{folder_path}"
if not os.path.exists(folder):
    nuke.message("This folder does not exist yet, but it will after you export")
else:
    os.system("xdg-open '" + folder + "'")
""".format(folder_path=folder_path)

    # Create the PyScript_Knob with the script above.
    open_folder_button_exr = nuke.PyScript_Knob(
        "open_folder", "Open Folder", button_script_open_file
    )
    open_folder_button_exr.clearFlag(nuke.STARTLINE)

    groupNode.addKnob(mov_export_button)
    groupNode.addKnob(frame_range)
    groupNode.addKnob(frame_in_exr)
    groupNode.addKnob(frame_out_exr)

    groupNode.addKnob(note_exr)

    groupNode.addKnob(divider3)
    groupNode.addKnob(exr_export_path)
    groupNode.addKnob(open_folder_button_exr)


def createLinks(groupNode, text_nodes, mov_node, exr_node, switch):
    # mov export tab:
    switch["which"].setExpression("parent.disable_text")
    text_nodes[4]["departmentDropdown"].setExpression(
        "parent.departmentDropdown"
    )  # department


def main():
    if check_saved():
        current_node = None
        selected_nodes = nuke.selectedNodes()
        if selected_nodes:
            current_node = selected_nodes[0]

        base_name = "LD_Write"
        final_name = base_name

        # Check if a node with the base name exists.
        if nuke.toNode(base_name) is not None:
            count = 2  # Start numbering at 2.
            final_name = "{}{}".format(base_name, count)
            # Increment count until a unique name is found.
            while nuke.toNode(final_name) is not None:
                count += 1
                final_name = "{}{}".format(base_name, count)

        # Create the group node and set its name to the unique name.
        groupNode = nuke.createNode("Group")
        groupNode["name"].setValue(final_name)

        # Enter the group to build its internal node graph.
        groupNode.begin()

        # input_node
        input_node = nuke.createNode("Input")

        # All text nodes
        text_nodes = make_text_nodes()

        # Switch Node
        text_node_pos_x = text_nodes[3].xpos()
        text_node_pos_y = text_nodes[3].ypos()
        switcheroo = nuke.createNode("Switch")
        switcheroo.setInput(0, text_nodes[3])
        switcheroo.setInput(1, input_node)
        switcheroo.setXYpos(text_node_pos_x + 100, text_node_pos_y)

        # reformat node
        nuke.createNode("Reformat")

        # MOV node
        mov_node = make_MOV_node()

        # update text nodes messages
        update_text_messages(
            text_nodes[0], text_nodes[1], text_nodes[2], text_nodes[3], text_nodes[4]
        )

        # update settings in mov node
        update_mov_node(mov_node)

        # output Node
        output_node = nuke.createNode("Output")
        output_node.setInput(0, switcheroo)
        output_node.setXYpos(text_node_pos_x, text_node_pos_y + 100)

        # EXR node
        mov_node_pos_x = mov_node.xpos()
        mov_node_pos_y = mov_node.ypos()
        exr_node = make_EXR_node()
        exr_node.setInput(0, input_node)
        exr_node.setXYpos(mov_node_pos_x + 100, mov_node_pos_y)

        makeUI(groupNode)
        createLinks(groupNode, text_nodes, mov_node, exr_node, switcheroo)
        # Create Links

        for n in nuke.allNodes():
            n.hideControlPanel()
        groupNode.end()

        groupNode.setSelected(True)

        if current_node:
            groupNode.setInput(0, current_node)

        groupNode["tile_color"].setValue(0xFF6699FF)  # Example: a blueish color


# main()
