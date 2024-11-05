from __future__ import annotations

import hou
import logging
from enum import Enum
from pathlib import Path
from typing import cast

import pipe.h
from pipe.glui.dialogs import FilteredListDialog
from pipe.struct.db import SGEntity, Shot

from .filemanager import HFileManager


log = logging.getLogger(__name__)


class HShotFileManager(HFileManager):
    _department: DEPARTMENT

    class DEPARTMENT(str, Enum):
        CFX = "cfx"
        FX = "fx"
        LIGHTING = "lighting"

    def __init__(self):
        department_dialog = FilteredListDialog(
            pipe.h.local.get_main_qt_window(),
            [self.DEPARTMENT.CFX, self.DEPARTMENT.FX, self.DEPARTMENT.LIGHTING],
            "Department Select",
            include_filter_field=False,
            accept_button_name="Select",
        )
        department_dialog.exec_()

        self._department = department_dialog.get_selected_item()
        if not self._department:
            return
        super().__init__(Shot, versioning=True, version_glob="{}_v*.{}")

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        return self._department, "hipnc"

    def _get_subpath(self) -> str:
        return self._department

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HShotFileManager, HShotFileManager)._setup_file(self, path, entity)
        shot = cast(Shot, entity)

        if shot.path:
            hou.setContextOption("SHOT", shot.path)

        stage: hou.Node = hou.node("/stage")  # type: ignore[assignment]

        load_layer = stage.createNode("sdm223::main::LnD_Load_Layers::1.0")
        load_layer.setUserData("nodeshape", "bulge_down")
        load_layer.parm("shot").set("$JOB/`@SHOT`")  # type: ignore[union-attr]

        muted_deps: list[str] = []
        if self._department == self.DEPARTMENT.CFX:
            muted_deps = ["cfx", "fx", "layout", "lighting"]
        elif self._department == self.DEPARTMENT.FX:
            muted_deps = ["fx"]
        elif self._department == self.DEPARTMENT.LIGHTING:
            muted_deps = ["lighting"]

        for dep in muted_deps:
            load_layer.parm(f"{dep}_enable").set(0)  # type: ignore[union-attr]

        if shot.set:
            layout = self._conn.get_env_by_stub(shot.set)
            load_layer.parm("layout_path").set(f"$JOB/{layout.path}/main.usd")  # type: ignore[union-attr]

        layer_break = stage.createNode("layerbreak")

        begin_dep = stage.createNode("null")
        begin_dep.setName(f"BEGIN_{self._department.upper()}")

        end_dep = stage.createNode("null")
        end_dep.setName(f"END_{self._department.upper()}")

        publish = stage.createNode("usd_rop")
        publish.setName("PUBLISH")
        publish.parm("lopoutput").set("$HIP/usd/main.usd")  # type: ignore[union-attr]

        layer_break.setInput(0, load_layer)
        begin_dep.setInput(0, layer_break)
        end_dep.setInput(0, begin_dep)
        publish.setInput(0, end_dep)

        end_dep.setPosition((0, 1))
        begin_dep.setPosition((0, 4))
        layer_break.setPosition((0, 5))
        load_layer.setPosition((0, 6))

        hou.hipFile.save()
