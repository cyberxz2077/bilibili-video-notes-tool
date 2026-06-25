#!/usr/bin/env bash
set -euo pipefail

bili-video-notes "https://www.bilibili.com/video/BV1xxxxxxx/" \
  --browser-metadata-json ./browser.json \
  --out-dir ./output \
  --download-subtitles \
  --download-audio \
  --transcribe \
  --write-note
