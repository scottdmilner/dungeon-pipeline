from dataclasses import dataclass
from pipe.struct.util import Diffable, Freezable, JsonSerializable


from typing import Any, Dict, Optional, Type


@dataclass
class AssetStub(JsonSerializable, Freezable):
    """Represent "stubs" that come from ShotGrid
    Stubs are JSON objects with 3 fields: id, name, and type (which is always Asset in this case)
    """

    disp_name: str
    id: int

    def __post_init__(self) -> None:
        super().__post_init__()
        self.__init_freezer__(["disp_name", "id"])

    @classmethod
    def from_sg(cls: Type["AssetStub"], sg_stub: Dict) -> "AssetStub":
        return cls(disp_name=sg_stub["name"], id=sg_stub["id"])


@dataclass
class Asset(Diffable):
    name: str
    disp_name: Optional[str]
    id: Optional[int]
    material_variants: set[str]
    parent: Optional[AssetStub]
    path: Optional[str]
    version = None
    variants: list[AssetStub]

    def __post_init__(self) -> None:
        super().__post_init__()
        self.__init_freezer__(
            [
                "id",
                "parent",
            ]
        )

    @property
    def is_variant(self) -> bool:
        return "_" in self.name

    @property
    def variant_name(self) -> Optional[str]:
        if not self.is_variant:
            return None
        return self.name.split("_")[1]

    @property
    def tex_path(self) -> Optional[str]:
        return f"{self.path}/tex/" + (self.variant_name or "main")

    def sg_diff(self) -> dict[str, Any]:
        """Return a dict with changes made to the asset since it was
        initialized, in the form that ShotGrid expects"""
        sg_diff: dict[str, Any] = {}
        for k, v in self._diff().items():
            # fix names/schemes that are different
            if k == "name":
                sg_diff["sg_pipe_name"] = v
            elif k == "disp_name":
                sg_diff["code"] = v
            elif k == "material_variants":
                sg_diff["sg_material_variants"] = ",".join((i for i in list(v) if i))
            elif k == "variants":
                sg_diff["assets"] = [dict(s) for s in list(v)]
            else:
                sg_diff[k] = v
        return sg_diff

    @classmethod
    def from_sg(cls: Type["Asset"], sg_asset: Optional[Dict]) -> Optional["Asset"]:
        if not sg_asset:
            return None

        return cls(
            name=(sg_asset.get("sg_pipe_name") or "ERROR"),
            disp_name=sg_asset.get("code"),
            material_variants=set(
                (sg_asset.get("sg_material_variants") or "").split(",")
            ),
            path=sg_asset.get("sg_path"),
            id=sg_asset.get("id"),
            variants=[AssetStub.from_sg(v) for v in (sg_asset.get("assets") or [])],
            # at least for now, assume only 0 or 1 parents per asset
            parent=(
                AssetStub.from_sg(p[0]) if (p := sg_asset.get("parents")) else None
            ),
        )
