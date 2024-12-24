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
Note that the pythonocc-core folder gets linked as blender-app/4.3/python/lib/python3.11/OCC
