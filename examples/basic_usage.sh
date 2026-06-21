#!/usr/bin/env bash
set -euo pipefail

bili-video-notes "https://www.bilibili.com/video/BV1xxxxxxx/" \
  --out-dir ./output \
  --download-subtitles \
  --write-note
