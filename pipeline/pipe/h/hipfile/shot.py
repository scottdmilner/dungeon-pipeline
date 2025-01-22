from __future__ import annotations

import hou
import logging
from enum import Enum
from pathlib import Path
from typing import cast

import pipe.h
from pipe.db import DB
from pipe.glui.dialogs import FilteredListDialog
from pipe.struct.db import SGEntity, Shot

from env_sg import DB_Config

from .filemanager import HFileManager


log = logging.getLogger(__name__)


class HShotFileManager(HFileManager):
    _department: str

    class DEPARTMENT(str, Enum):
        CFX = "cfx"
        FLO = "flo"
        FX = "fx"
        LIGHTING = "lighting"

    def __init__(
        self,
        *,
        override_dept: str | None = None,
        override_entity_code: str | None = None,
    ):
        if override_dept:
            self._department = override_dept
        else:
            department_dialog = FilteredListDialog(
                pipe.h.local.get_main_qt_window(),
                [
                    self.DEPARTMENT.CFX,
                    self.DEPARTMENT.FLO,
                    self.DEPARTMENT.FX,
                    self.DEPARTMENT.LIGHTING,
                ],
                "Department Select",
                include_filter_field=False,
                accept_button_name="Select",
            )
            department_dialog.exec_()

            self._department = department_dialog.get_selected_item() or ""

        if not self._department:
            return

        super().__init__(
            Shot,
            versioning=True,
            version_glob="{}_v*.{}",
            override_entity_code=override_entity_code,
        )

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        return self._department, "hipnc"

    def _get_subpath(self) -> str:
        return self._department

    def _post_open_file(self, entity: SGEntity):
        shot = cast(Shot, entity)

        shot_in = shot.cut_in - 5
        shot_out = shot.cut_out + 5
        if self._department == HShotFileManager.DEPARTMENT.CFX:
            shot_in = 940

        hou.playbar.setFrameRange(shot_in - 5, shot_out + 5)
        hou.playbar.setPlaybackRange(shot_in - 5, shot_out + 5)
        hou.setFrame(shot_in)

        # update substeps
        try:
            hou.node("/stage/PUBLISH").parm("f3").set(1.0 / shot.substeps)  # type: ignore[union-attr]
        except Exception:
            pass

    def _open_file(self, path):
        def do_post_open_file(event: hou.hipFileEventType) -> None:
            if event != hou.hipFileEventType.AfterLoad:
                return
            try:
                shot_code = str(hou.contextOption("SHOT")).split("/").pop()
                conn = DB.Get(DB_Config)
                shot = conn.get_shot_by_code(shot_code)
                self._post_open_file(shot)
            except Exception:
                print("Failed to update frame range!")

            hou.hipFile.removeEventCallback(do_post_open_file)

        # hou.hipFile.load interrupts the running of the script so we have to
        # call _post_open_file with a callback instead
        hou.hipFile.addEventCallback(do_post_open_file)
        super()._open_file(path)

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
        if self._department == HShotFileManager.DEPARTMENT.CFX:
            muted_deps = ["cfx", "fx", "layout", "lighting"]
        elif self._department == HShotFileManager.DEPARTMENT.FLO:
            muted_deps = ["cfx", "flo", "lighting"]
        elif self._department == HShotFileManager.DEPARTMENT.FX:
            muted_deps = ["fx"]
        elif self._department == HShotFileManager.DEPARTMENT.LIGHTING:
            muted_deps = ["lighting"]

        for dep in muted_deps:
            load_layer.parm(f"{dep}_enable").set(0)  # type: ignore[union-attr]

        if env_stub := (shot.set or self._conn.get_sequence_by_stub(shot.sequence).set):  # type: ignore[arg-type]
            layout = self._conn.get_env_by_stub(env_stub)
            load_layer.parm("layout_path").set(f"$JOB/{layout.path}/main.usd")  # type: ignore[union-attr]

        layer_break = stage.createNode("layerbreak")

        begin_dep = stage.createNode("null")
        begin_dep.setName(f"BEGIN_{self._department.upper()}")

        end_dep = stage.createNode("null")
        end_dep.setName(f"END_{self._department.upper()}")

        publish = stage.createNode("usd_rop")
        publish.setName("PUBLISH")
        publish.parm("lopoutput").set("$HIP/usd/main.usd")  # type: ignore[union-attr]
        publish.parm("trange").set("normal")  # type: ignore[union-attr]

        layer_break.setInput(0, load_layer)
        begin_dep.setInput(0, layer_break)
        end_dep.setInput(0, begin_dep)
        publish.setInput(0, end_dep)

        end_dep.setPosition((0, 1))
        begin_dep.setPosition((0, 4))
        layer_break.setPosition((0, 5))
        load_layer.setPosition((0, 6))

        if self._department == HShotFileManager.DEPARTMENT.CFX:
            publish.parm("f1").set(shot.cut_in - 5)  # type: ignore[union-attr]
            sublayer = stage.createNode("sublayer")
            sublayer.setPosition((0, 2))
            sublayer.setInput(0, begin_dep)
            end_dep.setInput(0, sublayer)

            for idx, stub in enumerate(shot.assets):
                asset = self._conn.get_asset_by_stub(stub)
                if asset.name == "rayden":
                    char_cfx = stage.createNode("cooks23::RAYDEN_CFXSHOT::1.0")
                elif asset.name == "robin":
                    char_cfx = stage.createNode("cooks23::dev::ROBIN_CFXSHOT::1.0")
                else:
                    continue
                char_cfx.setPosition((idx + 1, 3))
                char_cfx.setInput(0, begin_dep)
                sublayer.setNextInput(char_cfx)

        self._post_open_file(shot)

        hou.hipFile.save()
