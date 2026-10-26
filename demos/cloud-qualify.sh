#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 PIP_NO_CACHE_DIR=1
ulimit -v 4194304
available=$(df -Pk . | awk 'NR==2 {print $4}')
[ "$available" -gt 10485760 ] || { echo 'Need 10 GiB free scratch'; exit 1; }
python3.12 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
cd demos
../.venv/bin/python -m pip install -q -r requirements-livekit.txt -r requirements-pipecat.txt
cd ..
.venv/bin/python -m unittest discover -s livekit-plugins-pyai/tests -v
.venv/bin/python -m unittest discover -s pipecat-pyai/tests -v
PYAI_API_KEY=offline-contract OPENAI_API_KEY=offline-contract .venv/bin/python demos/livekit_agent.py --help
PYAI_API_KEY=offline-contract OPENAI_API_KEY=offline-contract .venv/bin/python demos/pipecat_bot.py --help
.venv/bin/python -m unittest discover -s demos -p 'test_*.py' -v
.venv/bin/python demos/pipecat_pipeline_check.py
.venv/bin/python -m pip freeze > qualification-packages.txt
