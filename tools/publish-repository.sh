#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# User explicitly authorized public repository creation; this does not create a release.
[ "$(gh api user --jq .login)" = lowmiaq-gmail ] || { echo 'Wrong GitHub account'; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo 'Commit changes first'; exit 1; }
gh repo create lowmiaq-gmail/embedded-rust-verify --public --source . --remote origin --push
