from __future__ import annotations

import logging

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pipe.struct.db import Shot

if TYPE_CHECKING:
    from pathlib import Path
    from pipe.util import Playblaster
    from typing import Callable, Literal

log = logging.getLogger(__name__)


def dummy_shot(code: str, cut_in: int, cut_out: int, cut_duration: int) -> Shot:
    """Generate a generic `Shot` object to hold cut info that doesn't
    correspond to a ShotGrid shot"""
    return Shot(
        code=code,
        id=0,
        assets=[],
        cut_in=cut_in,
        cut_out=cut_out,
        cut_duration=cut_duration,
        sequence=None,
        set=None,
    )


@dataclass
class HudDefinition:
    """
    Definition for a viewport HUD.
    Attributes
        name: str
            Internal name used by Maya for the HUD
        command: Callable[[], str]
            Command for the HUD to call
        section: int
            HUD section to occupy (see Maya docs)
        label: str
            String that precedes the return value of `command`
        event: str
            Event string that triggers a refresh (see Maya docs)
        idle_refresh: bool
            Alternative to `event`, will refresh every frame
        blockSize: Literal["small", "large"]
            Amount of HUD space to occupy
        labelFontSize: Literal["small", "large"]
    """

    name: str
    command: Callable[[], str]
    section: int
    label: str = ""
    event: str = ""
    idle_refresh: bool = False
    blockSize: Literal["small", "large"] = "small"
    labelFontSize: Literal["small", "large"] = "small"


@dataclass
class MShotPlayblastConfig:
    """Information needed to playblast a shot.
    Attributes:
        camera: str | None
            Camera to use. Set to `None` if `use_sequencer` is set
        shot: Shot
            Shot struct to hold shot code, cut in, cut out, and duration
        save_locs: list[tuple[SaveLocation, bool]]
            List of SaveLocations, paired with their default enable value
        enabled: bool = True
            Whether to playblast this shot
        paths: dict[Playblaster.PRESET, list[str | Path]]
            Paths to output to
        tails: tuple[int, int]
            How many frames early/late to start playblasting
        use_sequencer: bool = False
            Whether to playblast from the sequencer. If set to True, `camera`
            will be ignored
    """

    camera: str | None
    shot: Shot
    save_locs: list[tuple[SaveLocation, bool]]
    enabled: bool = True
    paths: dict[Playblaster.PRESET, list[str | Path]] = field(default_factory=dict)
    tails: tuple[int, int] = (0, 0)
    use_sequencer: bool = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_paths(self, paths: dict[Playblaster.PRESET, list[str | Path]]) -> None:
        self.paths = paths


@dataclass
class MPlayblastConfig:
    """Information needed to configure a Maya playblast
    Attributes:
        builtin_huds: list[str]
            List of valid Maya builtin HUD names
        custom_huds: list[HudDefinition]
            List of `HudDefinition`s
        lighting: bool
            Toggle viewport lighting
        shadows: bool
            Toggle viewport shadows
        shots: list[MShotPlayblastConfig]
            List of shots to playblast
    """

    builtin_huds: list[str]
    custom_huds: list[HudDefinition]
    lighting: bool
    shadows: bool
    shots: list[MShotPlayblastConfig]


class SaveLocation:
    """Information needed for a save location. If a lambda is provided to
    `path` it will call that and return the value"""

    name: str
    preset: Playblaster.PRESET
    _path: str | Path | Callable[[], str | Path]

    def __init__(
        self,
        name: str,
        path: str | Path | Callable[[], str | Path],
        preset: Playblaster.PRESET,
    ):
        self.name = name
        self._path = path
        self.preset = preset

    @property
    def path(self) -> str | Path:
        if callable(self._path):
            return self._path()
        else:
            return self._path
