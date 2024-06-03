from enum import IntEnum


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
