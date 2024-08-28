from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

import maya.cmds as mc

from pipe.m.publish import Publisher
from pipe.m.usdchaser import ChaserMode, ExportChaser

log = logging.getLogger(__name__)


class RiggedExporter(Publisher):
    EXPORT_SETS: dict[str, str] = {
        "rayden": "Rayden:cache_SET",
        "robin": "Robin:cache_SET",
    }

    _char: str
    _anim: bool

    def __init__(self, char: str, anim: bool = False) -> None:
        self._char = char
        self._anim = anim
        super().__init__()

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        kwargs = {
            "chaser": [ExportChaser.ID],
            "chaserArgs": [(ExportChaser.ID, "mode", ChaserMode.RIG)],
            "exportCollectionBasedBindings": True,
            "exportMaterialCollections": True,
            "materialCollectionsPath": "/CHAR/MODEL",
            "shadingMode": "useRegistry",
        }

        if self._anim:
            kwargs.update(
                {
                    "exportColorSets": False,
                    "exportComponentTags": False,
                    "exportUVs": False,
                    "frameRange": [1, 20],
                    "frameStride": 1.0,
                    "shadingMode": "none",
                }
            )

        return kwargs

    def _presave(self) -> bool:
        mc.select(self.EXPORT_SETS[self._char])
        return True
