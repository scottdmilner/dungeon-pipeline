import dwpicker

from shared.util import get_rigging_path


def run():
    picker_folder_path = get_rigging_path() / "Pickers"

    picker_filepaths = [
        str(p) for p in picker_folder_path.iterdir() if p.suffix == ".json"
    ]
    print("Picker filepaths", picker_filepaths)

    dwpicker.show(pickers=picker_filepaths)
