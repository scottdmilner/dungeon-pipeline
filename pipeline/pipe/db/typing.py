from typing import Any, Literal, Optional, TypedDict, Union

TimeUnit = Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
BasicFilter = Union[
    tuple[
        str,
        Literal[
            "is", "is_not", "less_than", "greater_than", "contains", "not_contains"
        ],
        Any,
    ],
    tuple[str, Literal["starts_with", "ends_with"], str],
    tuple[str, Literal["between", "not_between"], Any, Any],
    tuple[str, Literal["in_last", "in_next"], int, TimeUnit],
    tuple[str, Literal["in"], list[Any]],
    tuple[str, Literal["type_is", "type_is_not"], Optional[str]],
    tuple[
        str, Literal["in_calendar_day", "in_calendar_week", "in_calendar_month"], int
    ],
    tuple[
        str,
        Literal[
            "name_contains", "name_not_contains", "name_starts_with", "name_ends_with"
        ],
        str,
    ],
]


class ComplexFilter(TypedDict):
    filter_operator: Literal["any", "all"]
    filters: list[BasicFilter]


Filter = Union[BasicFilter, ComplexFilter]
