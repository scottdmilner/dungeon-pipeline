from __future__ import annotations

import ffmpeg  # type: ignore[import-untyped]
import logging
import os
import platform
import shutil
import subprocess
import sys

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from pathlib import Path
from Qt import QtWidgets

from typing import TYPE_CHECKING

from pipe.db import DBInterface
from pipe.glui.dialogs import (
    FilteredListDialog,
    MessageDialog,
    MessageDialogCustomButtons,
)
from pipe.struct.db import SGEntity, Shot
from shared.util import get_production_path

if TYPE_CHECKING:
    import typing
    from types import ModuleType
    from typing import Any
    from typing_extensions import Self

    KT = typing.TypeVar("KT")
    VT = typing.TypeVar("VT")


log = logging.getLogger(__name__)


class dotdict(dict):
    """dot notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


class FileManager(metaclass=ABCMeta):
    _conn: DBInterface
    _entity_type: type[SGEntity]
    _main_window: QtWidgets.QWidget | None

    def __init__(
        self,
        conn: DBInterface,
        entity_type: type[SGEntity],
        main_window: QtWidgets.QWidget | None,
    ) -> None:
        self._conn = conn
        self._entity_type = entity_type
        self._main_window = main_window

    @staticmethod
    @abstractmethod
    def _check_unsaved_changes() -> bool:
        pass

    @staticmethod
    @abstractmethod
    def _generate_filename(entity: SGEntity) -> str:
        pass

    @staticmethod
    def _get_subpath() -> str:
        return ""

    @staticmethod
    @abstractmethod
    def _open_file(path: Path) -> None:
        """Opens the file into the current session"""
        pass

    @abstractmethod
    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        """Setup a new file in the current session"""
        pass

    def _post_open_file(self, entity: SGEntity) -> None:
        """Execute additional code after opening or creating a scene"""
        pass

    def _prompt_create_if_not_exist(self, path: Path) -> bool:
        """Returns True if safe to proceed, False otherwise"""
        if not path.exists():
            prompt_create = MessageDialogCustomButtons(
                self._main_window,
                f"{str(path)} does not exist. Create?",
                has_cancel_button=True,
                ok_name="Create Folder",
                cancel_name="Cancel",
            )
            if not bool(prompt_create.exec_()):
                return False
            path.mkdir(mode=0o770, parents=True)
        return True

    def open_file(self) -> None:
        if not self._check_unsaved_changes():
            return

        entity_names = self._conn.get_entity_code_list(
            self._entity_type, sorted=True, child_mode=DBInterface.ChildQueryMode.ROOTS
        )
        open_file_dialog = FilteredListDialog(
            self._main_window,
            entity_names,
            f"Open {self._entity_type.__name__} File",
            f"Select the {self._entity_type.__name__} file that you'd like to open.",
            accept_button_name="Open",
        )

        if not open_file_dialog.exec_():
            log.debug("error intializing dialog")
            return

        response = open_file_dialog.get_selected_item()
        if not response:
            return

        entity = self._conn.get_entity_by_code(self._entity_type, response)

        try:
            assert entity is not None
            assert entity.path is not None
        except AssertionError:
            MessageDialog(
                self._main_window,
                f"The {self._entity_type.__name__.lower()} you are trying to "
                "load does not have a path set in ShotGrid.",
                "Error: No path set",
            ).exec_()
            return

        entity_path = get_production_path() / entity.path / self._get_subpath()
        if not self._prompt_create_if_not_exist(entity_path):
            return

        file_path = entity_path / self._generate_filename(entity)
        if file_path.is_file():
            self._open_file(file_path)
        else:
            self._setup_file(file_path, entity)

        self._post_open_file(entity)


@dataclass(frozen=True)
class FFMpegPreset:
    ext: str
    out_kwargs: dict[str, Any]

    def __hash__(self):
        return hash(frozenset(self.out_kwargs.items()))


class Playblaster(metaclass=ABCMeta):
    """Parent class for creating playblasters. Uses FFmpeg to encode videos"""

    _conn: DBInterface
    _shot: Shot
    _in_context: bool

    FR = 24

    class PRESET(FFMpegPreset, Enum):
        EDIT_SQ = (
            "mov",
            {
                "vcodec": "dnxhd",
                "pix_fmt": "yuv422p",
                "vprofile": "dnxhr_sq",
                # this number comes from Avid's table in the DNxHD whitepaper
                "video_bitrate": "124M",
            },
        )
        EDIT_HQX = (
            "mov",
            {
                "vcodec": "dnxhd",
                "pix_fmt": "yuv422p10le",
                "vprofile": "dnxhr_hqx",
                "video_bitrate": "188M",
            },
        )
        WEB = (
            "mp4",
            {
                "vcodec": "libx264",
                "preset": "veryslow",
                "tune": "animation",
                "crf": 20,
            },
        )

    def __init__(self, conn: DBInterface) -> None:
        self._conn = conn

    @abstractmethod
    def _write_images(self, path: str) -> None:
        pass

    def __enter__(self) -> Self:
        self._in_context = True
        return self

    def __call__(self, shot: Shot, *args):
        self._shot = shot
        return self

    def __exit__(self, *args) -> None:
        self._in_context = False

    def _do_playblast(
        self,
        out_paths: dict[PRESET, list[Path | str]] | None = None,
        tail: int = 0,
    ) -> None:
        if not self._in_context:
            raise RuntimeError("_do_playblast not called from within context self")

        if not out_paths:
            out_paths = {}

        tempdir = Path(os.getenv("TMPDIR", os.getenv("TEMP", "tmp"))).resolve()

        FILENAME = "lnd_pb_temp." + self._shot.code

        # remove any old playblasts
        for p in tempdir.glob(FILENAME + "*"):
            p.unlink()

        # do the playblast
        self._write_images(str(tempdir / FILENAME))

        # use ffmpeg to encode the video
        start_frame = int(self._shot.cut_in) - tail
        images = ffmpeg.input(
            str(tempdir / FILENAME) + ".%04d.png",
            start_number=start_frame,
            r=self.FR,
            # precisely define input colorspace
            colorspace="bt709",
            color_trc="iec61966-2-1",
        )
        for preset, paths in out_paths.items():
            out_filename = str(tempdir / FILENAME) + "." + preset.ext
            ffmpeg.output(
                images,
                out_filename,
                **preset.out_kwargs,
                timecode="00:00:{:02}:{:02}".format(
                    start_frame // self.FR,
                    start_frame % self.FR,
                ),
                r=self.FR,
            ).overwrite_output().run()

            # copy video out of tempdir
            for path in (Path(str(p) + "." + preset.ext) for p in paths):
                if not path.parent.exists():
                    path.parent.mkdir(mode=0o770, parents=True)
                shutil.copyfile(out_filename, path)

        # clean up if not in debug mode
        if not log.isEnabledFor(logging.DEBUG):
            for p in tempdir.glob(FILENAME + "*"):
                p.unlink()

    @abstractmethod
    def playblast(self) -> None:
        """Function to be called by the user to trigger a playblast.
        This should call `_do_playblast` from within a `with self(...)`
        block.
        Looks something like:
            >>> def playblast(self) -> None:
            >>>     with self(shot):
            >>>         super()._do_playblast([filepath])
        """
        pass


def checkbox_callback_helper(
    checkbox: QtWidgets.QCheckBox, widget: QtWidgets.QWidget
) -> typing.Callable[[], None]:
    """Helper function to generate a callback to enable/disable a widget when
    a checkbox is checked"""

    def inner() -> None:
        widget.setEnabled(checkbox.isChecked())

    return inner


def dict_index(d: dict[KT, VT], v: VT) -> KT:
    """List index function for dicts"""
    return list(d.keys())[list(d.values()).index(v)]


def log_errors(fun):
    @wraps(fun)
    def wrap(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception as e:
            log.error(e, exc_info=True)
            raise

    return wrap


def reload_pipe(extra_modules: typing.Sequence[ModuleType] | None = None) -> None:
    """Reload all pipe python modules"""
    if extra_modules is None:
        extra_modules = []
    else:
        extra_modules = list(extra_modules)

    pipe_modules = [
        module
        for name, module in sys.modules.items()
        if (name.startswith("pipe") or name.startswith("shared"))
        and ("shotgun_api3" not in name)
        or (name == "env")
    ] + extra_modules

    for module in pipe_modules:
        if (name := module.__name__) in sys.modules:
            log.info(f"Unloading {name}")
            del sys.modules[name]


try:

    def silent_startupinfo() -> subprocess.STARTUPINFO | None:  # type: ignore[name-defined]
        """Returns a Windows-only object to make sure tasks launched through
        subprocess don't open a cmd window.

        Returns:
            subprocess.STARTUPINFO -- the properly configured object if we are on
                                    Windows, otherwise None
        """
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        return startupinfo
except Exception:

    def silent_startupinfo() -> typing.Any | None:
        pass
