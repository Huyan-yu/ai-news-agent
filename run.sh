#!/usr/bin/env bash
# 一键起环境: 建虚拟环境 + 装依赖 + 起 Web
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
: "${AGNES_API_KEY:?AGNES_API_KEY not set; export it before running}"
echo "[OK] ready. Starting web on http://127.0.0.1:8000"
python app.py
