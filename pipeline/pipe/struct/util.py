import json
from dataclasses import dataclass, fields
from typing import get_args, get_origin, Any, Type, TypeVar, Union

FT = TypeVar("FT")
Self = TypeVar("Self")  # In Python 3.11+, just use `from typing import Self`


@dataclass
class JsonSerializable:
    """
    The JsonSerializable class provides utility to allow loading/writing
    dataclass objects to/from JSON files.

    Subclasses should also be decorated as a dataclass, like so:

    ```
    @dataclass
    class MyClass(JsonSerializable):
        data1: str
        data2: int
        data3: list[bool]
        ...
    ```

    Make sure to only use types that are actually serializable to JSON format,
    such as int, str, dict, list, bool, IntEnum, etc. When type hinting, prefer
    dict to Dict, and list to List. You may use Optional or Union[type, None]
    as well. Any other types will probably not work properly.
    """

    @classmethod
    def from_json(cls: Type[Self], json_data: Union[str, bytes, bytearray]) -> Self:
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

    def __post_init__(self) -> None:
        """After initializing the fields, recurse through and ensure that
        types match"""
        for field in fields(self):
            value = getattr(self, field.name)
            field_type = field.type

            if get_origin(field_type) == Union:
                args = get_args(field_type)
                # if one of the options in the Union is None
                if type(None) in args:
                    if value is None:
                        continue  # go to next iteration of for loop
                    elif len(args) == 2:
                        # if there is only one option besides None, set
                        #   field_type to the other option (if it was None,
                        #   we handled that up above)
                        field_type = next(a for a in args if a != type(None))
                    else:
                        # Otherwise, there are 2+ options besides None in the
                        #   Union. Raise an error
                        raise ValueError(
                            "Cannot currently handle Union types other than Optional"
                        )
                else:
                    # This is a Union not created by Optional. Raise an error
                    raise ValueError(
                        "Cannot currently handle Union types other than Optional"
                    )

            origin_type = get_origin(field_type)
            if origin_type == dict:
                key_type, value_type = get_args(field_type)
                setattr(
                    self,
                    field.name,
                    {
                        self._spread_cast(key_type, k): self._spread_cast(value_type, v)
                        for k, v in value.items()
                    },
                )
            elif origin_type == list:
                value_type = get_args(field_type)
                setattr(
                    self, field.name, [self._spread_cast(value_type, v) for v in value]
                )
            else:
                if isinstance(value, field_type):
                    continue
                try:
                    setattr(self, field.name, self._spread_cast(field_type, value))
                except Exception:
                    raise ValueError(
                        f"Expected {field.name} to be {field_type}, "
                        f"got {repr(value)}"
                    )
