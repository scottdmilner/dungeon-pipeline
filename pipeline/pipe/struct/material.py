from __future__ import annotations

import attrs

from enum import IntEnum

from pipe.struct.util import JsonSerializable


class DisplacementSource(IntEnum):
    NONE = 0
    HEIGHT = 1
    DISPLACEMENT = 2


class NormalSource(IntEnum):
    NORMAL_HEIGHT = 0
    NORMAL_ONLY = 1


class NormalType(IntEnum):
    STANDARD = 0
    BUMP_ROUGHNESS = 1


@attrs.define
class TexSetInfo(JsonSerializable):
    displacement_source: DisplacementSource = DisplacementSource.NONE
    has_udims: bool = True
    normal_source: NormalSource = NormalSource.NORMAL_HEIGHT
    normal_type: NormalType = NormalType.STANDARD


@attrs.define
class MaterialInfo(JsonSerializable):
    tex_sets: dict[str, TexSetInfo] = dict()
