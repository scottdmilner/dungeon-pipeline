import site
from pathlib import Path

ROOT = Path(__file__).parents[1]
venv_version: str

with open(ROOT / ".venv/pyvenv.cfg", "r") as cfg:
    for line in cfg:
        if not line.startswith("version_info"):
            continue
        version_str = line.split(" = ")[1]
        venv_version = "python" + ".".join(version_str.split(".", 2)[:2])
        break

SITEDIR = ROOT / ".venv/lib" / venv_version / "site-packages"
site.addsitedir(str(SITEDIR))
