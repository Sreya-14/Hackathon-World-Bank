#!/usr/bin/env bash
# Build the app for GitHub Pages and push the built files to the gh-pages branch.
# Only app/dist is pushed; source branches are untouched.
#   Usage:  scripts/deploy-pages.sh
#           VITE_API_URL=https://<backend> scripts/deploy-pages.sh   (live listings instead of samples)
set -euo pipefail

if [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  echo "Node $(node -v) is too old for Vite; need 20+. Run: nvm use 22" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_URL="$(git -C "$ROOT" remote get-url origin)"
REPO="$(basename -s .git "$REMOTE_URL")"

cd "$ROOT/app"
BASE_PATH="/$REPO/" npx vite build

# GitHub Pages has no SPA fallback: serve the app for unknown paths (e.g. the share target).
cp dist/index.html dist/404.html
# Don't let Jekyll drop files that start with an underscore.
touch dist/.nojekyll

cd dist
rm -rf .git
git init -q -b gh-pages
git add -A
git -c user.name="$(git -C "$ROOT" config user.name)" -c user.email="$(git -C "$ROOT" config user.email)" \
  commit -q -m "Deploy $(git -C "$ROOT" describe --always --dirty) ($(date -u +%Y-%m-%dT%H:%MZ))"
git push -q -f "$REMOTE_URL" gh-pages
rm -rf .git

echo "Pushed to gh-pages. Site: https://$(basename "$(dirname "$REMOTE_URL")" | tr '[:upper:]' '[:lower:]').github.io/$REPO/"
