#!/usr/bin/env bash
set -e

echo "Building standalone binary using PyInstaller..."

# Define hidden imports for Textual and rich
HIDDEN_IMPORTS="--hidden-import textual.widgets --hidden-import rich"

pyinstaller --name gptcgt \
            --onefile \
            --clean \
            $HIDDEN_IMPORTS \
            src/tui/app.py

echo "Build complete! Binary is located in dist/gptcgt"
