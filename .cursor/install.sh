#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

corepack enable
corepack pnpm install --frozen-lockfile

mkdir -p data
