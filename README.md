pythonOCC + Blender Installer
===

This bash script is based on https://github.com/tpaviot/pythonocc-core/blob/master/INSTALL.md

Usage: 
./installer.sh

Assumes Linux x64. Tested with PopOS (ubuntu-based).

Installs
1. swig 4.2.1
2. OCCT 7.8.1
3. pythonocc-core 7.8.1.1
4. blender (binary) 4.3.2

Creates a file called blender.sh which calls the executable with LD_LIBRARY_PATH pointing to occt libs.
You can also add it to your ld sources and use ldconfig, or install the occt libs somewhere standard.
Note that the pythonocc-core folder gets linked as blender-app/4.3/python/lib/python3.11/OCC
You can move it somewhere more standard, this is just to let you use the blender binary (which includes its own python).

BlenderOCC Blender Addon
===

This is a blender addon that lets you define customizable buttons. It consists of 2 files:

- blenderocc.py (addon)
- opencascade_commands.py (user-definable commands)

For rapid development of the addon, after installing it in blender, you can remove the file from the addons folder and replace it with a symbolic link. 
To make it active, disable and reenable the addon.

