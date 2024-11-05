from __future__ import annotations

import hou
import logging
from pathlib import Path
from typing import cast

from pipe.struct.db import Asset, SGEntity

from .filemanager import HFileManager

log = logging.getLogger(__name__)


class HAssetFileManager(HFileManager):
    def __init__(self) -> None:
        super().__init__(Asset)

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        asset = cast(Asset, entity)
        return asset.name, "hipnc"

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HAssetFileManager, HAssetFileManager)._setup_file(self, path, entity)

        hip_path = Path(hou.hscriptStringExpression("$HIP"))
        hou.setContextOption("ASSET", hip_path.name)
