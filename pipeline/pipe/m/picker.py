import dwpicker

from shared.util import get_rigging_path

picker_filenames = [
    "Ray_Facial_Picker.json",
    "Rayden_Picker.json",
    "Robin_Picker.json",
]


def run():
    picker_folder_path = get_rigging_path() / "Pickers"

    picker_filepaths = [str(picker_folder_path / pfn) for pfn in picker_filenames]
    print("Picker filepaths", picker_filepaths)

    dwpicker.show(pickers=picker_filepaths)
