from dataclasses import dataclass
from pipe.struct.util import JsonSerializable


from typing import Dict, Optional, Type


@dataclass
class AssetStub(JsonSerializable):
    """Represent "stubs" that come from ShotGrid
    Stubs are JSON objects with 3 fields: id, name, and type (which is always Asset in this case)
    """

    disp_name: str
    id: int

    @classmethod
    def from_sg(cls: Type["AssetStub"], sg_stub: Dict) -> "AssetStub":
        return cls(disp_name=sg_stub["name"], id=sg_stub["id"])


@dataclass
class Asset(JsonSerializable):
    name: str
    disp_name: Optional[str]
    id: Optional[int]
    parent: Optional[AssetStub]
    path: Optional[str]
    version = None
    variants: list[AssetStub]

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

    @classmethod
    def from_sg(cls: Type["Asset"], sg_asset: Optional[Dict]) -> Optional["Asset"]:
        if not sg_asset:
            return None

        return cls(
            name=(sg_asset.get("sg_pipe_name") or "ERROR"),
            disp_name=sg_asset.get("code"),
            path=sg_asset.get("sg_path"),
            id=sg_asset.get("id"),
            variants=[AssetStub.from_sg(v) for v in (sg_asset.get("assets") or [])],
            # at least for now, assume only 0 or 1 parents per asset
            parent=(
                AssetStub.from_sg(p[0]) if (p := sg_asset.get("parents")) else None
            ),
        )
