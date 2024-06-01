import substance_painter as sp

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Set, TypeVar

from pipe.sp.local import get_main_qt_window
from pipe.db import DB
from pipe.struct.asset import Asset
from pipe.struct.material import DisplacementSource, NormalSource, NormalType
from pipe.glui.dialogs import MessageDialog
from pipe.texconverter import TexConverter, TexConversionError
from pipe.util import get_production_path, resolve_mapped_path
from env import SG_Config

RT = TypeVar("RT")  # return type

lib_path = resolve_mapped_path(Path(__file__).parents[1] / "lib")
log = logging.getLogger(__name__)


@dataclass
class TexSetExportSettings:
    tex_set: sp.textureset.TextureSet
    extra_channels: Set[sp.textureset.Channel]
    resolution: int
    displacement_source: DisplacementSource
    normal_type: NormalType
    normal_source: NormalSource


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
        assert (a := self.conn.get_asset_by_id(id)) is not None
        self.asset = a

        # initialize paths, pulling from SG database
        assert self.asset.tex_path is not None
        self.out_path = resolve_mapped_path(get_production_path() / self.asset.tex_path)
        self.src_path = self.out_path / "src"
        self.tex_path = self.out_path / "tex"
        self.preview_path = self.out_path / "preview"

        # create paths if not exist
        self.src_path.mkdir(parents=True, exist_ok=True)
        self.tex_path.mkdir(parents=True, exist_ok=True)
        self.preview_path.mkdir(parents=True, exist_ok=True)

    def export(self, exp_setting_arr: List[TexSetExportSettings]) -> bool:
        """Export all the textures of the given Texture Sets"""
        # TODO: multiple material types
        self.src_path.mkdir(parents=True, exist_ok=True)
        try:
            [tss.tex_set.get_stack() for tss in exp_setting_arr]
        except ValueError:
            MessageDialog(
                get_main_qt_window(),
                "Warning! Exporter could not get stack! You are doing something cool with material layering. Please show this to Scott so he can fix it.",
            ).exec_()
            return False

        config = generate_config(self.src_path, exp_setting_arr)
        log.debug(config)

        try:
            self.export_result = sp.export.export_project_textures(config)
        except Exception as e:
            print(e)
            return False

        self.write_mat_info(exp_setting_arr)

        tex_converter = TexConverter(
            self.tex_path, self.preview_path, self.export_result.textures.values()
        )

        try:
            tex_converter.convert_tex()
            tex_converter.convert_previewsurface()
        except TexConversionError:
            MessageDialog(
                get_main_qt_window(),
                (
                    "Warning! Not all textures were converted! Make sure to "
                    'stop rendering this asset in Houdini and press "Reset '
                    'RenderMan RIS/XPU".'
                ),
            ).exec_()
            return False

        return True

    def write_mat_info(
        self, export_settings_arr: Iterable[TexSetExportSettings]
    ) -> bool:
        """Write out JSON file with information about the texturesets"""
        info = [
            {
                "name": export_settings.tex_set.name(),
                "has_udims": export_settings.tex_set.has_uv_tiles(),
                "normal_type": export_settings.normal_type,
                "displacement": export_settings.displacement_source
                is not DisplacementSource.NONE,
            }
            for export_settings in export_settings_arr
        ]
        with open(str(self.out_path / "mat.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=4)
            return True


def generate_config(
    asset_path: Path, export_settings_arr: Iterable[TexSetExportSettings]
) -> dict:
    return {
        "exportPath": str(asset_path),
        "exportShaderParams": True,
        "exportPresets": [
            {
                "name": export_settings.tex_set.name(),
                "maps": [
                    # Default RenderMan maps
                    *shader_maps(
                        export_settings.resolution,
                        export_settings.normal_source,
                        export_settings.normal_type,
                        export_settings.displacement_source,
                    ),
                    # Extra AOVs
                    *[
                        {
                            "fileName": f"$textureSet_{getattr(ch, 'label', None) and ch.label().replace(' ', '') or ch.type().name}(_$colorSpace)(.$udim)",
                            "channels": [
                                {
                                    "destChannel": color,
                                    "srcChannel": color,
                                    "srcMapType": "documentMap",
                                    "srcMapName": ch.type().name.lower(),
                                }
                                for color in colors
                            ],
                            "parameters": {
                                "bitDepth": bit_depth.lower(),
                                "fileFormat": "png",
                                "sizeLog2": export_settings.resolution,
                            },
                        }
                        for ch in export_settings.extra_channels
                        for colors, bit_depth in re.findall(
                            r"^s?(L|RGB)(\d{1,2}F?)$",
                            export_settings.tex_set.get_stack()
                            .get_channel(ch.type())
                            .format()
                            .name,
                        )
                    ],
                    # Preview Surface
                    *preview_surface_maps,
                ],
            }
            for export_settings in export_settings_arr
        ],
        "exportList": [
            {
                "rootPath": str(export_settings.tex_set.get_stack()),
                "exportPreset": export_settings.tex_set.name(),
            }
            for export_settings in export_settings_arr
        ],
        "exportParameters": [
            {
                "parameters": {
                    "dithering": False,
                    "paddingAlgorithm": "color",
                    "dilationDistance": 24,
                }
            }
        ],
    }


normal_source_to_sbs_parm = {
    NormalSource.NORMAL_HEIGHT: {"srcMapType": "documentMap", "srcMapName": "height"}
}


def shader_maps(
    resolution: int,
    normal_source: NormalSource,
    normal_type: NormalType,
    displacement_source: DisplacementSource,
) -> List:
    maps = [
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
                "bitDepth": "8",
                "fileFormat": "png",
                "sizeLog2": resolution,
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
                "sizeLog2": resolution,
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
                "sizeLog2": resolution,
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
                "sizeLog2": resolution,
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
                "sizeLog2": resolution,
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
                "sizeLog2": resolution,
            },
        },
        {
            "fileName": f"$textureSet_Normal(_$colorSpace)(.$udim){'.pre-b2r' if normal_type == NormalType.BUMP_ROUGHNESS else ''}",
            "channels": [
                {
                    "destChannel": ch,
                    "srcChannel": ch,
                    **(
                        {
                            "srcMapType": "virtualMap",
                            "srcMapName": "Normal_OpenGL",
                        }
                        if normal_source is NormalSource.NORMAL_HEIGHT
                        else {
                            "srcMapType": "documentMap",
                            "srcMapName": "normal",
                        }
                    ),
                }
                for ch in "RGB"
            ],
            "parameters": {
                **(
                    {
                        "bitDepth": "16f",
                        "fileFormat": "exr",
                    }
                    if normal_type is NormalType.BUMP_ROUGHNESS
                    else {
                        "bitDepth": "16",
                        "fileFormat": "png",
                    }
                ),
                "sizeLog2": resolution,
            },
        },
    ]

    if displacement_source is not DisplacementSource.NONE:
        maps += [
            {
                "fileName": "$textureSet_Displacement(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": "L",
                        "srcChannel": "L",
                        "srcMapType": "documentMap",
                        "srcMapName": (
                            "height"
                            if displacement_source == DisplacementSource.HEIGHT
                            else "displacement"
                        ),
                    },
                ],
                "parameters": {
                    "bitDepth": "16",
                    "fileFormat": "png",
                    "sizeLog2": resolution,
                },
            }
        ]

    return maps


preview_surface_maps = [
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
]
