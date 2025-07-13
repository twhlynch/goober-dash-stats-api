#!/usr/bin/env bash

python3 -m venv .

bin/pip install -r requirements.txt

bin/python update.py $EMAIL $PASSWORD