#!/usr/bin/env bash
# GitHub の Issue を立てて、スマホの GitHub アプリに通知する。 使い方: alert.sh "タイトル" "本文"
set -u
gh label create alert --color d73a4a --description "ルイからの警告" --force >/dev/null 2>&1 || true
run="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
gh issue create --title "$1（$(TZ=Asia/Tokyo date '+%m/%d %H:%M')）" --label alert \
  --body "@tatuya-st $2

詳細: $run" || true
