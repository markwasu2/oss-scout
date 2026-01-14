#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Activate venv
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
else
  echo "❌ Missing .venv. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r pipeline/requirements.txt"
  exit 1
fi

echo "▶ Running pipeline/fetch.py"
python pipeline/fetch.py

echo "▶ Generating contributor graph"
python pipeline/graph.py

echo "▶ Copying data files to web/public/data/"
mkdir -p web/public/data
cp data/projects.json web/public/data/projects.json

# Copy embeddings if exists
if [ -f "data/embeddings.json" ]; then
  cp data/embeddings.json web/public/data/embeddings.json
  echo "   ✓ Copied embeddings.json"
fi

# Copy alerts if exists
if [ -f "data/alerts.json" ]; then
  cp data/alerts.json web/public/data/alerts.json
  echo "   ✓ Copied alerts.json"
fi

echo "✅ Done."
echo "   - data/projects.json"
echo "   - web/public/data/projects.json"
echo "   - web/public/data/graph.json"
