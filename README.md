# bilibili-video-notes-tool

一个用于提取哔哩哔哩视频学习资料的 Python CLI 工具。支持获取视频元数据、接收浏览器页面会话中捕获的播放信息、下载公开视频字幕、仅下载音频、调用本地 faster-whisper 进行 ASR 转写，并可生成 Markdown 学习笔记草稿。推荐工作流是先通过浏览器自动化打开 Bilibili 页面并完成登录，再把页面上下文里的 playurl/subtitle JSON 交给 CLI 处理；公共 API 和 yt-dlp 作为回退方案。适合课程学习、视频资料整理、Obsidian 笔记流和个人知识库构建。

Extract Bilibili video metadata, browser-captured media URLs, subtitles, audio, local ASR transcripts, and Markdown study-note drafts.

The tool is designed for course/video study workflows:

- Use a logged-in browser page session to capture metadata, subtitles, and signed audio stream URLs.
- Fetch public Bilibili metadata with the official web APIs when the browser path is unavailable.
- Prefer existing subtitles when available.
- Download only audio, not full video, when ASR is needed.
- Fall back to `yt-dlp` for API-drift cases or when browser page extraction fails.
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

Recommended browser-first workflow:

1. Open the Bilibili video page in a normal logged-in browser or with browser automation.
2. From the page context, capture the current metadata/play URL JSON:

```js
async () => {
  const state = window.__INITIAL_STATE__ || {};
  const bvid = state.bvid;
  const cid = state.videoData?.cid || state.cid;
  const playurl = await fetch(
    `https://api.bilibili.com/x/player/playurl?bvid=${bvid}&cid=${cid}&qn=16&fnval=4048&fourk=1`,
    { credentials: "include", headers: { accept: "application/json" } }
  ).then((response) => response.json());
  const player = await fetch(
    `https://api.bilibili.com/x/player/v2?bvid=${bvid}&cid=${cid}`,
    { credentials: "include", headers: { accept: "application/json" } }
  ).then((response) => response.json());
  return {
    initialState: state,
    playinfo: window.__playinfo__ || null,
    playurl,
    player,
  };
}
```

3. Save that result as `browser.json`, then run:

```bash
bili-video-notes "https://www.bilibili.com/video/BV1xxxxxxx/" \
  --browser-metadata-json ./browser.json \
  --out-dir ./output \
  --download-subtitles \
  --download-audio \
  --transcribe \
  --write-note
```

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

1. If `--browser-metadata-json` is provided, use that logged-in page capture first.
2. Otherwise try direct public Bilibili APIs for metadata, subtitles, and audio streams.
3. If direct audio fails, fall back to `yt-dlp` when installed.
4. Use local `faster-whisper` only when `--transcribe` is requested.

Why browser-first:

- Page-context `fetch(..., { credentials: "include" })` reuses the active Bilibili login session without reading local cookie databases.
- Signed DASH audio URLs can be selected directly from `data.dash.audio`, usually by highest `bandwidth`.
- It avoids macOS Keychain prompts and the fragile `yt-dlp --cookies-from-browser` path unless that fallback is truly needed.

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
