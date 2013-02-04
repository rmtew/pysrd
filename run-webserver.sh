#!/bin/bash
[ -f /c/python27/python.exe ] && export PYTHON=/c/python27/python.exe || export PYTHON=python
$PYTHON python/run-webserver.py $@
