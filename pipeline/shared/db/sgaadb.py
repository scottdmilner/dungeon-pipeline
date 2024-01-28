import logging
from datetime import datetime, timedelta
from abc import ABC, abstractmethod, abstractproperty
from typing import Any, Callable, Iterable, List, Sequence, Set, Type

from shared.struct import Asset

from .baseclass import DB
from .typing import Filter

from . import shotgun_api3

log = logging.getLogger(__name__)


class SGaaDB(DB):
    """ShotGrid as a Database"""

    sg: Type[shotgun_api3.Shotgun]
    id: int
    sg_asset_list: List[object]
    sg_asset_list_utime: datetime
    sg_asset_list_exp: timedelta = timedelta(minutes=2)

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
        self.sg = shotgun_api3.Shotgun(sg_server, sg_script, sg_key)
        self.id = id

        self._load_sg_asset_list()
        # TODO: some sort of timeout/expiration
        super().__init__()

    def _load_sg_asset_list(self) -> None:
        """Loads the list of assets from SG"""
        query = self._AssetListQuery(self.id)
        self.sg_asset_list = query.exec(self.sg)
        self.sg_asset_list_utime = datetime.now()

    def _asset_access(func: Callable) -> Callable:
        """Check if the asset list has expired before making calls"""

        def inner(self, *args, **kwargs) -> Any:
            if self.sg_asset_list_utime + self.sg_asset_list_exp < datetime.now():
                log.debug("Asset cache expired, refreshing list")
                self._load_sg_asset_list()
            return func(self, *args, **kwargs)

        return inner

    @_asset_access
    def get_asset_by_name(self, name: str) -> Asset:
        return next((a for a in self.sg_asset_list if a["code"] == name), None)

    @_asset_access
    def get_asset_name_list(self) -> Sequence[str]:
        return [a["code"] for a in self.sg_asset_list]

    @_asset_access
    def get_assets(self, names: Iterable[str]) -> Set[Asset]:
        return set(
            [Asset.fromSG(a) for a in self.sg_asset_list if a["code"] in names] or None
        )

    class _Query(ABC):
        _untracked_asset_types = [
            "Character",
            "FX",
            "Graphic",
            "Matte Painting",
            "Vehicle",
            "Tool",
            "Font",
        ]

        project_id: int
        fields: List[str]
        filter_out_variants: bool
        filters: List[Filter]

        def __init__(
            self,
            project_id: int,
            extra_fields: Sequence[str] = [],
            override_default_fields: bool = False,
            filter_out_variants: bool = True,
        ) -> None:
            self.project_id = project_id
            self.fields = self._construct_fields(extra_fields, override_default_fields)
            self.filter_out_variants = filter_out_variants
            self.filters = self._construct_filters()

        def _construct_fields(
            self, extra_fields: Sequence[str], override_default_fields: bool
        ) -> Sequence[str]:
            """Construct the fields needed for the ShotGrid query"""
            if override_default_fields:
                return extra_fields
            else:
                return list(set(self._base_fields + extra_fields))

        def _construct_filters(self) -> Sequence[Filter]:
            """Construct the list of filters needed for the ShotGrid query"""
            base_filters = self._base_filters
            base_filters.insert(
                0, ["project", "is", {"type": "Project", "id": self.project_id}]
            )
            return base_filters

        def insert_field(self, field: str) -> None:
            self.fields.append(field)

        def insert_filter(self, filter: Filter) -> None:
            self.filters.append(filter)

        @abstractmethod
        def exec(self, sg: Type[shotgun_api3.Shotgun]) -> Any:
            pass

        @abstractproperty
        def _base_fields(self) -> List[str]:
            pass

        @abstractproperty
        def _base_filters(self) -> List[Filter]:
            pass

    class _AssetListQuery(_Query):
        # Override
        def exec(self, sg: Type[shotgun_api3.Shotgun]) -> List[Asset]:
            return sg.find("Asset", self.filters, self.fields)

        # Override
        @property
        def _base_fields(self) -> List[str]:
            return [
                "code",  # display name
                "sg_pipe_name"  # internal name
                "sg_path",  # asset path
                "id",  # asset id
                "parents",  # parent assets
                "assets",  # child assets
                "tags",  # asset tags
                "shots",  # shots asset present in
            ]

        # Override
        @property
        def _base_filters(self) -> List[Filter]:
            filters = [
                ["sg_status_list", "is_not", "oop"],
                {
                    "filter_operator": "all",
                    "filters": [
                        ["sg_asset_type", "is_not", t]
                        for t in self._untracked_asset_types
                    ],
                },
            ]

            if self.filter_out_variants:
                # TODO
                pass

            return filters

    class _ShotListQuery(_Query):
        """TODO"""

        # Override
        @property
        def _base_fields() -> Sequence[str]:
            return ["code", "id", "sg_cut_in", "sg_cut_out"]


