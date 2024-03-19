# `env.py` Contents

In this folder the pipeline expects a file named `env.py` with the following 
defined variables to properly function. Note that they will need to be defined 
conditionally based off of operating system for functionality on multiple 
operating systems.

```python
import platform

from dataclasses import dataclass
from pathlib import Path

production_path: Path  # absolute path to this repository (ie /groups/project/dungeon-pipeline)

@dataclass
class Executables:
    hfs: Path                 # absolute path to the Houdini HFS folder (ie /opt/hfs19.5.640)
    houdini: Path             # absolute path to the Houdini binary
    hython: Path              # absolute path to the Hython binary
    mayabin: Path             # absolute path to the Maya bin folder (ie /usr/autodesk/maya2024/bin)
    maya: Path                # absolute path to the Maya executable
    mayapy: Path              # absolute path to the mayapy executable
    nukedir: Path             # absolute path to the Nuke installation dir (ie /opt/Nuke14.0v5)
    nuke: Path                # absolute path to the Nuke executable
    nuke_python: Path         # absolute path to the Nuke python executable
    oiiotool: Path            # absolute path to the oiiotool executable (such as the one bundled with Houdini)
    substance_designer: Path  # absolute path to the Substance Designer executable
    substance_painter: Path   # absolute path to the Substance Painter executable
    txmake: Path              # absolute path to the txmake execuatable (such as the one bundled with RenderMan)


@dataclass
class SG_Config:
    project_id: int
    # DO NOT SHARE/COMMIT THE sg_key!!! IT'S EQUIVALENT TO AN ADMIN PW!!!
    sg_key: str
    sg_script: str
    sg_server: str

```
