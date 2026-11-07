#!/bin/bash
set -e
cd "$(dirname "$0")"
if python3 -c 'import streamlit, pandas, altair, openpyxl' >/dev/null 2>&1; then
  runner=(python3)
else
  if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
  fi
  runner=(.venv/bin/python)
  if ! "${runner[@]}" -c 'import streamlit, pandas, altair, openpyxl' >/dev/null 2>&1; then
    "${runner[@]}" -m pip install -r requirements.txt
  fi
fi
exec "${runner[@]}" -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
