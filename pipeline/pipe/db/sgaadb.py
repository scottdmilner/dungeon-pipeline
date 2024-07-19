from __future__ import annotations

import logging
import threading

from abc import ABC, abstractmethod, abstractproperty
from dataclasses import dataclass
from functools import partialmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing
    from .typing import Filter

from pipe.struct.db import Asset, AssetStub, Sequence, SequenceStub, Shot, ShotStub

from .baseclass import DB

from . import shotgun_api3


log = logging.getLogger(__name__)


@dataclass(eq=True, frozen=True)
class SG_Config:
    project_id: int
    # DO NOT SHARE/COMMIT THE sg_key!!! IT'S EQUIVALENT TO AN ADMIN PW!!!
    sg_key: str
    sg_script: str
    sg_server: str


class SGaaDB(DB):
    """ShotGrid as a Database"""

    _sg: shotgun_api3.Shotgun
    _id: int
    _sg_asset_list: list[dict]
    _sg_sequence_list: list[dict]
    _sg_shot_list: list[dict]
    _cache_lock: threading.Lock
    _update_notifier: threading.Condition
    _update_thread: threading.Thread

    _conn_instances: dict[SG_Config, SGaaDB] = {}

    @classmethod
    def Get(cls, config: SG_Config) -> SGaaDB:
        if config in cls._conn_instances:
            return cls._conn_instances[config]
        else:
            log.debug("Creating new DB instance.")
            cls._conn_instances[config] = cls(config)
            return cls._conn_instances[config]

    def __init__(self, config: SG_Config) -> None:
        self._sg = shotgun_api3.Shotgun(
            config.sg_server, config.sg_script, config.sg_key
        )
        self._id = config.project_id

        self._cache_lock = threading.Lock()
        self._update_notifier = threading.Condition()

        self._load_sg_asset_list()
        self._load_sg_sequence_list()
        self._load_sg_shot_list()

        self._update_thread = threading.Thread(
            target=self._threaded_updater, daemon=True
        )
        self._update_thread.start()

        super().__init__()

    def _threaded_updater(self) -> None:
        while True:
            with self._update_notifier:
                # wait until the cache is manually expired or timeout (5 min) reached
                try:
                    self._update_notifier.wait(timeout=300)
                except TimeoutError:
                    pass

                log.debug("Cache expired, refreshing list")
                # sequences don't update freqently, so we just pull them once
                self._load_sg_asset_list()
                self._load_sg_shot_list()

    def _load_sg_asset_list(self) -> None:
        """Load the list of assets from SG to local cache"""
        with self._cache_lock:
            query = _AssetListQuery(self._id)
            self._sg_asset_list = query.exec(self._sg)

    def _load_sg_sequence_list(self) -> None:
        """Load the list of sequences from SG to local cache"""
        with self._cache_lock:
            query = _SequenceListQuery(self._id)
            self._sg_sequence_list = query.exec(self._sg)

    def _load_sg_shot_list(self) -> None:
        """Load the list of shots from SG to local cache"""
        with self._cache_lock:
            query = _ShotListQuery(self._id)
            self._sg_shot_list = query.exec(self._sg)

    def expire_cache(self) -> None:
        with self._update_notifier:
            self._update_notifier.notify()

    def get_asset_by_attr(self, attr: str, attr_val: str | int) -> Asset:
        attr = Asset.map_sg_field_names(attr)
        return Asset.from_sg(
            next((a for a in self._sg_asset_list if a[attr] == attr_val), None)
        )

    if TYPE_CHECKING:

        class GetAssetAttrPartial(typing.Protocol):
            def __call__(self, attr_val: str | int) -> Asset: ...

    get_asset_by_name: GetAssetAttrPartial = partialmethod(
        get_asset_by_attr, "disp_name"
    )  # type: ignore[assignment]
    get_asset_by_id: GetAssetAttrPartial = partialmethod(get_asset_by_attr, "id")  # type: ignore[assignment]

    def get_asset_by_stub(self, stub: AssetStub) -> Asset:
        return self.get_asset_by_id(stub.id)

    def get_assets_by_stub(self, stubs: typing.Iterable[AssetStub]) -> list[Asset]:
        ids = [s.id for s in stubs]
        return [Asset.from_sg(a) for a in self._sg_asset_list if a["id"] in ids]

    def get_asset_attr_list(
        self,
        attr: str,
        *,
        child_mode: DB.ChildQueryMode = DB.ChildQueryMode.LEAVES,
        sorted: bool = False,
    ) -> list[str]:
        """Get a list of a single attribute on the asset list"""
        attr = Asset.map_sg_field_names(attr)

        if child_mode == DB.ChildQueryMode.ALL:
            arr = [a[attr] for a in self._sg_asset_list]
        elif child_mode == DB.ChildQueryMode.CHILDREN:
            arr = [a[attr] for a in self._sg_asset_list if a["parents"]]
        elif child_mode == DB.ChildQueryMode.ROOTS:
            arr = [a[attr] for a in self._sg_asset_list if not a["parents"]]
        elif child_mode == DB.ChildQueryMode.PARENTS:
            arr = [a[attr] for a in self._sg_asset_list if a["assets"]]
        elif child_mode == DB.ChildQueryMode.LEAVES:
            arr = [a[attr] for a in self._sg_asset_list if not a["assets"]]
        else:
            raise IndexError("Not a valid ChildQueryMode", child_mode)

        if sorted:
            arr.sort()
        return arr

    if TYPE_CHECKING:

        class GetAssetAttrListPartial(typing.Protocol):
            def __call__(
                self,
                child_mode: DB.ChildQueryMode = DB.ChildQueryMode.LEAVES,
                sorted: bool = False,
            ) -> list[str]: ...

    get_asset_name_list: GetAssetAttrListPartial = partialmethod(
        get_asset_attr_list, "disp_name"
    )  # type: ignore[assignment]

    def get_assets_by_name(self, names: typing.Iterable[str]) -> list[Asset]:
        self.get_asset_name_list()
        return [
            Asset.from_sg(i)
            for i in set([a for a in self._sg_asset_list if a["code"] in names])
        ]

    def update_asset(self, asset: Asset) -> bool:
        try:
            assert asset.id
            self._sg.update("Asset", asset.id, asset.sg_diff())
        except Exception as e:
            log.error(e)
            return False
        finally:
            self.expire_cache()
        return True

    def get_sequence_by_attr(self, attr: str, attr_val: int | str) -> Sequence:
        attr = Sequence.map_sg_field_names(attr)
        return Sequence.from_sg(
            next((s for s in self._sg_sequence_list if s.get(attr) == attr_val), None)
        )

    if TYPE_CHECKING:

        class GetSequenceAttrPartial(typing.Protocol):
            def __call__(self, attr_val: str | int) -> Sequence: ...

    get_sequence_by_code: GetSequenceAttrPartial = partialmethod(
        get_sequence_by_attr, "code"
    )  # type: ignore[assignment]
    get_sequence_by_id: GetSequenceAttrPartial = partialmethod(
        get_sequence_by_attr, "id"
    )  # type: ignore[assignment]

    def get_sequence_by_stub(self, stub: SequenceStub) -> Sequence:
        return self.get_sequence_by_id(stub.id)

    def get_sequence_attr_list(self, attr: str, *, sorted: bool = False) -> list[str]:
        """Get a list of a single attribute on the sequence list"""
        attr = Sequence.map_sg_field_names(attr)
        arr = [s[attr] for s in self._sg_sequence_list]
        if sorted:
            arr.sort()
        return arr

    if TYPE_CHECKING:

        class GetSequenceAttrListPartial(typing.Protocol):
            def __call__(self, sorted: bool = False) -> list[str]: ...

    get_sequence_code_list: GetSequenceAttrListPartial = partialmethod(
        get_sequence_attr_list, "code"
    )  # type: ignore[assignment]

    def get_shot_by_attr(self, attr: str, attr_val: int | str) -> Shot:
        attr = Shot.map_sg_field_names(attr)
        return Shot.from_sg(
            next((s for s in self._sg_shot_list if s.get(attr) == attr_val), None)
        )

    if TYPE_CHECKING:

        class GetShotAttrPartial(typing.Protocol):
            def __call__(self, attr_val: int | str) -> Shot: ...

    get_shot_by_code: GetShotAttrPartial = partialmethod(get_shot_by_attr, "code")  # type: ignore[assignment]
    get_shot_by_id: GetShotAttrPartial = partialmethod(get_shot_by_attr, "id")  # type: ignore[assignment]

    def get_shot_by_stub(self, stub: ShotStub) -> Shot:
        return self.get_shot_by_id(stub.id)

    def get_shot_attr_list(self, attr: str, *, sorted: bool = False) -> list[str]:
        attr = Shot.map_sg_field_names(attr)
        arr = [s[attr] for s in self._sg_shot_list]
        if sorted:
            arr.sort()
        return arr

    if TYPE_CHECKING:

        class GetShotAttrListPartial(typing.Protocol):
            def __call__(self, sorted: bool = False) -> list[str]: ...

    get_shot_code_list: GetShotAttrListPartial = partialmethod(
        get_shot_attr_list, "code"
    )  # type: ignore[assignment]


