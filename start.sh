#!/bin/bash

if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
    source .venv/bin/activate
    python3.11 -m pip install --upgrade pip
    python3.11 -m pip install -r config/requirements.txt
else
    source .venv/bin/activate
fi

python3.11 main.py