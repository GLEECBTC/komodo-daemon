#!/usr/bin/env bash

delete_linux_depends=true
force_rebuild_containers=false

build_xenial=false
build_focal=true
build_windows=true
build_macos=false

# we should rebuild linux depends before build for different linux os
if [[ $build_xenial == true && $build_focal == true ]]; then
  delete_linux_depends=true
fi

download_and_check_macos_sdk() {
    url="https://download.decker.im/depends-sources/Xcode-13.2.1-13C100-extracted-SDK-with-libcxx-headers.tar.gz"
    output_file="Xcode-13.2.1-13C100-extracted-SDK-with-libcxx-headers.tar.gz"
    expected_checksum="3d200832a74bc7401160043c92f68b11fcedba2d01353b5ab204f9e6a65653d1"

    # Check if file exists
    if [[ -f "$output_file" ]]; then
        # Calculate checksum of the file
        actual_checksum=$(sha256sum "$output_file" 2>/dev/null | awk '{print $1}')
        if [[ -n $actual_checksum ]]; then
            # Compare checksums
            if [[ "$actual_checksum" == "$expected_checksum" ]]; then
                echo "MacOS SDK already exists and has the correct checksum. Skipping download."
                return
            fi
        fi
    fi

    echo "Downloading MacOS SDK ..."
    # Download the file
    curl -L -o "$output_file" "$url"

    # Calculate checksum of the downloaded file
    actual_checksum=$(sha256sum "$output_file" | awk '{print $1}')

    # Compare checksums
    if [[ "$actual_checksum" != "$expected_checksum" ]]; then
        echo "ERROR: Downloaded MacOS SDK has an invalid checksum."
        exit 1
    fi

    echo "MacOS SDK downloaded successfully and has a valid checksum."
}

delete_artefacts() {
    local release_name=$1

    if [[ "$release_name" = "windows" ]]; then
    ext=".exe"
    else
    ext=""
    fi

    mkdir -p ${WORKSPACE}/releases/${release_name}

    binaries=(
    "src/komodod"
    "src/wallet-utility"
    "src/komodo-tx"
    "src/komodo-cli"
    "src/komodo-test"
    )

    for binary in "${binaries[@]}"
    do
    rm -f "${WORKSPACE}/${binary}${ext}" || false
    done

    echo "Deleting artefacts from ${WORKSPACE} ..."
    # delete possible artefacts from previous build(s)
    find ${WORKSPACE}/src \( -name "*.a" -o -name "*.la" -o -name "*.o" -o -name "*.lo" -o -name "*.Plo" -o -name "*.Po" -o -name "*.lai" -o -name "*.dirstamp" \) -delete
    find ${WORKSPACE}/src \( -name "*.a" -o -name "*.la" -o -name "*.o" -o -name "*.lo" -o -name "*.Plo" -o -name "*.Po" -o -name "*.lai" -o -name "*.dirstamp" \) -path "*/.*" -delete
    rm -f ${WORKSPACE}/src/qt/moc_*.cpp # delete meta object code files, otherwise we will have MacOS after Linux/Windows build error
}