class _Query(ABC):
    """Helper class for making queries to a SG connection instance"""

    project_id: int
    fields: list[str]
    filters: list[Filter]

    def __init__(
        self,
        project_id: int,
        *,
        extra_fields: typing.Sequence[str] | None = None,
        override_default_fields: bool = False,
    ) -> None:
        if extra_fields is None:
            extra_fields = []
        self.project_id = project_id
        self.fields = self._construct_fields(extra_fields, override_default_fields)
        self.filters = self._construct_filters()

    def _construct_fields(
        self, extra_fields: typing.Sequence[str], override_default_fields: bool
    ) -> list[str]:
        """Construct the fields needed for the ShotGrid query"""
        if override_default_fields:
            return list(extra_fields)
        else:
            return list(set(self._base_fields + list(extra_fields)))

    def _construct_filters(self) -> list[Filter]:
        """Construct the list of filters needed for the ShotGrid query"""
        base_filters = self._base_filters
        base_filters.insert(
            0, ("project", "is", {"type": "Project", "id": self.project_id})
        )
        return base_filters

    def insert_field(self, field: str) -> None:
        self.fields.append(field)

    def insert_filter(self, filter: Filter) -> None:
        self.filters.append(filter)

    @abstractmethod
    def exec(self, sg: shotgun_api3.Shotgun) -> typing.Any:
        pass

    @abstractproperty
    def _base_fields(self) -> list[str]:
        pass

    @abstractproperty
    def _base_filters(self) -> list[Filter]:
        pass


