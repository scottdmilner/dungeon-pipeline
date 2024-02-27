import substance_painter as sp

import json
import logging
import os
import re
import subprocess
from math import ceil, floor, sqrt
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Type, TypeVar

import pipe
from pipe.db import DB
from pipe.struct import Asset, MaterialType
from pipe.glui.dialogs import MessageDialog
from pipe.util import get_production_path, resolve_mapped_path, silent_startupinfo
from env import Executables, SG_Config

RT = TypeVar("RT")  # return type

lib_path = resolve_mapped_path(Path(__file__).parents[1] / "lib")
log = logging.getLogger(__name__)


class Exporter:
    """Class to manage exporting and converting textures"""

    conn: DB
    asset: Asset
    out_path: Path
    src_path: Path
    tex_path: Path
    preview_path: Path
    export_result: sp.export.TextureExportResult

    def __init__(self) -> None:
        self.conn = DB(SG_Config)
        id = sp.project.Metadata("LnD").get("asset_id")
        self.asset = self.conn.get_asset_by_id(id)

        # initialize paths, pulling from SG database
        self.out_path = resolve_mapped_path(get_production_path() / self.asset.tex_path)
        self.src_path = self.out_path / "src"
        self.tex_path = self.out_path / "tex"
        self.preview_path = self.out_path / "preview"

        # create paths if not exist
        self.src_path.mkdir(parents=True, exist_ok=True)
        self.tex_path.mkdir(parents=True, exist_ok=True)
        self.preview_path.mkdir(parents=True, exist_ok=True)

    def _debug_out(self, func: Callable[..., RT]) -> Callable[..., RT]:
        """Decorator to debug print the output of the function"""

        def inner(self: Type[Exporter], *args, **kwargs) -> RT:
            ret = func(self, *args, **kwargs)
            log.debug(ret)
            return ret

        return inner

    def export(self, tex_sets: Dict[sp.textureset.TextureSet, MaterialType]) -> bool:
        """Export all the textures of the given Texture Sets"""
        # TODO: multiple material types
        self.src_path.mkdir(parents=True, exist_ok=True)
        try:
            [ts.get_stack() for ts in tex_sets.keys()]
        except:
            MessageDialog(
                pipe.local.get_main_qt_window(),
                "Warning! Exporter could not get stack! You are doing something cool with material layering. Please show this to Scott so he can fix it.",
            ).exec_()
            return

        config = general_config(
            self.src_path, (ts.get_stack() for ts in tex_sets.keys())
        )

        try:
            self.export_result = sp.export.export_project_textures(config)
        except Exception as e:
            print(e)
            return False

        self.write_mat_info(tex_sets)
        tex_success = self.convert_tex()
        pvw_success = self.convert_previewsurface()

        return tex_success and pvw_success

    def write_mat_info(
        self, tex_sets: Dict[sp.textureset.TextureSet, MaterialType]
    ) -> bool:
        """Write out JSON file with information about the texturesets"""
        info = [
            {
                "name": ts.name(),
                "has_udims": ts.has_uv_tiles(),
                "material_type": mt,
            }
            for ts, mt in tex_sets.items()
        ]
        with open(str(self.out_path / "mat.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=4)

    def convert_tex(self) -> bool:
        """Convert all .png textures in the most recent export to .tex"""

        if not self.export_result:
            raise AssertionError(
                "The export() function has not been called yet, there are no textures to convert"
            )

        @self._debug_out
        def tex_cmd(img: Path) -> list[str]:
            # currently using oiiotool so txmake doesn't freak out at the color space
            # TODO: switch back to txmake for color in R26
            # fmt: off
            return [
                str(Executables.oiiotool),
                str(img),
                "--compression", "lossless",
                "--planarconfig", "separate",
                "-otex:fileformatname=tx:wrap=clamp:resize=1:prman_options=1",
                f"{str(self.tex_path / img.stem)}.tex",
            ]
            # fmt: on

        @self._debug_out
        def b2r_cmd(img: Path) -> list[str]:
            # fmt: off
            return [
                str(Executables.txmake),
                "-resize", "round-",
                "-mode", "periodic",
                "-filter", "box",
                "-mipfilter", "box",
                "-bumprough", "2", "0", "1", "0", "0", "1",
                "-newer",
                str(img),
                f"{str(self.tex_path / img.stem)}.b2r",
            ]
            # fmt: on

        # procs = [
        #     subprocess.Popen(
        #         (b2r_cmd if "Normal" in img.name else tex_cmd)(img),
        #         env=os.environ,
        #         startupinfo=silent_startupinfo(),
        #         stderr=subprocess.PIPE,
        #         stdout=subprocess.PIPE,
        #     )
        #     for imgs in self.export_result.textures.values()
        #     for img in (Path(i) for i in imgs)
        #     if img.suffix == ".png"
        # ]

        procs = []
        for imgs in self.export_result.textures.values():
            log.debug(imgs)
            for img in (Path(i) for i in imgs):
                if img.suffix == ".png":
                    log.debug(f"        {str(img)}")
                    procs.append(
                        subprocess.Popen(
                            (b2r_cmd if "Normal" in img.name else tex_cmd)(img),
                            env=os.environ,
                            startupinfo=silent_startupinfo(),
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                        )
                    )

        for p in procs:
            p.wait()

            if log.isEnabledFor(logging.DEBUG):
                if stdout := p.stdout.read().decode("utf-8"):
                    log.debug(stdout)
                if stderr := p.stderr.read().decode("utf-8"):
                    log.debug(stderr)

        return True

    def convert_previewsurface(self) -> bool:
        """Compile all .jpeg textures in the most recent export to UDIM-less tiles"""

        if not self.export_result:
            raise AssertionError(
                "The export() function has not been called yet, there are no textures to convert"
            )

        @self._debug_out
        def jpeg_cmd(root: Path, imgs: List[str]) -> list[str]:
            img_info = subprocess.check_output(
                [
                    str(Executables.oiiotool),
                    "--info",
                    imgs[0],
                ],
                startupinfo=silent_startupinfo(),
            ).decode("utf-8")
            img_dims = re.search(r"^.* : (\d+) x (\d+), .*$", img_info)
            dimx, dimy = img_dims.group(1, 2)

            img_name = re.search(r"^(.*_)(.+)$", root.name)
            name_base, color_space = img_name.group(1, 2)

            count = len(imgs)
            grid_height = int(floor(sqrt(count)))
            grid_base = int(grid_height + ceil(count / grid_height - grid_height))

            # fmt: off
            return [
                str(Executables.oiiotool), 
                *imgs,
                "--mosaic", f"{grid_base}x{grid_height}",
                "--resize", f"{dimx}x{dimy}",
                *(["--colorconvert", "ACEScg", "srgb_tx"] if color_space == "ACEScg" else []),
                "-o", f"{str(self.preview_path / name_base)}{'sRGB' if color_space == 'ACEScg' else 'Linear'}.jpeg",
            ]
            # fmt: on

        # construct list of grouped images
        img_list: Dict[str, List[str]] = {}
        for imgs in self.export_result.textures.values():
            for img in imgs:
                if img.endswith(".jpeg"):
                    key = re.search(r"^(.*)\.\d{4}\.jpeg$", img).group(1)
                    if not key in img_list:
                        img_list[key] = []
                    img_list[key].append(img)

        procs = [
            subprocess.Popen(
                jpeg_cmd(Path(root), imgs),
                env=os.environ,
                startupinfo=silent_startupinfo(),
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            for root, imgs in img_list.items()
        ]

        for p in procs:
            p.wait()

            if log.isEnabledFor(logging.DEBUG):
                if stdout := p.stdout.read().decode("utf-8"):
                    log.debug(stdout)
                if stderr := p.stderr.read().decode("utf-8"):
                    log.debug(stderr)

        return True


def general_config(asset_path: Path, stacks: Iterable[sp.textureset.Stack]) -> dict:
    return {
        "exportPath": str(asset_path),
        "exportShaderParams": True,
        "defaultExportPreset": "LnD-General",
        "exportPresets": [
            {
                "name": "LnD-General",
                "maps": [
                    # RenderMan
                    {
                        "fileName": "$textureSet_BaseColor(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "documentMap",
                                "srcMapName": "baseColor",
                            }
                            for ch in "RGB"
                        ],
                        "parameters": {
                            "bitDepth": "16",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_Metallic(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": "L",
                                "srcChannel": "L",
                                "srcMapType": "documentMap",
                                "srcMapName": "metallic",
                            },
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_Specular(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": "L",
                                "srcChannel": "L",
                                "srcMapType": "documentMap",
                                "srcMapName": "specular",
                            },
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_Normal(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "virtualMap",
                                "srcMapName": "Normal_OpenGL",
                            }
                            for ch in "RGB"
                        ],
                        "parameters": {
                            "bitDepth": "16",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_SpecularRoughness(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": "L",
                                "srcChannel": "L",
                                "srcMapType": "documentMap",
                                "srcMapName": "roughness",
                            },
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_GlowColor(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "documentMap",
                                "srcMapName": "emissive",
                            }
                            for ch in "RGB"
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_Presence(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": "L",
                                "srcChannel": "L",
                                "srcMapType": "documentMap",
                                "srcMapName": "opacity",
                            },
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_Displacement(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": "L",
                                "srcChannel": "L",
                                "srcMapType": "documentMap",
                                "srcMapName": "height",
                            },
                        ],
                        "parameters": {
                            "bitDepth": "16",
                            "fileFormat": "png",
                        },
                    },
                    # USD Preview Surface
                    {
                        "fileName": "$textureSet_DiffuseColor(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "virtualMap",
                                "srcMapName": "Diffuse",
                            }
                            for ch in "RGB"
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "jpeg",
                        },
                    },
                    {
                        "fileName": "$textureSet_ORM(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": "R",
                                "srcChannel": "R",
                                "srcMapType": "documentMap",
                                "srcMapName": "opacity",
                            },
                            {
                                "destChannel": "G",
                                "srcChannel": "G",
                                "srcMapType": "documentMap",
                                "srcMapName": "roughness",
                            },
                            {
                                "destChannel": "B",
                                "srcChannel": "B",
                                "srcMapType": "documentMap",
                                "srcMapName": "metallic",
                            },
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "jpeg",
                        },
                    },
                    {
                        "fileName": "$textureSet_Emissive(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "documentMap",
                                "srcMapName": "emissive",
                            }
                            for ch in "RGB"
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "jpeg",
                        },
                    },
                    {
                        "fileName": "$textureSet_NormalDX(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "virtualMap",
                                "srcMapName": "Normal_DirectX",
                            }
                            for ch in "RGB"
                        ],
                        "parameters": {
                            "bitDepth": "8",
                            "fileFormat": "jpeg",
                        },
                    },
                ],
            },
        ],
        "exportList": [{"rootPath": str(stack)} for stack in stacks],
        "exportParameters": [
            {
                "parameters": {
                    "dithering": False,
                    "paddingAlgorithm": "infinite",
                },
            },
        ],
    }
