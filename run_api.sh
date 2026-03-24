#!/bin/bash
cd "$(dirname "$0")"
exec python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 "$@"
