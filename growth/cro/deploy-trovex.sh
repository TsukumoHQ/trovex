#!/usr/bin/env bash
# Deploy trovex.dev (origin/main) to Vercel production from any worktree.
#
# Why a script: the trovex MAIN checkout is usually parked on another lead's
# branch, so `vercel --prod` there deploys the WRONG code and a plain ff-merge
# fails. This detaches to the real origin/main, deploys, and restores your branch.
# Deterministic-first (20/80): the repeated, error-prone ship step, scripted once.
#
# Run from the trovex repo or any trovex worktree. Requires: gh-less, vercel CLI
# authed as helios-code. Project/org IDs are public identifiers, not secrets.
set -euo pipefail

ORG_ID="team_5OLH1GrvOmFUOkTI0eyRjNnA"
PROJECT_ID="prj_YF2512MDXaAn23E6K8if1dDAPyST"

START_REF=$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)
restore() { git checkout -q "$START_REF" 2>/dev/null || true; }
trap restore EXIT

git fetch origin -q
git checkout -q --detach origin/main
echo "→ deploying trovex.dev @ $(git log -1 --oneline)"
VERCEL_ORG_ID="$ORG_ID" VERCEL_PROJECT_ID="$PROJECT_ID" vercel --prod --yes
echo "✓ deployed (restoring $START_REF)"
