import logging
from abc import ABC, abstractmethod, abstractproperty
from datetime import datetime, timedelta
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from pipe.struct.asset import Asset, AssetStub

from .baseclass import DB
from .typing import Filter

from . import shotgun_api3

RT = TypeVar("RT")  # return type

log = logging.getLogger(__name__)


class SGaaDB(DB):
    """ShotGrid as a Database"""

    _sg: shotgun_api3.Shotgun
    _id: int
    _sg_asset_list: List[dict]
    _sg_asset_list_utime: datetime
    # MAGIC NUMBER: cache expiry time
    _sg_asset_list_exp: timedelta = timedelta(minutes=2)
    _force_expire: bool

    def __init__(self, *args) -> None:
        # unpack SG_Config object if we're passed one
        # instead of individual arguments
        if len(args) == 1:
            self._init(
                args[0].sg_server,
                args[0].sg_script,
                args[0].sg_key,
                args[0].project_id,
            )
        else:
            self._init(*args)

    def _init(self, sg_server: str, sg_script: str, sg_key: str, id: int) -> None:
        self._sg = shotgun_api3.Shotgun(sg_server, sg_script, sg_key)
        self._id = id

        self._load_sg_asset_list()
        self._force_expire = False
        super().__init__()

    def _load_sg_asset_list(self) -> None:
        """Loads the list of assets from SG to local cache"""
        query = self._AssetListQuery(self._id)
        self._sg_asset_list = query.exec(self._sg)
        self._sg_asset_list_utime = datetime.now()

    def _asset_uptodate(func: Callable[..., RT]) -> Callable[..., RT]:  # type: ignore[misc]
        """Decorator to check if the asset list has expired before making calls"""

        def inner(self: "SGaaDB", *args, **kwargs) -> RT:
            if (
                self._sg_asset_list_utime + self._sg_asset_list_exp < datetime.now()
            ) or self._force_expire:
                log.debug("Asset cache expired, refreshing list")
                self._force_expire = False
                self._load_sg_asset_list()
            return func(self, *args, **kwargs)

        return inner

    def expire_cache(self) -> None:
        self._force_expire = True

    @_asset_uptodate
    def get_asset_by_attr(
        self, attr: str, attr_val: Union[str, int]
    ) -> Optional[Asset]:
        return Asset.from_sg(
            next((a for a in self._sg_asset_list if a[attr] == attr_val), None)
        )

    def get_asset_by_name(self, name: str) -> Optional[Asset]:
        return self.get_asset_by_attr("code", name)

    def get_asset_by_id(self, id: int) -> Optional[Asset]:
        return self.get_asset_by_attr("id", id)

    @_asset_uptodate
    def get_asset_by_stub(self, stub: AssetStub) -> Optional[Asset]:
        return Asset.from_sg(next(a for a in self._sg_asset_list if a["id"] == stub.id))

    @_asset_uptodate
    def get_assets_by_stub(self, stubs: Iterable[AssetStub]) -> List[Optional[Asset]]:
        ids = [s.id for s in stubs]
        return [Asset.from_sg(a) for a in self._sg_asset_list if a["id"] in ids]

    @_asset_uptodate
    def get_asset_attr_list(
        self,
        attr: str,
        child_mode: DB.ChildQueryMode = DB.ChildQueryMode.LEAVES,
        sorted: bool = False,
    ) -> List[str]:
        """Get a list of a single attribute on the asset list
        Valid attrs: name, code, sg_path, sg_pipe_name, id
        """
        if attr == "name":
            attr = "sg_pipe_name"
        if attr == "path":
            attr = "sg_path"
        if attr == "disp_name":
            attr = "code"

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

    def get_asset_name_list(
        self,
        child_mode: DB.ChildQueryMode = DB.ChildQueryMode.LEAVES,
        sorted: bool = False,
    ) -> List[str]:
        return self.get_asset_attr_list("disp_name", child_mode, sorted)

    @_asset_uptodate
    def get_assets_by_name(self, names: Iterable[str]) -> List[Asset]:
        return [
            a
            for a in (
                Asset.from_sg(i)
                for i in set([a for a in self._sg_asset_list if a["code"] in names])
            )
            if a
        ]  # wrap in list comprehension to remove Nones

    def update_asset(self, asset: Asset) -> bool:
        try:
            assert asset.id
            self._sg.update("Asset", asset.id, asset.sg_diff())
            return True
        except Exception as e:
            log.error(e)
        finally:
            self.expire_cache()
        return False

    class _Query(ABC):
        """Helper class for making queries to a SG connection instance"""

        project_id: int
        fields: List[str]
        filters: List[Filter]

        def __init__(
            self,
            project_id: int,
            extra_fields: Optional[Sequence[str]] = None,
            override_default_fields: bool = False,
        ) -> None:
            if extra_fields is None:
                extra_fields = []
            self.project_id = project_id
            self.fields = self._construct_fields(extra_fields, override_default_fields)
            self.filters = self._construct_filters()

        def _construct_fields(
            self, extra_fields: Sequence[str], override_default_fields: bool
        ) -> List[str]:
            """Construct the fields needed for the ShotGrid query"""
            if override_default_fields:
                return list(extra_fields)
            else:
                return list(set(self._base_fields + list(extra_fields)))

        def _construct_filters(self) -> List[Filter]:
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
        def exec(self, sg: shotgun_api3.Shotgun) -> Any:
            pass

        @abstractproperty
        def _base_fields(self) -> List[str]:
            pass

        @abstractproperty
        def _base_filters(self) -> List[Filter]:
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
        def exec(self, sg: shotgun_api3.Shotgun) -> List[dict]:
            return sg.find("Asset", self.filters, self.fields)

        # Override
        @property
        def _base_fields(self) -> List[str]:
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
        def _base_filters(self) -> List[Filter]:
            filters: List[Filter] = [
                ("sg_status_list", "is_not", "oop"),
                {
                    "filter_operator": "all",
                    "filters": [
                        ("sg_asset_type", "is_not", t)
                        for t in self._untracked_asset_types
                    ],
                },
            ]

            return filters

    class _ShotListQuery(_Query):
        """Helper class for making queries about shots to a SG connection instance"""

        """TODO"""

        # Override
        @property
        def _base_fields(self) -> List[str]:
            return ["code", "id", "sg_cut_in", "sg_cut_out"]
