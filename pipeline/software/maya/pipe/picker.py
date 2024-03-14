import os
import pipe.util
import dwpicker


path_to_picker = ["character", "Rigging", "Pickers"]

picker_filenames_windows = [
    "Robin_Picker.json"
    # "Ray_Picker.json"
]

picker_filenames_linux = [
    "Robin_Picker_linux.json"
    # "Ray_Picker_linux.json"
]


def run():
    picker_folder_path = pipe.util.get_character_path() / "Rigging/Pickers"

    picker_filepaths = [
        str(picker_folder_path / picker_filename)
        for picker_filename in (
            picker_filenames_windows if os.name == "nt" else picker_filenames_linux
        )
    ]
    print("Picker filepaths", picker_filepaths)

    dwpicker.show(pickers=picker_filepaths)
