# bilibili-video-notes-tool

一个用于提取哔哩哔哩视频学习资料的 Python CLI 工具。支持获取视频元数据、下载公开视频字幕、仅下载音频、调用本地 faster-whisper 进行 ASR 转写，并可生成 Markdown 学习笔记草稿。默认优先使用 Bilibili 公共 API，失败时可通过 yt-dlp 和浏览器 cookies 回退处理。适合课程学习、视频资料整理、Obsidian 笔记流和个人知识库构建。

Extract Bilibili video metadata, subtitles, audio, local ASR transcripts, and Markdown study-note drafts.

The tool is designed for course/video study workflows:

- Fetch public Bilibili metadata with the official web APIs.
- Prefer existing subtitles when available.
- Download only audio, not full video, when ASR is needed.
- Fall back to `yt-dlp` for login/cookie or API-drift cases.
- Run local `faster-whisper` ASR when subtitles are unavailable.
- Generate a transcript-backed Markdown note draft.

> Use this for personal study, research, and content you have the right to process. Do not redistribute copyrighted transcripts without permission.

## Install

From source:

```bash
git clone https://github.com/cyberxz2077/bilibili-video-notes-tool.git
cd bilibili-video-notes-tool
python3 -m pip install -e .
```

Optional ASR and `yt-dlp` support:

```bash
python3 -m pip install -e ".[all]"
```

## Quick Start

Metadata only:

```bash
bili-video-notes "https://www.bilibili.com/video/BV1xxxxxxx/" --metadata-only
```

Download subtitles and create a Markdown note draft:

```bash
bili-video-notes "https://www.bilibili.com/video/BV1xxxxxxx/" \
  --out-dir ./output \
  --download-subtitles \
  --write-note
```

Download audio and run local ASR:

```bash
bili-video-notes "https://www.bilibili.com/video/BV1xxxxxxx/" \
  --out-dir ./output \
  --download-audio \
  --transcribe \
  --write-note
```

Use `yt-dlp` with browser cookies when direct APIs fail:

```bash
bili-video-notes "https://www.bilibili.com/video/BV1xxxxxxx/" \
  --backend yt-dlp \
  --cookies-from-browser chrome \
  --out-dir ./output \
  --download-audio \
  --transcribe \
  --write-note
```

## Outputs

Depending on flags, the output directory may contain:

- `<BVID>_metadata.json`
- `<BVID>_subtitles.json`
- `<BVID>_subtitle_transcript.jsonl`
- `<BVID>_audio.m4s`
- `<BVID>_transcript.jsonl`
- `<BVID>_transcript_meta.json`
- `<BVID>_study_note.md`

## Backend Strategy

Default backend is `auto`:

1. Try direct public Bilibili APIs for metadata, subtitles, and audio streams.
2. If direct audio fails, fall back to `yt-dlp` when installed.
3. Use local `faster-whisper` only when `--transcribe` is requested.

Suggested ASR defaults are CPU-friendly:

```bash
--model small --device cpu --compute-type int8 --language zh
```

## Notes

`--write-note` creates a structured Markdown draft from subtitles or ASR transcript. It does not call an LLM and does not claim to produce a polished summary automatically. Review the timeline, merge repeated points, correct ASR mistakes, and add your own conclusions.

## Development

```bash
python3 -m pip install -e ".[dev]"
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall src
```

## License

MIT
