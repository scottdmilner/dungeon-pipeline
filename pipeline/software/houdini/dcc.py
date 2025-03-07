from __future__ import annotations

import atexit
import filecmp
import logging
import os
import platform
import shutil
import sqlite3

from contextlib import closing, contextmanager, suppress
from filelock import FileLock
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing

from shared.util import get_production_path, resolve_mapped_path

from ..baseclass import DCC
from env import Executables

log = logging.getLogger(__name__)

_PROD_DB = str(get_production_path() / "asset/assetGallery.db")
_TMPDIR = Path(os.getenv("TMPDIR", os.getenv("TEMP", "tmp"))).resolve() / str(
    os.getpid()
)
_TMPDIR.mkdir(0o755, exist_ok=True)


class HoudiniDCC(DCC):
    """Houdini DCC class"""

    _assetdb_path: str
    _orig_assetdb_path: str

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        self._assetdb_path = str(_TMPDIR / "assetGallery.db")
        self._orig_assetdb_path = str(_TMPDIR / "assetGallery_orig.db")

        env_vars: typing.Mapping[str, int | str | None] | None
        env_vars = {
            "DCC": str(this_path.parent.name),
            # Asset Gallery sqlite db (set in 456.py)
            "HOUDINI_ASSETGALLERY_DATA_SOURCE": (
                self._assetdb_path
                if platform.system() == "Linux"
                else self._assetdb_path.replace("\\", "/")
            ),
            # Backup directory
            "HOUDINI_BACKUP_DIR": "./.backup",
            # Dump the core on crash to help debugging
            "HOUDINI_COREDUMP": 1,
            # Compiled Houdini files debug
            "HOUDINI_DSO_ERROR": 2 if log.isEnabledFor(logging.DEBUG) else None,
            # Max backup files
            "HOUDINI_MAX_BACKUP_FILES": 20,
            # Prevent user envs from overriding existing values
            "HOUDINI_NO_ENV_FILE_OVERRIDES": 1,
            # Disable start page splash
            "HOUDINI_NO_START_PAGE_SPLASH": 1,
            # Configure additional HDA locations outside of the pipeline
            "HOUDINI_OTLSCAN_PATH": os.pathsep.join(
                [
                    str(p)
                    for p in resolve_mapped_path(
                        get_production_path() / "hda"
                    ).iterdir()
                ]
                + ["&"]
            ),
            # Package loading debug logging
            "HOUDINI_PACKAGE_VERBOSE": 1 if log.isEnabledFor(logging.DEBUG) else None,
            # Houdini Path
            "HOUDINI_PATH": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    "&",
                ]
            ),
            # Splash file
            "HOUDINI_SPLASH_FILE": str(pipe_path / "lib/splash/dunginisplash19.5.png"),
            # Project-specific preference overrides
            "HSITE": str(resolve_mapped_path(this_path.parent / "hsite")),
            # Job directory
            "JOB": str(resolve_mapped_path(get_production_path())),
            # Ensure LD_LIBRARY_PATH is unset to allow nesting pipe instances
            "LD_LIBRARY_PATH": None,
            # Manually set LD_LIBRARY_PATH to integrated Houdini libraries (for Axiom)
            # "LD_LIBRARY_PATH": str(Executables.hfs / "dsolib")
            # if platform.system() == "Linux"
            # else None,
            # Set project OCIO config
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            # Pass log level defined on commandline
            "PIPE_LOG_LEVEL": log.getEffectiveLevel(),
            "PIPE_PATH": str(pipe_path),
            # Configure Asset Resolver
            "PXR_AR_DEFAULT_SEARCH_PATH": os.pathsep.join(
                [
                    str(get_production_path()),
                ]
            ),
            # USD Plugins
            "PXR_PLUGINPATH_NAME": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    os.environ.get("PXR_PLUGINPATH_NAME", ""),
                ]
            ),
            # Add pipe modules to Python path
            "PYTHONPATH": os.pathsep.join(
                [
                    str(resolve_mapped_path(pipe_path)),
                    # Add $RMANTREE/bin to PYTHONPATH for the Tractor PDG scheduler
                    # os.environ.get("RMANTREE", "") + "/bin",
                    str(
                        get_production_path()
                        / (
                            "opt/pixar/RenderManProServer-26.3"
                            if platform.system() == "Linux"
                            else "PFiles/Pixar/RenderManProServer-26.3"
                        )
                    ),
                ]
            ),
            # RenderMan color config json file
            "RMAN_COLOR_CONFIG_DIR": str(pipe_path / "lib/ocio/love-v01"),
            # Explicitly set Tractor location
            "TRACTOR_ENGINE": "tractor-engine.cs.byu.edu:443",
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(Executables.hython)
        else:
            launch_command = str(Executables.houdini)

        if is_python_shell:
            launch_args = extra_args or []
        else:
            launch_args = ["-foreground", *(extra_args or [])]

        super().__init__(
            launch_command, launch_args, env_vars, lambda: self._set_up_asset_gallery()
        )

    def _set_up_asset_gallery(self) -> None:
        for f in _TMPDIR.glob("assetGallery.*"):
            f.unlink()

        shutil.copy(_PROD_DB, self._assetdb_path)
        shutil.copy(self._assetdb_path, self._orig_assetdb_path)

        atexit.register(lambda: self._merge_asset_gallery_changes())

    def _merge_asset_gallery_changes(self) -> None:
        # test if the gallery has changed
        filecmp.clear_cache()
        if filecmp.cmp(self._orig_assetdb_path, self._assetdb_path, shallow=False):
            return

        print("Merging asset gallery changes")

        lock_path = _PROD_DB + ".lock"

        lock = FileLock(lock_path, mode=0o775)

        # merge local modifications into the prod database
        with lock.acquire(timeout=40), closing(sqlite3.connect(_PROD_DB)) as conn:
            cur = conn.cursor()
            with (
                attach_db(cur, self._assetdb_path) as MODIFIED,
                attach_db(cur, self._orig_assetdb_path) as ORIGINAL,
                conn,
            ):
                cur.execute("BEGIN")
                table_query = (
                    f"SELECT * from {MODIFIED}.sqlite_master WHERE type='table'"
                )
                for table in (nm for tp, nm, *_ in cur.execute(table_query)):
                    # find the insertion point we left off at
                    cur.execute(f"SELECT MAX(id) FROM {ORIGINAL}.{table}")
                    last_id = cur.fetchone()[0]

                    if isinstance(last_id, int):  # if there are already entries
                        # update any changes to existing entries
                        cur.execute(
                            f"INSERT OR REPLACE INTO {table} "
                            f"SELECT * FROM {MODIFIED}.{table} WHERE id <= {last_id} "
                            + (
                                "AND marked_for_deletion = 0"
                                if table == "items"
                                else ""
                            )
                        )
                        # find all the non-id columns
                        cur.execute(f"SELECT * FROM {ORIGINAL}.{table}")
                        columns_no_id = [d[0] for d in cur.description if d[0] != "id"]
                        columns_str = ", ".join(columns_no_id)
                        # insert any new entries, will generate a new ID
                        cur.execute(
                            f"INSERT INTO {table} ({columns_str}) "
                            f"SELECT {columns_str} FROM {MODIFIED}.{table} WHERE id > {last_id} "
                            + (
                                "AND marked_for_deletion = 0"
                                if table == "items"
                                else ""
                            )
                        )
                    else:
                        # insert any new entries
                        cur.execute(
                            f"INSERT INTO {table} "
                            f"SELECT * FROM {MODIFIED}.{table} "
                            + (
                                "WHERE marked_for_deletion = 0"
                                if table == "items"
                                else ""
                            )
                        )

        # clean up
        for f in _TMPDIR.glob("assetGallery.*"):
            f.unlink()
        with suppress(OSError):
            _TMPDIR.rmdir()


@contextmanager
def attach_db(cur: sqlite3.Cursor, path: str):
    name = "".join(c for c in path if c.isalpha())
    cur.execute(f"ATTACH DATABASE '{path}' AS {name}")

    try:
        yield name
    finally:
        cur.execute(f"DETACH DATABASE {name}")
