#!/usr/bin/env bash

# If `make clean` fails for any reason, it is helpful to
# manually clean any remaining files from the previous build.
# This is especially useful if the new build is for a different
# architecture than the previous build, such as a Windows release
# after an OSX cross-compile. Normally these files should be
# cleaned during `make clean` execution.

is_git_root=0

function check_git_root() {

  local dir=$(pwd)

  while [[ "$dir" != "" && ! -d "$dir/.git" ]]; do
    dir=${dir%/*} # ${parameter%word}
  done

  if [ "$dir" == "" ]; then
    echo "$(pwd) is not in a Git repository. Exiting..."
    is_git_root=0
  else
    if [ "$dir" != "$(pwd)" ]; then
      echo "$(pwd) is not the root of the Git repository. Exiting..."
      is_git_root=0
    else
      echo "$(pwd) is the root of the Git repository."
      is_git_root=1
    fi
  fi
}

check_git_root

if [ "$is_git_root" -eq "1" ]; then

    rm -f ./src/qt/moc_*.cpp # delete meta object code files, otherwise we will have MacOS after Linux/Windows build error
    rm -f ./src/qt/*.moc
    rm -f ./src/qt/libkomodoqt.a
    rm -f ./src/leveldb/libmemenv.a
    rm -f ./src/leveldb/libleveldb_sse42.a
    rm -f ./src/leveldb/libleveldb.a
    rm -f ./src/qt/qrc_komodo.cpp
    rm -f ./src/qt/qrc_komodo_locale.cpp

    # https://unix.stackexchange.com/questions/84265/linux-shell-find-exec-in-find-exec
    # https://askubuntu.com/questions/377438/how-can-i-recursively-delete-all-files-of-a-specific-extension-in-the-current-di

    # search for *.a, *.la, *.o, *.lo, *.Plo, *.Po, *.lai, *.dirstamp in all folders starting from .src, including hidden folders,
    # to search only in hidden folders add -path "*/.*" arg to command
    find ./src \( -name "*.a" -o -name "*.la" -o -name "*.o" -o -name "*.lo" -o -name "*.Plo" -o -name "*.Po" -o -name "*.lai" -o -name "*.dirstamp" \) -delete
    echo "Remnant build files deleted!"
fi