# """ShotGridQueryHelpers from 2024 pipeline
#    (https://github.com/Student-Accomplice-Pipeline-Team/accomplice_pipe/commit/e079297149b15ce6918ee24ea0055f9b90e45cdd)"""
# class ShotGridQueryHelper(ABC):
#     _untracked_asset_types = [
#         "Character",
#         "FX",
#         "Graphic",
#         "Matte Painting",
#         "Vehicle",
#         "Tool",
#         "Font",
#     ]

#     def __init__(
#         self,
#         database: SGaaDB,
#         additional_fields: list = [],
#         override_fields=False,
#     ):
#         self.sgdb = database
#         self.sg = database.sg
#         self.fields = self._construct_all_fields(additional_fields, override_fields)

#         base_filters = self._create_base_filter()
#         # The project filter is common to all queries
#         base_filters.insert(
#             0, ["project", "is", {"type": "Project", "id": self.sgdb.PROJECT_ID}]
#         )
#         self.filters = base_filters

#     def _construct_all_fields(
#         self, additional_fields: list = [], override_fields=False
#     ):
#         if override_fields:
#             return additional_fields
#         else:
#             # Remove duplicates
#             return list(set(self._create_base_fields() + additional_fields))

#     def _get_code_name_filter(self, names: Iterable[str]) -> dict:
#         return {
#             "filter_operator": "any",
#             "filters": [["code", "is", name] for name in names],
#         }

#     @abstractmethod
#     def _create_base_filter(self) -> list:
#         pass

#     @abstractmethod
#     def _create_base_fields(self) -> list:
#         pass

#     @abstractmethod
#     def get(self):
#         pass


# class AssetQueryHelper(ShotGridQueryHelper):
#     """An abstract class containing shared methods for querying assets."""

#     def __init__(
#         self,
#         database: SGaaDB,
#         additional_fields: list = [],
#         override_fields=False,
#         filter_variants=True,
#     ):
#         self.filter_variants = filter_variants
#         super().__init__(database, additional_fields, override_fields)

#     # Override
#     def _create_base_fields(self) -> list:
#         return [
#             "code",
#             "sg_path",
#             "id",
#             "parents",  # Parents are now included by default so that we can filter for everything that doesn't have parents.
#         ]

#     # Override
#     def _create_base_filter(self) -> list:
#         return [
#             ["sg_status_list", "is_not", "oop"],
#             {
#                 "filter_operator": "all",
#                 "filters": [
#                     ["sg_asset_type", "is_not", t] for t in self._untracked_asset_types
#                 ],
#             },
#         ]

#     # def _get_path_name_filter(self, names: Iterable[str]) -> dict:
#     #     return {
#     #         "filter_operator": "any",
#     #         "filters": [["sg_path", "ends_with", name.lower()] for name in names],
#     #     }

#     def _get_all_asset_json(self):
#         assets = self.sg.find("Asset", self.filters, self.fields)
#         if self.filter_variants:
#             assets = self._filter_out_child_assets(assets)
#         return assets

#     def _filter_out_child_assets(self, assets):
#         return [
#             asset for asset in assets if asset["parents"] == []
#         ]  # Filter out child assets (variants)

#     # def _construct_filter_by_path_end_name(self, name: str) -> list:
#     #     return self._get_path_name_filter([name])

#     # def _construct_filter_by_path_end_names(self, names: Iterable[str]) -> list:
#     #     return self._get_path_name_filter(names)


# class GetAllAssetsByName(AssetQueryHelper):
#     def __init__(
#         self,
#         database: ShotGridDatabase,
#         names: Iterable[str],
#         additional_fields: list = [],
#         override_fields=False,
#         filter_out_variants=True,
#     ):
#         self.names = names
#         super().__init__(
#             database, additional_fields, override_fields, filter_out_variants
#         )

#     def _get_all_assets_by_path_end_name(self, names: Iterable[str]):
#         self.filters.append(self._construct_filter_by_path_end_names(names))
#         return self._get_all_asset_json()

#     def _get_all_assets_by_code_names(self, names: Iterable[str]):
#         self.filters.append(self._get_code_name_filter(names))
#         return self._get_all_asset_json()

#     def _remove_assets_that_do_not_match_name_explicitly(
#         self, assets_json, names: Iterable[str]
#     ):
#         new_assets = []
#         for asset in assets_json:
#             path = asset["sg_path"]
#             # base_name = os.path.basename(path) # I'd do this, but IDK if it'll work on Windows
#             base_name = path.split("/")[-1]
#             if base_name.lower() in names:
#                 new_assets.append(asset)
#         return new_assets

#     # Override
#     def get(self):
#         attempt_by_path_end = self._get_all_assets_by_path_end_name(self.names)
#         if len(attempt_by_path_end) > 0:  # First attempt to find assets by path end
#             print("Assets found by path end name.")
#             return self._remove_assets_that_do_not_match_name_explicitly(
#                 attempt_by_path_end, self.names
#             )

#         # If that fails, try to find assets by code name
#         print(
#             "No assets found by path end name. Attempting to find assets by code name."
#         )
#         self.filters = self._create_base_filter()
#         return self._get_all_assets_by_code_names(self.names)
