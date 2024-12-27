export SCRIPTDIR=$(pwd)
echo "installing to $SCRIPTDIR"
echo <<EOF
# Run the following to install dependencies on debian-based systems
sudo apt-get update
sudo apt-get install -y \
    wget \
    libglu1-mesa-dev \
    libgl1-mesa-dev \
    libxmu-dev \
    libxi-dev \
    build-essential \
    cmake \
    libfreetype6-dev \
    tk-dev \
    python3-dev \
    rapidjson-dev \
    python3 \
    git \
    python3-pip \
    libpcre2-dev
# Move the EOF down as needed if you have to rerun the script to avoid repeatedly downloading stuff or up to install dependencies
EOF
mkdir -p filesneeded

cd filesneeded
curl -L -C - http://prdownloads.sourceforge.net/swig/swig-4.2.1.tar.gz -o swig.tar.gz
curl -L -C - https://github.com/Open-Cascade-SAS/OCCT/archive/refs/tags/V7_8_1.tar.gz -o OCCT.tar.gz
curl -L -C - https://github.com/tpaviot/pythonocc-core/archive/refs/tags/7.8.1.1.tar.gz -o pythonocc-core.tar.gz
curl -L -C - https://mirrors.ocf.berkeley.edu/blender/release/Blender4.3/blender-4.3.2-linux-x64.tar.xz -o blender-app.tar.xz
cd ..

mkdir -p src
cd src
# Uncomment these and comment the corresponding 
#git clone --depth=1 https://github.com/swig/swig
#git clone --depth=1 https://github.com/Open-Cascade-SAS/OCCT
#git clone --depth=1 https://github.com/blender/blender
#git clone --depth=1 https://github.com/tpaviot/pythonocc-core

tar -zxvf ../filesneeded/swig.tar.gz && mv swig-4.2.1 swig
tar -zxvf ../filesneeded/OCCT.tar.gz && mv OCCT-7_8_1 OCCT
tar -zxvf ../filesneeded/pythonocc-core.tar.gz && mv pythonocc-core-7.8.1.1 pythonocc-core

cd $SCRIPTDIR
mkdir -p src
cd src/swig
./autogen.sh
cd $SCRIPTDIR
mkdir -p swig-build
cd swig-build
$SCRIPTDIR/src/swig/configure --prefix=$SCRIPTDIR/lib/swig
make -j$(nproc)
make install

cd ..
cd $SCRIPTDIR
mkdir -p occt-build
cd occt-build
cmake -DINSTALL_DIR=$SCRIPTDIR/lib/occt \
      -DBUILD_RELEASE_DISABLE_EXCEPTIONS=OFF \
      $SCRIPTDIR/src/OCCT
make -j$(nproc)
make install

cd ..
mkdir -p pythonocc-build
cd pythonocc-build
cmake \
    -DOCCT_INCLUDE_DIR=$SCRIPTDIR/lib/occt/include/opencascade \
    -DOCCT_LIBRARY_DIR=$SCRIPTDIR/lib/occt/lib \
    -DCMAKE_BUILD_TYPE=Release \
    -DPYTHONOCC_INSTALL_DIRECTORY=$SCRIPTDIR/lib/pythonocc \
    -DPYTHONOCC_MESHDS_NUMPY=ON \
    $SCRIPTDIR/src/pythonocc-core
make -j$(nproc) && make install

cd $SCRIPTDIR
mkdir -p app
cd app
tar -Jxvf ../filesneeded/blender-app.tar.xz && mv blender-4.3.2-linux-x64 blender-app
cd ..

ln -s $SCRIPTDIR/lib/pythonocc/ $SCRIPTDIR/app/blender-app/4.3/python/lib/python3.11/OCC
echo "LD_LIBRARY_PATH=$SCRIPTDIR/lib/occt/lib/ ./app/blender-app/blender">./blender.sh
chmod +x blender.sh
echo "to run, use ./blender.sh"
echo "Otherwise, use this to add to your ldconfig:"
echo "sudo echo $SCRIPTDIR/lib/occt/lib/>ld.so.conf.d/occt.conf && sudo ldconfig"
echo "(pythonocc-core is just a python wrapper for OCCT, so it needs access to the OCCT libs.)"


cat << EOF > addoninstaller.py
import bpy
bpy.ops.preferences.addon_install(filepath="$SCRIPTDIR/blenderocc.py")
bpy.ops.preferences.addon_enable(module='blenderocc')
EOF
echo "to install the blender occ addon use ./addoninstaller.py"
