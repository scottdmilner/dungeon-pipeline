import logging
import os
import re
import subprocess

from math import ceil, floor, sqrt
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Type, TypeVar

from .util import silent_startupinfo

from env import Executables

RT = TypeVar("RT")  # return type

log = logging.getLogger(__name__)


class TexConverter:
    tex_path: Path
    preview_path: Path
    imgs_by_tex_set: Iterable[List[str]]

    def __init__(
        self,
        tex_path: Path,
        preview_path: Path,
        imgs_by_tex_set: Iterable[List[str]],
    ) -> None:
        self.tex_path = tex_path
        self.preview_path = preview_path
        self.imgs_by_tex_set = imgs_by_tex_set

    def convert_tex(self) -> bool:
        """Convert all .png textures in the most recent export to .tex"""

        assert self.tex_path is not None

        @self._debug_out
        def tex_cmd(img: Path) -> list[str]:
            # currently using oiiotool so txmake doesn't freak out at the color space
            # TODO: switch back to txmake for color in R26
            # fmt: off
            return [
                str(Executables.oiiotool),
                str(img),
                "--compression", "lossless",
                "--planarconfig", "separate",
                "-otex:fileformatname=tx:wrap=clamp:resize=1:prman_options=1",
                f"{str(self.tex_path / img.stem)}.tex",
            ]
            # fmt: on

        @self._debug_out
        def b2r_cmd(img: Path) -> list[str]:
            # fmt: off
            return [
                str(Executables.txmake),
                "-resize", "round-",
                "-mode", "periodic",
                "-filter", "box",
                "-mipfilter", "box",
                "-bumprough", "2", "0", "1", "0", "0", "1",
                "-newer",
                str(img),
                f"{str(self.tex_path / img.stem)}.b2r",
            ]
            # fmt: on

        cmdlines: List[List[str]] = []
        # procs: List[subprocess.Popen] = []
        for imgs in self.imgs_by_tex_set:
            log.debug(imgs)
            for img in (Path(i) for i in imgs):
                if img.suffix == ".png":
                    log.debug(f"        {str(img)}")
                    cmdlines.append((b2r_cmd if "Normal" in img.name else tex_cmd)(img))

        self._wait_and_print_cmds(cmdlines)

        return True

    def convert_previewsurface(self) -> bool:
        """Compile all .jpeg textures in the most recent export to UDIM-less tiles"""

        assert self.preview_path is not None

        @self._debug_out
        def jpeg_cmd(root: Path, imgs: List[str]) -> list[str]:
            img_info = subprocess.check_output(
                [
                    str(Executables.oiiotool),
                    "--info",
                    imgs[0],
                ],
                startupinfo=silent_startupinfo(),
            ).decode("utf-8")
            img_dims = re.search(r"^.* : +(\d+) +x +(\d+), .*$", img_info)

            assert img_dims is not None
            dimx, dimy = img_dims.group(1, 2)

            img_name = re.search(r"^(.*_)(.+)$", root.name)
            assert img_name is not None
            name_base, color_space = img_name.group(1, 2)

            count = len(imgs)
            grid_height = int(floor(sqrt(count)))
            grid_base = int(grid_height + ceil(count / grid_height - grid_height))

            # fmt: off
            return [
                str(Executables.oiiotool), 
                *imgs,
                "--mosaic", f"{grid_base}x{grid_height}",
                "--resize", f"{dimx}x{dimy}",
                *(["--colorconvert", "ACEScg", "srgb_tx"] if color_space == "ACEScg" else []),
                "-o", f"{str(self.preview_path / name_base)}{'sRGB' if color_space == 'ACEScg' else 'Linear'}.jpeg",
            ]
            # fmt: on

        # construct list of grouped images
        img_list: Dict[str, List[str]] = {}
        for imgs in self.imgs_by_tex_set:
            for img in imgs:
                if img.endswith(".jpeg"):
                    key_search = re.search(r"^(.*)\.\d{4}\.jpeg$", img)
                    if not key_search:  # no UDIMs
                        key_search = re.search(r"^(.*)\.jpeg$", img)
                        assert key_search is not None

                    key = key_search.group(1)
                    if key not in img_list:
                        img_list[key] = []
                    img_list[key].append(img)

        self._wait_and_print_cmds(
            [jpeg_cmd(Path(root), sorted(imgs)) for root, imgs in img_list.items()]
        )

        return True

    def _wait_and_print_cmds(self, cmds: List[List[str]]) -> None:
        """Wait for list of processes to finish and print them to the debug log"""
        BATCH_SIZE = 12

        batched_cmds = (
            cmds[i : i + BATCH_SIZE] for i in range(0, len(cmds), BATCH_SIZE)
        )

        while batch := next(batched_cmds, None):
            procs: List[subprocess.Popen] = []
            for cmd in batch:
                procs.append(
                    subprocess.Popen(
                        cmd,
                        env=os.environ,
                        startupinfo=silent_startupinfo(),
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                    )
                )

            for p in procs:
                p.wait()
                if log.isEnabledFor(logging.DEBUG):
                    if p.stdout and (stdout := p.stdout.read().decode("utf-8")):
                        log.debug(stdout)
                    if p.stderr and (stderr := p.stderr.read().decode("utf-8")):
                        log.debug(stderr)

    def _debug_out(self, func: Callable[..., RT]) -> Callable[..., RT]:
        """Decorator to debug print the output of the function"""

        def inner(self: Type[TexConverter], *args, **kwargs) -> RT:
            ret = func(self, *args, **kwargs)
            log.debug(ret)
            return ret

        return inner