copy_release() {
    local release_name=$1

    if [[ "$release_name" = "windows" ]]; then
    ext=".exe"
    else
    ext=""
    fi

    mkdir -p ${WORKSPACE}/releases/${release_name}

    binaries=(
    "src/komodod"
    "src/wallet-utility"
    "src/komodo-tx"
    "src/komodo-cli"
    )

    for binary in "${binaries[@]}"
    do
        case $release_name in
        windows)
            docker run -it -u $(id -u ${USER}):$(id -g ${USER}) -v $PWD:$PWD -w $PWD -e HOME=/root ocean_focal_builder /bin/bash -c "/usr/bin/x86_64-w64-mingw32-strip ${WORKSPACE}/${binary}${ext}" || false
            ;;
        macos)
            docker run -it -u $(id -u ${USER}):$(id -g ${USER}) -v $PWD:$PWD -w $PWD -e HOME=/root ocean_focal_builder /bin/bash -c "${WORKSPACE}/depends/x86_64-apple-darwin/native/bin/x86_64-apple-darwin-strip ${WORKSPACE}/${binary}${ext}" || false
            ;;
        *)
            strip "${WORKSPACE}/${binary}${ext}" || false
            ;;
        esac
        cp -f "${WORKSPACE}/${binary}${ext}" "${WORKSPACE}/releases/${release_name}/"
    done

    case $release_name in
        xenial)
            echo "Performing actions for Xenial..."
            # mv "${WORKSPACE}/releases/${release_name}/komodo-qt" "${WORKSPACE}/releases/${release_name}/komodo-qt-linux"
            ;;
        focal)
            echo "Performing actions for Focal..."
            # mv "${WORKSPACE}/releases/${release_name}/komodo-qt" "${WORKSPACE}/releases/${release_name}/komodo-qt-linux"
            ;;
        windows)
            echo "Performing actions for Windows..."
            # mv "${WORKSPACE}/releases/${release_name}/komodo-qt${ext}" "${WORKSPACE}/releases/${release_name}/komodo-qt-windows${ext}"
            ;;
        macos)
            echo "Performing actions for MacOS..."
            docker run -it -u $(id -u ${USER}):$(id -g ${USER}) -v $PWD:$PWD -w $PWD -e HOME=/root ocean_focal_builder /bin/bash -c "make deploy" || false
            cp -f ${WORKSPACE}/*.dmg "${WORKSPACE}/releases/${release_name}/"
            # mv "${WORKSPACE}/releases/${release_name}/komodo-qt${ext}" "${WORKSPACE}/releases/${release_name}/komodo-qt-mac${ext}"
            ;;
        *)
            echo "Unknown release name: $release_name"
            ;;
    esac
}

check_image_focal() {
    if [[ "${force_rebuild_containers}" == "true" || "$(docker images --format '{{.Repository}}' | grep -c ocean_focal_builder)" -eq 0 ]]; then
        echo "Container 'ocean_focal_builder' rebuilding ..."
        docker build --no-cache -f Dockerfile.focal.ci --build-arg BUILDER_NAME=$USER --build-arg BUILDER_UID=$(id -u) --build-arg BUILDER_GID=$(id -g) -t ocean_focal_builder .
    fi
}

check_image_xenial() {
    if [[ "${force_rebuild_containers}" == "true" || "$(docker images --format '{{.Repository}}' | grep -c ocean_xenial_builder)" -eq 0 ]]; then
        echo "Container 'ocean_xenial_builder' rebuilding ..."
        docker build --no-cache -f Dockerfile.xenial.ci --build-arg BUILDER_NAME=$USER --build-arg BUILDER_UID=$(id -u) --build-arg BUILDER_GID=$(id -g) -t ocean_xenial_builder .
    fi
}

# https://stackoverflow.com/questions/4774054/reliable-way-for-a-bash-script-to-get-the-full-path-to-itself
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
pushd ${SCRIPTPATH}
WORKSPACE=$(pwd)

echo "Workspace directory: ${WORKSPACE}"

# Check if awk command exists
command -v awk >/dev/null 2>&1 || { echo >&2 "ERROR: awk command not found."; exit 1; }
# Check if sha256sum command exists
command -v sha256sum >/dev/null 2>&1 || { echo >&2 "ERROR: sha256sum command not found."; exit 1; }
# Simple check if docker exists
command -v docker >/dev/null 2>&1 || { echo >&2 "ERROR: docker not found."; exit 1; }

### xenial
if [[ "${build_xenial}" = "true" ]]; then

    # delete old depends binaries (from previous linux version, bcz it's x86_64-unknown-linux-gnu also)
    if [[ "${delete_linux_depends}" = true ]]; then
        rm -rf ${WORKSPACE}/depends/built/x86_64-unknown-linux-gnu
        rm -rf ${WORKSPACE}/depends/x86_64-unknown-linux-gnu
        rm -rf ${WORKSPACE}/depends/built/x86_64-pc-linux-gnu
        rm -rf ${WORKSPACE}/depends/x86_64-pc-linux-gnu
    fi
    # delete possible artefacts from previous build(s)
    delete_artefacts xenial

    check_image_xenial

    docker run -it -u $(id -u ${USER}):$(id -g ${USER}) -v $PWD:$PWD -w $PWD -e HOME=/root ocean_xenial_builder /bin/bash -c 'zcutil/build.sh -j'$(expr $(nproc) - 1)
    copy_release xenial
fi

### focal
if [[ "${build_focal}" = "true" ]]; then

    # delete old depends binaries (from previous linux version, bcz it's x86_64-unknown-linux-gnu also)
    if [[ "${delete_linux_depends}" = true ]]; then
        rm -rf ${WORKSPACE}/depends/built/x86_64-unknown-linux-gnu
        rm -rf ${WORKSPACE}/depends/x86_64-unknown-linux-gnu
        rm -rf ${WORKSPACE}/depends/built/x86_64-pc-linux-gnu
        rm -rf ${WORKSPACE}/depends/x86_64-pc-linux-gnu
    fi
    # delete possible artefacts from previous build(s)
    delete_artefacts focal

    check_image_focal

    docker run -it -u $(id -u ${USER}):$(id -g ${USER}) -v $PWD:$PWD -w $PWD -e HOME=/root ocean_focal_builder /bin/bash -c 'zcutil/build.sh -j'$(expr $(nproc) - 1)
    copy_release focal
fi

### windows
if [[ "${build_windows}" = "true" ]]; then
    delete_artefacts windows

    check_image_focal

    docker run -it -u $(id -u ${USER}):$(id -g ${USER}) -v $PWD:$PWD -w $PWD -e HOME=/root ocean_focal_builder /bin/bash -c 'zcutil/build-win.sh -j'$(expr $(nproc) - 1)
    copy_release windows
fi

### macos
if [[ "${build_macos}" = "true" ]]; then
    download_and_check_macos_sdk
    delete_artefacts macos

    check_image_focal

    docker run -it -u $(id -u ${USER}):$(id -g ${USER}) -v $PWD:$PWD -w $PWD -e HOME=/root ocean_focal_builder /bin/bash -c 'zcutil/build-mac-cross.sh -j'$(expr $(nproc) - 1)
    copy_release macos
fi

popd