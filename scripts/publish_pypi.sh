#!/usr/bin/env bash
set -e

echo "Building gptcgt package..."
python -m build

echo "Uploading to PyPI..."
twine upload dist/*

echo "Publishing complete!"
