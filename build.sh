#!/bin/bash
# build.sh
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
python -m flask db upgrade