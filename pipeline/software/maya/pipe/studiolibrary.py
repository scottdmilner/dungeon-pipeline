import sys
import os

def run():
    shrineflow_path_prefix = ""
    file_delin = ""
    if os.name == "nt":
        # we're in windows
        shrineflow_path_prefix = 'G:\\shrineflow'
        file_delin = '\\'
    else:
        shrineflow_path_prefix = '/groups/shrineflow'
        file_delin = '/'

    studio_library_path = f'{shrineflow_path_prefix}{file_delin}pipeline{file_delin}pipeline{file_delin}lib{file_delin}studiolibrary'
    if studio_library_path not in sys.path:
        sys.path.insert(0, studio_library_path)
    import studiolibrary

    assets_path = f'{shrineflow_path_prefix}{file_delin}working_files{file_delin}Animation{file_delin}StudioLibrary_files'
    studiolibrary.setLibraries([
        {'name': 'Pose Library', 'path': assets_path, 'default': True, 'theme': {'accentColor': 'rgb(3,252,211)',},},
        ])
    studiolibrary.main()

