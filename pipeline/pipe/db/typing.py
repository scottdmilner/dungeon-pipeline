from __future__ import annotations

from typing import Any, Iterable, Literal, Optional, Protocol, TypedDict, Union
from typing_extensions import NotRequired, Unpack

from pipe.struct.db import (
    Asset,
    AssetStub,
    Environment,
    EnvironmentStub,
    Sequence,
    SequenceStub,
    SGEntity,
    Shot,
    ShotStub,
)

from .interface import DBInterface

TimeUnit = Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
BasicFilter = Union[
    tuple[
        str,
        Literal[
            "is", "is_not", "less_than", "greater_than", "contains", "not_contains"
        ],
        Any,
    ],
    tuple[str, Literal["starts_with", "ends_with"], str],
    tuple[str, Literal["between", "not_between"], Any, Any],
    tuple[str, Literal["in_last", "in_next"], int, TimeUnit],
    tuple[str, Literal["in"], list[Any]],
    tuple[str, Literal["type_is", "type_is_not"], Optional[str]],
    tuple[
        str, Literal["in_calendar_day", "in_calendar_week", "in_calendar_month"], int
    ],
    tuple[
        str,
        Literal[
            "name_contains", "name_not_contains", "name_starts_with", "name_ends_with"
        ],
        str,
    ],
]


class ComplexFilter(TypedDict):
    filter_operator: Literal["any", "all"]
    filters: list[BasicFilter]


Filter = Union[BasicFilter, ComplexFilter]


class AttrMappingKwargs(TypedDict):
    child_mode: NotRequired[DBInterface.ChildQueryMode]


class T_GetAssetAttrList(Protocol):
    def __call__(
        self,
        attr: str,
        *,
        sorted: bool = False,
        child_mode: DBInterface.ChildQueryMode = DBInterface.ChildQueryMode.LEAVES,
    ) -> list[str]: ...


class T_GetAssetByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Asset: ...


class T_GetAssetById(Protocol):
    def __call__(self, id: int) -> Asset: ...


class T_GetAssetByName(Protocol):
    def __call__(self, name: str) -> Asset: ...


class T_GetAssetByStub(Protocol):
    def __call__(self, stub: AssetStub) -> Asset: ...


class T_GetAssetNameList(Protocol):
    def __call__(
        self,
        child_mode: DBInterface.ChildQueryMode = DBInterface.ChildQueryMode.LEAVES,
        sorted: bool = False,
    ) -> list[str]: ...


class T_GetAssetsByStub(Protocol):
    def __call__(self, stubs: Iterable[AssetStub]) -> list[Asset]: ...


class T_GetAttrList(Protocol):
    def __call__(self, attr: str, *, sorted: bool = False) -> list[str]: ...


class T_GetCodeList(Protocol):
    def __call__(
        self,
        *,
        sorted: bool = False,
        child_mode: DBInterface.ChildQueryMode = DBInterface.ChildQueryMode.LEAVES,
    ) -> list[str]: ...


class T_GetEntityByCode(Protocol):
    def __call__(self, entity_type: type[SGEntity], code: str) -> SGEntity: ...


class T_GetEntityCodeList(Protocol):
    def __call__(
        self,
        entity_type: type[SGEntity],
        *,
        sorted: bool = False,
        **kwargs: Unpack[AttrMappingKwargs],
    ) -> list[str]: ...


class T_GetEnvByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Environment: ...


class T_GetEnvByCode(Protocol):
    def __call__(self, code: str) -> Environment: ...


class T_GetEnvById(Protocol):
    def __call__(self, id: int) -> Environment: ...


class T_GetEnvByStub(Protocol):
    def __call__(self, stub: EnvironmentStub) -> Environment: ...


class T_GetEnvsByStub(Protocol):
    def __call__(self, stubs: Iterable[EnvironmentStub]) -> list[Environment]: ...


class T_GetSeqByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Sequence: ...


class T_GetSeqByCode(Protocol):
    def __call__(self, code: str) -> Sequence: ...


class T_GetSeqById(Protocol):
    def __call__(self, id: int) -> Sequence: ...


class T_GetSeqByStub(Protocol):
    def __call__(self, stub: SequenceStub) -> Sequence: ...


class T_GetSeqsByStub(Protocol):
    def __call__(self, stubs: Iterable[SequenceStub]) -> list[Sequence]: ...


class T_GetShotByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Shot: ...


class T_GetShotByCode(Protocol):
    def __call__(self, code: str) -> Shot: ...


class T_GetShotById(Protocol):
    def __call__(self, id: int) -> Shot: ...


class T_GetShotByStub(Protocol):
    def __call__(self, stub: ShotStub) -> Shot: ...


class T_GetShotsByStub(Protocol):
    def __call__(self, stubs: Iterable[ShotStub]) -> list[Shot]: ...
