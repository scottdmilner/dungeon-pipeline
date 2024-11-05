from __future__ import annotations

import hou
import logging
from pathlib import Path
from typing import cast

from pipe.struct.db import Environment, SGEntity

from .filemanager import HFileManager

log = logging.getLogger(__name__)


class HEnvFileManager(HFileManager):
    def __init__(self) -> None:
        super().__init__(Environment)

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        env = cast(Environment, entity)
        return env.name, "hipnc"

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HEnvFileManager, HEnvFileManager)._setup_file(self, path, entity)

        hip_path = Path(hou.hscriptStringExpression("$HIP"))
        hou.setContextOption("ENVIRON", hip_path.name)
