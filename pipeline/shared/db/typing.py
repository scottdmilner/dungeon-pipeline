from typing import Any, List, Literal, Optional, Tuple, TypedDict, Union

TimeUnit = Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
BasicFilter = Union[
    Tuple[
        str,
        Literal[
            "is", "is_not", "less_than", "greater_than", "contains", "not_contains"
        ],
        Any,
    ],
    Tuple[str, Literal["starts_with", "ends_with"], str],
    Tuple[str, Literal["between", "not_between"], Any, Any],
    Tuple[str, Literal["in_last", "in_next"], int, TimeUnit],
    Tuple[str, Literal["in"], List[Any]],
    Tuple[str, Literal["type_is", "type_is_not"], Optional[str]],
    Tuple[
        str, Literal["in_calendar_day", "in_calendar_week", "in_calendar_month"], int
    ],
    Tuple[
        str,
        Literal[
            "name_contains", "name_not_contains", "name_starts_with", "name_ends_with"
        ],
        str,
    ],
]


class ComplexFilter(TypedDict):
    filter_operator: Literal["any", "all"]
    filters: List[BasicFilter]


Filter = Union[BasicFilter, ComplexFilter]
