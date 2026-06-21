# bili-video-notes

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
git clone https://github.com/your-name/bili-video-notes.git
cd bili-video-notes
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
