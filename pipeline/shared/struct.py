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

    def to_json(self):
        return json.dumps(vars(self), default=lambda o: o.__dict__, indent=4)


class Asset(JsonSerializable):
    name = None
    _path = None
    version = None
    variants: Iterable[str] = None
    id = None

    def __init__(
        self, name: str, path: Optional[str] = None, id: Optional[int] = None
    ) -> None:
        self.name = name
        self._path = path
        self.id = id

    def fromSG(sg_asset: object) -> "Asset":
        return Asset(sg_asset["code"], "", sg_asset["id"])
