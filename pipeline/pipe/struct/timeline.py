from __future__ import annotations

import attrs

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .db import Shot

from .util import JsonSerializable


PREROLL_DURATION = 55


@attrs.define(frozen=True)
class Timeline(JsonSerializable):
    start: int
    end: int
    head_duration: int = attrs.field(default=5)
    tail_duration: int = attrs.field(default=5)
    preroll_duration: int = attrs.field(default=PREROLL_DURATION)
    head: int = attrs.field(
        init=False,
        default=attrs.Factory(lambda s: s.start - s.head_duration, takes_self=True),
    )
    tail: int = attrs.field(
        init=False,
        default=attrs.Factory(lambda s: s.end + s.tail_duration, takes_self=True),
    )
    preroll: int = attrs.field(
        init=False,
        default=attrs.Factory(lambda s: s.head - s.preroll_duration, takes_self=True),
    )

    @classmethod
    def from_shot(
        cls: type[Timeline], shot: Shot, preroll_duration: int = PREROLL_DURATION
    ) -> Timeline:
        return cls(
            start=shot.cut_in,
            end=shot.cut_out,
            preroll_duration=preroll_duration,
            head_duration=5,
            tail_duration=5,
        )
