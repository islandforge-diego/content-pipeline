#!/usr/bin/env bash
# Publish the generated client preview to the GitHub Pages repo.
#
# Builds the pages (generate.py) and pushes the output (clients/ + root index.html)
# to the dedicated preview repo, which serves GitHub Pages. The pipeline/tool repo
# stays private; only the built review site is public.
#
# Usage:  ./deploy.sh
# Override the target with:  PREVIEW_REPO=https://github.com/<owner>/<repo>.git ./deploy.sh
set -euo pipefail

REPO="${PREVIEW_REPO:-https://github.com/islandforge-diego/deba-content-preview.git}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "Building preview pages…"
python3 generate.py

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Cloning $REPO…"
git clone --depth 1 "$REPO" "$TMP" >/dev/null 2>&1

cp -R clients "$TMP"/
cp index.html "$TMP"/

cd "$TMP"
git add -A
if git diff --cached --quiet; then
  echo "No changes to publish."
else
  git commit -m "Update content preview" >/dev/null
  git push
  echo "Published. GitHub Pages will refresh in ~1 minute."
fi
