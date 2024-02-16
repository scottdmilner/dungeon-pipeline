import substance_painter as sp

import subprocess
from enum import Enum
from pathlib import Path

import pipe
from pipe.db import DB
from pipe.struct import Asset
from pipe.glui.dialogs import MessageDialog
from pipe.util import get_production_path, resolve_mapped_path, silent_startupinfo
from env import SG_Config

lib_path = resolve_mapped_path(Path(__file__).parents[1] / "lib")


class MaterialType(Enum):
    GENERAL = 0
    METAL = 1
    GLASS = 2
    CLOTH = 3
    SKIN = 4


class Exporter:
    conn: DB
    asset: Asset
    out_path: Path
    src_path: Path

    def __init__(self) -> None:
        self.conn = DB(SG_Config)
        id = sp.project.Metadata("LnD").get("asset_id")
        self.asset = self.conn.get_asset_by_id(id)
        self.out_path = resolve_mapped_path(get_production_path() / self.asset.tex_path)
        self.src_path = self.out_path / "src"

    def export(
        self, tex_set: sp.textureset.TextureSet, material_type: MaterialType
    ) -> bool:
        self.src_path.mkdir(parents=True, exist_ok=True)
        try:
            stack = tex_set.get_stack()
        except:
            MessageDialog(
                pipe.local.get_main_qt_window(),
                "Warning! Exporter could not get stack! You are doing something cool with material layering. Please show this to Scott so he can fix it.",
            ).exec_()
            return

        config = general_config(self.src_path, stack)

        try:
            sp.export.export_project_textures(config)
        except Exception as e:
            print(e)
            return False

        return self.convert_tex(
            self.src_path, self.out_path / "tex"
        ) and self.convert_previewsurface(self.src_path, self.out_path / "preview")

    def convert_tex(self, src: Path, out: Path) -> bool:
        hoiiotool = "C:\\Program Files\\Side Effects Software\\Houdini 19.5.640\\bin\\hoiiotool.exe"
        txmake = "C:\\Program Files\\Pixar\\RenderManProServer-25.2\\bin\\txmake.exe"

        def tex_cmd(img: Path, out_dir: Path) -> list[str]:
            # currently using hoiiotool so txmake doesn't freak out at the color space
            # TODO: switch back to txmake for color in R26
            # fmt: off
            return [
                hoiiotool,
                str(img),
                "--compression", "lossless",
                "--planarconfig", "separate",
                "-otex:fileformatname=tx:wrap=clamp:resize=1:prman_options=1",
                str(out_dir / img.stem) + ".tex"
            ]
            # fmt: on

        def b2r_cmd(img: Path, out_dir: Path) -> list[str]:
            # fmt: off
            return [
                txmake,
                "-resize", "round-",
                "-mode", "periodic",
                "-filter", "box",
                "-mipfilter", "box",
                "-bumprough", "2", "0", "1", "0", "0", "1",
                "-newer",
                str(img),
                str(out_dir / img.stem) + ".b2r"
            ]
            # fmt: on

        out.mkdir(parents=True, exist_ok=True)

        procs = [
            subprocess.Popen(
                (b2r_cmd if "Normal" in img.name else tex_cmd)(img, out),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=silent_startupinfo(),
            )
            for img in src.iterdir()
            if img.suffix == ".png"
        ]

        for p in procs:
            p.wait()

        return True

    def convert_previewsurface(self, src: Path, out: Path) -> bool:
        return True


def general_config(asset_path: Path, stack: sp.textureset.Stack) -> dict:
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
                            "bitDepth": "16",
                            "fileFormat": "png",
                        },
                    },
                    {
                        "fileName": "$textureSet_SpecularFaceColor(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "virtualMap",
                                "srcMapName": "Specular",
                            }
                            for ch in "RGB"
                        ],
                        "parameters": {
                            "bitDepth": "16",
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
                        "fileName": "$textureSet_BaseColor(_$colorSpace)(.$udim)",
                        "channels": [
                            {
                                "destChannel": ch,
                                "srcChannel": ch,
                                "srcMapType": "documentMap",
                                "srcMapName": "basecolor",
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
                        "fileName": "$textureSet_NormalUE(_$colorSpace)(.$udim)",
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
        "exportList": [{"rootPath": str(stack)}],
        "exportParameters": [
            {
                "parameters": {
                    "dithering": False,
                    "paddingAlgorithm": "infinite",
                },
            },
        ],
    }
