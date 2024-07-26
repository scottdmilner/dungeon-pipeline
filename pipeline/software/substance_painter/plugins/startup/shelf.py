from __future__ import annotations

import substance_painter as sp

from shared.util import get_production_path

_SHELF_NAME = "lnd-resources"


def start_plugin():
    # create the LnD shelf
    sp.resource.Shelves().add(
        _SHELF_NAME, str(get_production_path() / "painter_assets")
    )


def close_plugin():
    sp.resource.Shelves().remove(_SHELF_NAME)


if __name__ == "__main__":
    window = start_plugin()
