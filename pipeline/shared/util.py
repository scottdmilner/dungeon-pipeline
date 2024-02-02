import platform
import importlib
import importlib.util

from inspect import getmembers, isabstract, isclass
from pathlib import Path
from typing import Optional, Union


def find_implementation(cls: type, module: str, package: Optional[str] = None) -> type:
    """Find an implementation of the class in the specified module."""
    # Check if the specified module exists
    if importlib.util.find_spec(module, package):
        # Import the module
        imported_module = importlib.import_module(module, package)

        # Check if the submodule contains an implementation of the class
        classes = getmembers(
            imported_module,
            lambda obj: isclass(obj) and not isabstract(obj) and issubclass(obj, cls),
        )

        # Check if more or less than one implementation was found
        if len(classes) < 1:
            raise AssertionError(
                f"module '{module}' does not contain an "
                f"implementation of class '{cls.__name__}'"
            )
        elif len(classes) > 1:
            raise AssertionError(
                f"module '{module}' contains multiple "
                f"implementations of class '{cls.__name__}'"
            )

        # Return the implementing class
        return classes[0][1]

    else:
        raise ValueError(f"could not find module '{module}'")


def get_pipe_path() -> Path:
    return Path(__file__).resolve().parents[1]


def get_production_path() -> Path:
    system = platform.system()
    if system == "Linux":
        return Path("/groups/dungeons/production")
    elif system == "Windows":
        return Path("G:/dungeons/production")
    else:
        raise NotImplementedError(
            "Production path is not defined for this operating system"
        )


def get_asset_path() -> Path:
    return get_production_path() / "asset"


def resolve_mapped_path(path: Union[str, Path]) -> Path:
    """Windows mapped drive workaround. Adapated from: https://bugs.python.org/msg309160"""
    path = Path(path).resolve()

    if platform.system() != "Windows":
        return path

    mapped_paths = []
    for drive in "ZYXWVUTSRQPONMLKJIHGFEDCBA":
        root = Path("{}:/".format(drive))
        try:
            mapped_paths.append(root / path.relative_to(root.resolve()))
        except (ValueError, OSError):
            pass
    return min(mapped_paths, key=lambda x: len(str(x)), default=path)
