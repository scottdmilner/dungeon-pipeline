import studiolibrary
from shared.util import get_anim_path


def run():
    libraries = [
        {
            "name": "LnD Poses",
            "path": str(get_anim_path() / "studiolibrary/lnd-poses"),
            "default": True,
            "theme": {
                "accentColor": "rgb(97, 30, 10)",
            },
        },
    ]
    studiolibrary.setLibraries(libraries)
    studiolibrary.main()
