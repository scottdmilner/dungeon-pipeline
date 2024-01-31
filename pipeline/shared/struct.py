import json

from typing import Iterable, Optional, Type, Union


class JsonSerializable:
    def __init__(self, **kwargs) -> None:
        """Initialize a JsonSerializable from a dictionary.

        This function is required to deserialize from JSON.
        """
        # Set values for existing attributes
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise ValueError(f"{self.__class__.__name__} has no attribute '{key}'")

    def __repr__(self):
        return self.to_json()

    @classmethod
    def from_json(
        cls: "Type[JsonSerializable]", json_data: Union[str, bytes, bytearray]
    ):
        data = json.loads(json_data)
        return cls(data)

    def to_json(self) -> str:
        return json.dumps(vars(self), default=lambda o: o.__dict__, indent=4)


class AssetStub(JsonSerializable):
    """Represent "stubs" that come from ShotGrid
    Stubs are JSON objects with 3 fields: id, name, and type (which is always Asset in this case)
    """

    disp_name: str
    id: int

    def __init__(self, disp_name: str, id: int) -> None:
        self.disp_name = disp_name
        self.id = id

    def from_sg(sg_stub: object) -> "AssetStub":
        return AssetStub(sg_stub["name"], sg_stub["id"])


class Asset(JsonSerializable):
    name: str
    disp_name: str
    id: int
    parent: Optional[AssetStub]
    path: str
    version = None
    variants: Optional[Iterable[AssetStub]]

    def __init__(
        self,
        name: str,
        disp_name: Optional[str],
        path: Optional[str] = None,
        id: Optional[int] = None,
        variants: Optional[Iterable[object]] = None,
        parent: Optional[object] = None,
    ) -> None:
        self.name = name
        self.disp_name = disp_name
        self.path = path
        self.id = id
        self.variants = [AssetStub.from_sg(v) for v in variants] if variants else None
        # at least for now, assume only 0 or 1 parents per asset
        self.parent = AssetStub.from_sg(parent[0]) if parent else None

    def from_sg(sg_asset: object) -> "Asset":
        return Asset(
            *[
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
