from __future__ import annotations

import logging
import os
import re
import subprocess
import time

from math import ceil, floor, log2, sqrt
from pathlib import Path
from typing import cast, Callable, Dict, Iterable, Sequence, TypeVar

from pipe.util import silent_startupinfo

from env import Executables

RT = TypeVar("RT")  # return type

log = logging.getLogger(__name__)


class TexConversionError(ChildProcessError):
    pass


class TexConverter:
    tex_path: Path
    preview_path: Path
    imgs_by_tex_set: Iterable[list[str]]

    def __init__(
        self,
        tex_path: Path,
        preview_path: Path,
        imgs_by_tex_set: Iterable[list[str]],
    ) -> None:
        self.tex_path = tex_path
        self.preview_path = preview_path
        self.imgs_by_tex_set = imgs_by_tex_set

    def convert_tex(self) -> list[Path]:
        """Convert all .png textures in the most recent export to .tex"""

        assert self.tex_path is not None

        @self._debug_out
        def tex_cmd(img: str, is_color: bool = False) -> list[str]:
            # currently using oiiotool so txmake doesn't freak out at the color space
            # TODO: switch back to txmake for color in R26
            # fmt: off
            return [
                str(Executables.oiiotool),
                img,
                *(
                    [
                        "--colorconvert", "ACEScg", "srgb-ap1",
                        "-d", "uint8", 
                        "--dither",
                    ] if is_color else []
                ),
                "--compression", "lzw" if is_color else "lossless",
                "--planarconfig", "separate",
                "-otex:fileformatname=tx:wrap=clamp:resize=1:prman_options=1",
                f"{str(self.tex_path / Path(img).stem.replace('ACEScg', 'srgb-ap1'))}.tex",
            ]
            # fmt: on

        @self._debug_out
        def b2r_cmd(img: str) -> list[str]:
            # fmt: off
            return [
                str(Executables.txmake),
                "-resize", "round-",
                "-mode", "periodic",
                "-filter", "box",
                "-mipfilter", "box",
                "-bumprough", "2", "0", "0", "0", "0", "1",
                "-newer",
                img,
                f"{str(self.tex_path / Path(img).stem)}.b2r",
            ]
            # fmt: on

        @self._debug_out
        def norm2height(img: str) -> list[str]:
            """Convert normal map to height map
            This is necessary because if we run b2r conversion directly on a
            normal map, reversed UV tiles will have incorrect normals.
            We can't run b2r conversion directly on the height map from
            Substance because that doesn't include normal painting or
            stickers. Thus, the remaining option is to convert the Normal map
            from Substance back into a height map."""
            img_dims = [str(int(log2(int(d)))) for d in self._img_dims(img)]
            # fmt: off
            return [
                str(Executables.sbsrender),
                "render",
                "--engine", "d3d11pc",
                "--exr-format-compression", "zip",
                "--output-bit-depth", "16f",
                "--output-format", "exr",
                "--input", f"{os.getenv('PIPE_PATH', '')}/lib/sbs/normal2height.sbsar",
                "--set-entry", f"input@{img}",
                "--set-value", f"$outputsize@{','.join(img_dims)}",
                "--output-path", str(Path(img).parent),
                "--output-name", img.replace(".pre-b2r", ""),
            ]
            # fmt: on

        pre_cmdlines: list[list[str]] = []
        cmdlines: list[list[str]] = []
        for imgs in self.imgs_by_tex_set:
            log.debug(imgs)
            for img in imgs:
                if img.endswith(".jpeg"):
                    continue
                log.debug(f"        {img}")
                if "pre-b2r" in img:
                    pre_cmdlines.append(norm2height(img))
                    cmdlines.append(b2r_cmd(img.replace(".pre-b2r", "")))
                else:
                    cmdlines.append(tex_cmd(img, ("Color" in img or "Emissive" in img)))

        self._wait_and_check_cmds(pre_cmdlines, skip_check=True)
        finished_imgs = self._wait_and_check_cmds(cmdlines)

        if len(finished_imgs) != len(cmdlines):
            raise TexConversionError("Not all png textures were converted")

        return finished_imgs

    def convert_previewsurface(self) -> list[Path]:
        """Compile all .jpeg textures in the most recent export to UDIM-less tiles"""

        assert self.preview_path is not None

        @self._debug_out
        def jpeg_cmd(root: Path, imgs: Sequence[str]) -> list[str]:
            dimx, dimy = self._img_dims(imgs[0])

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
                "-o", f"{str(self.preview_path / name_base)}{'sRGB' if color_space == 'sRGB-Texture' else 'Linear'}.jpeg",
            ]
            # fmt: on

        # construct list of grouped images
        img_list: Dict[str, list[str]] = {}
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

        cmdlines = [
            jpeg_cmd(Path(root), sorted(imgs)) for root, imgs in img_list.items()
        ]

        finished_imgs = self._wait_and_check_cmds(cmdlines)

        if len(finished_imgs) != len(cmdlines):
            raise TexConversionError("Not all jpeg textures were converted")

        return finished_imgs

    @staticmethod
    def _img_dims(img: str) -> tuple[str, str]:
        img_info = subprocess.check_output(
            [
                str(Executables.oiiotool),
                "--info",
                img,
            ],
            startupinfo=silent_startupinfo(),
        ).decode("utf-8")
        img_dims = re.search(r"^.* : +(\d+) +x +(\d+), .*$", img_info)

        assert img_dims is not None
        matches = img_dims.group(1, 2)
        return (matches[0], matches[1])

    @staticmethod
    def _wait_and_check_cmds(
        cmds: Sequence[list[str]], batch_size: int = 18, skip_check: bool = False
    ) -> list[Path]:
        """Wait for list of processes to finish and print them to the debug log"""

        batched_cmds = (
            cmds[i : i + batch_size] for i in range(0, len(cmds), batch_size)
        )

        finished_imgs: list[Path] = []

        while batch := next(batched_cmds, None):
            start_time = time.time()

            procs = [
                subprocess.Popen(
                    cmd,
                    env=os.environ,
                    startupinfo=silent_startupinfo(),
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                )
                for cmd in batch
            ]

            for p in procs:
                p.wait()
                if log.isEnabledFor(logging.DEBUG):
                    if p.stdout and (stdout := p.stdout.read().decode("utf-8")):
                        log.debug(stdout)
                    if p.stderr and (stderr := p.stderr.read().decode("utf-8")):
                        log.debug(stderr)

                if skip_check:
                    continue

                img = Path(cast(str, p.args[-1]))  # type: ignore[index]

                # check file has been touched recently
                if start_time < img.stat().st_mtime:
                    log.debug(f"Successfully converted {img}")
                    finished_imgs.append(img)

        return finished_imgs

    def _debug_out(self, func: Callable[..., RT]) -> Callable[..., RT]:
        """Decorator to debug print the output of the function"""

        def inner(self: TexConverter, *args, **kwargs) -> RT:
            ret = func(self, *args, **kwargs)
            log.debug(ret)
            return ret

        return inner
