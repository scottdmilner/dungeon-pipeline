from pipe.struct.util import JsonSerializable


from typing import Dict, List, Optional


class AssetStub(JsonSerializable):
    """Represent "stubs" that come from ShotGrid
    Stubs are JSON objects with 3 fields: id, name, and type (which is always Asset in this case)
    """

    disp_name: str
    id: int

    def __init__(self, disp_name: str, id: int) -> None:
        self.disp_name = disp_name
        self.id = id

    @staticmethod
    def from_sg(sg_stub: Dict) -> "AssetStub":
        return AssetStub(sg_stub["name"], sg_stub["id"])


class Asset(JsonSerializable):
    name: str
    disp_name: Optional[str]
    id: Optional[int]
    parent: Optional[AssetStub]
    path: Optional[str]
    version = None
    variants: List[AssetStub]

    def __init__(
        self,
        name: str,
        disp_name: Optional[str],
        path: Optional[str] = None,
        id: Optional[int] = None,
        variants: Optional[List[Dict]] = None,
        parent: Optional[List[Dict]] = None,
    ) -> None:
        self.name = name
        self.disp_name = disp_name
        self.path = path
        self.id = id
        self.variants = [AssetStub.from_sg(v) for v in variants] if variants else []
        # at least for now, assume only 0 or 1 parents per asset
        self.parent = AssetStub.from_sg(parent[0]) if parent else None

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

    @staticmethod
    def from_sg(sg_asset: Optional[Dict]) -> Optional["Asset"]:
        if not sg_asset:
            return None
        return Asset(
            *[  # type: ignore[arg-type]
                sg_asset.get(key)
                for key in [
                    "sg_pipe_name",
                    "code",
                    "sg_path",
                    "id",
                    "assets",
                    "parents",
                ]
            ]
        )
