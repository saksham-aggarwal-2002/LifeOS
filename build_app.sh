#!/bin/sh
# Builds LifeOS.app and installs it in /Applications.
# Rerun only after changing the icon or setup.py. Code changes don't need a rebuild.
set -e
cd "$(dirname "$0")"

[ -f assets/LifeOS.icns ] || .venv/bin/python assets/make_icon.py

rm -rf build dist
.venv/bin/python setup.py py2app -A > build.log 2>&1 || { tail -20 build.log; exit 1; }
rm -f build.log

rm -rf /Applications/LifeOS.app
cp -R dist/LifeOS.app /Applications/
echo "Installed /Applications/LifeOS.app"
