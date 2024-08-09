import hou
import os

from shared.util import get_production_path, resolve_mapped_path

# create embedded $ASSET variable if needed
hip_path = resolve_mapped_path(hou.hscriptStringExpression("$HIP"))
if any(get_production_path() / p in hip_path.parents for p in ["asset", "character"]):
    if not hou.contextOption("ASSET"):
        hou.setContextOption("ASSET", hip_path.name)

# ensure ASSETGALLERY_DATA_SOURCE is correct
hou.hscript(
    f"setenv ASSETGALLERY_DATA_SOURCE='{os.getenv('HOUDINI_ASSETGALLERY_DATA_SOURCE')}'"
)

# mark any node referencing above vars as dirty
hou.hscript("varchange")
