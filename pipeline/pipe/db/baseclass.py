from enum import Enum

from .interface import DBInterface


class DB(DBInterface):
    """Database"""

    class ChildQueryMode(Enum):
        # children + assets w/ no children
        LEAVES = 0
        # all
        ALL = 1
        # only assets that have parents
        CHILDREN = 2
        # only assets that have children
        PARENTS = 3
        # top-level assets regardless of if they have children
        ROOTS = 4

    def __init__(self):
        pass