class _AssetListQuery(_Query):
    """Helper class for making queries about assets to a SG connection instance"""

    _untracked_asset_types = [
        "FX",
        "Graphic",
        "Matte Painting",
        "Vehicle",
        "Tool",
        "Font",
    ]

    # Override
    def exec(self, sg: shotgun_api3.Shotgun) -> list[dict]:
        return sg.find("Asset", self.filters, self.fields)

    # Override
    @property
    def _base_fields(self) -> list[str]:
        return [
            "code",  # display name
            "sg_pipe_name",  # internal name
            "sg_path",  # asset path
            "id",  # asset id
            "parents",  # parent assets
            "assets",  # child assets
            "tags",  # asset tags
            "shots",  # shots asset present in
            "sg_material_variants",  # material variants
        ]

    # Override
    @property
    def _base_filters(self) -> list[Filter]:
        filters: list[Filter] = [
            ("sg_status_list", "is_not", "oop"),
            {
                "filter_operator": "all",
                "filters": [
                    ("sg_asset_type", "is_not", t) for t in self._untracked_asset_types
                ],
            },
        ]

        return filters


class _ShotListQuery(_Query):
    """Helper class for making queries about shots to a SG connection instance"""

    # Override
    def exec(self, sg: shotgun_api3.Shotgun) -> list[dict]:
        return sg.find("Shot", self.filters, self.fields)

    # Override
    @property
    def _base_fields(self) -> list[str]:
        return [
            "code",
            "id",
            "sg_cut_in",
            "sg_cut_out",
            "sg_cut_duration",
            "sg_sequence",
        ]

    # Override
    @property
    def _base_filters(self) -> list[Filter]:
        filters: list[Filter] = [("sg_status_list", "is_not", "oop")]

        return filters


class _SequenceListQuery(_Query):
    """Helper class for making queries about sequences to a SG connection instance"""

    # Override
    def exec(self, sg: shotgun_api3.Shotgun) -> list[dict]:
        return sg.find("Sequence", self.filters, self.fields)

    # Override
    @property
    def _base_fields(self) -> list[str]:
        return [
            "code",
            "id",
            "shots",
        ]

    # Override
    @property
    def _base_filters(self) -> list[Filter]:
        filters: list[Filter] = [("sg_status_list", "is_not", "oop")]

        return filters
