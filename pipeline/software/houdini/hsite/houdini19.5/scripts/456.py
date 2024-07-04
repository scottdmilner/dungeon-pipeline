import hou

from pipe.util import get_production_path, resolve_mapped_path

# create embedded $ASSET variable if needed
hip_path = resolve_mapped_path(hou.hscriptStringExpression("$HIP"))
if any(get_production_path() / p in hip_path.parents for p in ["asset", "character"]):
    if not hou.contextOption("ASSET"):
        hou.setContextOption("ASSET", hip_path.name)

# mark any node referencing above vars as dirty
hou.hscript("varchange")
