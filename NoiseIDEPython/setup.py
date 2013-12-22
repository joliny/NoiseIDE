import sys

from cx_Freeze import setup, Executable 

base = None
if sys.platform == "win32":
    base = "Win32GUI"

includefiles = ['dark.color.yaml', 
                'white.color.yaml', 
                'noiseide_copy.bat', 
                'rev.cfg', 
                'noiseide.template.yaml', 
                'data/images',
                'data/erlang/modules/apps/noiseide/include',
                'data/erlang/modules/apps/noiseide/ebin',
                'data/erlang/modules/apps/noiseide/src/noiseide_api.erl',
                'data/erlang/templates',
				'data/erlang/ide_cmds.yaml'
				]
    
build_exe_options = {'include_files':includefiles, 'build_exe' : 'noiseide'}
    
setup(
        name = "NoiseIDE",
        version = "0.1",
        description = "NoiseIDE",
        options = {"build_exe": build_exe_options},
        executables = [Executable("idn_mainframe.py",
            base = base,
            targetName = "NoiseIDE.exe",
            icon = "data/images/icon.ico")
        ])

