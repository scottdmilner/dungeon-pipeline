from os import getenv

import hou

# update embedded JOB variable
JOB = getenv("JOB") or ""
hou.putenv("JOB", JOB)
# mark any node referencing $JOB as dirty
hou.hscript("varchange")
