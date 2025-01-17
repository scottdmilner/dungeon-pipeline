from __future__ import annotations

import hou

from typing import TYPE_CHECKING

from pipe.db import DB
from env_sg import DB_Config

if TYPE_CHECKING:
    pass


class AnimPostProcessor:
    _conn: DB

    def __init__(self):
        self._conn = DB(DB_Config)

    def run(self, shot_code: str) -> None:
        # Set up
        shot = self._conn.get_shot_by_code(shot_code)
        hou.playbar.setFrameRange(shot.cut_in - 5, shot.cut_out + 5)
        hou.playbar.setPlaybackRange(shot.cut_in - 5, shot.cut_out + 5)

        stage_ctx: hou.Node = hou.node("/stage")  # type: ignore[assignment]

        load_layer = stage_ctx.createNode("sdm223::main::LnD_Load_Layers::1.0")
        load_layer.parm("shot").set(f"$JOB/{shot.path}")  # type: ignore[union-attr]

        for dep in ["cfx", "fx", "flo", "lighting"]:
            load_layer.parm(f"{dep}_enable").set(0)  # type: ignore[union-attr]

        if env_stub := (shot.set or self._conn.get_sequence_by_stub(shot.sequence).set):  # type: ignore[arg-type]
            layout = self._conn.get_env_by_stub(env_stub)
            load_layer.parm("layout_path").set(f"$JOB/{layout.path}/main.usd")  # type: ignore[union-attr]

        layer_break = stage_ctx.createNode("layerbreak")

        postprocess = stage_ctx.createNode("sdm222::lnd_anim_postprocess::1.0")

        publish = stage_ctx.createNode("usd_rop")

        publish.parm("trange").set("normal")  # type: ignore[union-attr]
        publish.parm("lopoutput").set(f"$JOB/{shot.path}/anim/usd/post-process.usd")  # type: ignore[union-attr]
        publish.parm("savestyle").set("flattenalllayers")  # type: ignore[union-attr]

        layer_break.setInput(0, load_layer)
        postprocess.setInput(0, layer_break)
        publish.setInput(0, postprocess)

        publish.parm("execute").pressButton()  # type: ignore[union-attr]
