from dataclasses import dataclass, fields
import json
from typing import get_args, get_origin, Any, Type, TypeVar, Union

FT = TypeVar("FT")


@dataclass
class JsonSerializable:
    @classmethod
    def from_json(
        cls: Type["JsonSerializable"], json_data: Union[str, bytes, bytearray]
    ):
        data = json.loads(json_data)
        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(
            vars(self), default=lambda o: o.__dict__, indent=4, ensure_ascii=False
        )

    @staticmethod
    def _spread_cast(ftype: Type[FT], value: Any) -> FT:
        """Helper function to spread out args"""
        if isinstance(value, ftype):
            return value
        elif isinstance(value, dict):
            return ftype(**value)
        elif isinstance(value, list):
            return ftype(*value)
        else:
            return ftype(value)  # type: ignore[call-arg]

    def __post_init__(self):
        """After initializing the fields, recurse through and ensure that types match"""
        for field in fields(self):
            value = getattr(self, field.name)
            ftype = field.type

            if get_origin(ftype) == Union:
                args = get_args(ftype)
                if type(None) in args:
                    # if Optional is valid and value is None
                    if value is None:
                        continue
                    if len(args) == 2:
                        ftype = args[0]
                    else:
                        raise ValueError(
                            "Cannot currently handle Union types " "other than Optional"
                        )

            otype = get_origin(ftype)
            if otype == dict:
                ktype, vtype = get_args(ftype)
                setattr(
                    self,
                    field.name,
                    {
                        self._spread_cast(ktype, k): self._spread_cast(vtype, v)
                        for k, v in value.items()
                    },
                )
            elif otype == list:
                vtype = get_args(ftype)
                setattr(self, field.name, [self._spread_cast(vtype, v) for v in value])
            else:
                if isinstance(value, ftype):
                    continue
                try:
                    setattr(self, field.name, self._spread_cast(ftype, value))
                except Exception:
                    raise ValueError(
                        f"Expected {field.name} to be {ftype}, " f"got {repr(value)}"
                    )
