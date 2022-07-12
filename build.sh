set -e

mkdir -p build/Release
(
    cd build/Release
    cmake ../.. -DCMAKE_BUILD_TYPE=Release
    make -j8 all
)
