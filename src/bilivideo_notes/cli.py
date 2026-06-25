#!/usr/bin/env python3
"""Fetch Bilibili metadata/subtitles/audio and optionally run local ASR.

Default backend order is:
1. Browser-captured metadata/play URLs from a logged-in page session.
2. Direct public Bilibili APIs for fast, dependency-light processing.
3. Optional yt-dlp fallback for cases where Bilibili APIs fail or audio streams
   require browser cookies.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


UA = "Mozilla/5.0"
PACKAGE_NAME = "bili-video-notes"


def extract_bvid(value: str) -> str:
    match = re.search(r"BV[0-9A-Za-z]+", value)
    if not match:
        raise SystemExit(f"Could not find BVID in: {value}")
    return match.group(0)


def video_url(bvid: str) -> str:
    return f"https://www.bilibili.com/video/{bvid}/"


def request_json(url: str, bvid: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": video_url(bvid)},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download(url: str, path: pathlib.Path, bvid: str) -> int:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": video_url(bvid)},
    )
    total = 0
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
            if total and total % (20 * 1024 * 1024) < 1024 * 1024:
                print(f"downloaded_mb={total / 1024 / 1024:.1f}", file=sys.stderr, flush=True)
    return total


def fmt_time(seconds: float | int | None) -> str:
    seconds = float(seconds or 0)
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def write_json(path: pathlib.Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def first_dict(*values: object) -> dict:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def owner_name(owner: object) -> str | None:
    if isinstance(owner, dict):
        value = owner.get("name") or owner.get("uname") or owner.get("mid")
        return str(value) if value is not None else None
    return str(owner) if owner else None


def subtitles_from_metadata(raw_metadata: dict[str, object]) -> list[dict]:
    player = first_dict(raw_metadata.get("player"))
    browser = first_dict(raw_metadata.get("browser"))
    state = first_dict(
        browser.get("__INITIAL_STATE__"),
        browser.get("initialState"),
        browser.get("initial_state"),
        browser.get("state"),
    )
    playinfo = first_dict(browser.get("__playinfo__"), browser.get("playinfo"), browser.get("playInfo"))

    candidates: list[object] = [
        ((player.get("data") or {}).get("subtitle") or {}).get("subtitles") if isinstance(player.get("data"), dict) else None,
        browser.get("subtitles"),
        ((playinfo.get("data") or {}).get("subtitle") or {}).get("subtitles") if isinstance(playinfo.get("data"), dict) else None,
        ((state.get("videoData") or {}).get("subtitle") or {}).get("subtitles") if isinstance(state.get("videoData"), dict) else None,
        (state.get("subtitle") or {}).get("list") if isinstance(state.get("subtitle"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return [item for item in candidate if isinstance(item, dict)]
    return []


def playurl_from_metadata(raw_metadata: dict[str, object]) -> dict:
    playurl = first_dict(raw_metadata.get("playurl"))
    if playurl:
        return playurl
    browser = first_dict(raw_metadata.get("browser"))
    return first_dict(
        browser.get("playurl"),
        browser.get("play_url"),
        browser.get("__playinfo__"),
        browser.get("playinfo"),
        browser.get("playInfo"),
    )


def browser_probe(browser_json_path: pathlib.Path, bvid: str) -> tuple[dict, dict]:
    payload = json.loads(browser_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("--browser-metadata-json must point to a JSON object")

    state = first_dict(
        payload.get("__INITIAL_STATE__"),
        payload.get("initialState"),
        payload.get("initial_state"),
        payload.get("state"),
        payload,
    )
    video_data = first_dict(state.get("videoData"), state.get("video_data"), payload.get("videoData"))
    playinfo = first_dict(payload.get("__playinfo__"), payload.get("playinfo"), payload.get("playInfo"))
    player = first_dict(payload.get("player"))
    playurl = playurl_from_metadata({"browser": payload})

    resolved_bvid = (
        payload.get("bvid")
        or state.get("bvid")
        or video_data.get("bvid")
        or bvid
    )
    duration = (
        payload.get("duration")
        or video_data.get("duration")
        or ((playinfo.get("data") or {}).get("timelength") / 1000 if isinstance(playinfo.get("data"), dict) and playinfo["data"].get("timelength") else None)
    )
    cid = payload.get("cid") or state.get("cid") or video_data.get("cid")
    raw_metadata: dict[str, object] = {"browser": payload}
    if player:
        raw_metadata["player"] = player
    if playurl:
        raw_metadata["playurl"] = playurl

    summary = {
        "backend_used": "browser",
        "bvid": resolved_bvid,
        "aid": payload.get("aid") or state.get("aid") or video_data.get("aid"),
        "cid": cid,
        "title": payload.get("title") or video_data.get("title") or state.get("title"),
        "owner": owner_name(payload.get("owner") or video_data.get("owner") or state.get("owner")),
        "duration": duration,
        "duration_hhmmss": fmt_time(duration),
        "desc": payload.get("desc") or video_data.get("desc") or state.get("desc"),
        "subtitle_count": len(subtitles_from_metadata(raw_metadata)),
        "need_login_subtitle": None,
        "outputs": {},
    }
    return summary, raw_metadata


def write_subtitle_jsonl(subtitle_json: dict, output: pathlib.Path) -> int:
    count = 0
    body = subtitle_json.get("body") or []
    with output.open("w", encoding="utf-8") as out:
        for item in body:
            text = (item.get("content") or "").strip()
            if not text:
                continue
            record = {
                "id": count,
                "start": item.get("from"),
                "end": item.get("to"),
                "text": text,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_transcript_jsonl(path: pathlib.Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as src:
        for line in src:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def build_note_markdown(summary: dict, transcript_path: pathlib.Path, transcript_source: str) -> str:
    records = read_transcript_jsonl(transcript_path)
    title = summary.get("title") or summary.get("bvid") or "Bilibili video"
    bvid = summary.get("bvid") or ""
    owner = summary.get("owner") or ""
    duration = summary.get("duration_hhmmss") or fmt_time(summary.get("duration"))
    created = time.strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "---",
        "type: video-note",
        "source: Bilibili",
        f"bvid: {bvid}",
        f"video_title: {json.dumps(title, ensure_ascii=False)}",
        f"created: {created}",
        f"transcript_source: {transcript_source}",
        "---",
        "",
        f"# {title}",
        "",
        "## Source",
        "",
        f"- UP: {owner}",
        f"- Duration: {duration}",
        f"- BVID: {bvid}",
        f"- URL: {video_url(str(bvid)) if bvid else ''}",
        f"- Transcript source: {transcript_source}",
        "",
        "## 0. Overview",
        "",
        "This is a transcript-backed draft note. Review the timeline, merge repeated points, and add your own conclusions.",
        "",
        "## 1. Timeline Notes",
        "",
    ]

    bucket: list[str] = []
    bucket_start: float | None = None
    bucket_end = 0.0
    bucket_seconds = 8 * 60

    def flush_bucket() -> None:
        nonlocal bucket, bucket_start, bucket_end
        if not bucket:
            return
        start = fmt_time(bucket_start)
        end = fmt_time(bucket_end)
        text = " ".join(bucket)
        lines.extend([f"### {start}-{end}", "", text, ""])
        bucket = []
        bucket_start = None
        bucket_end = 0.0

    for record in records:
        text = (record.get("text") or "").strip()
        if not text:
            continue
        start = float(record.get("start") or 0)
        end = float(record.get("end") or start)
        if bucket_start is None:
            bucket_start = start
        if start - bucket_start >= bucket_seconds:
            flush_bucket()
            bucket_start = start
        bucket.append(text)
        bucket_end = max(bucket_end, end)
    flush_bucket()

    lines.extend(
        [
            "## 2. Key Concepts Index",
            "",
            "- TODO: add important terms after review.",
            "",
            "## 3. Actionable Templates",
            "",
            "- TODO: extract reusable methods, checklists, or decision rules.",
            "",
            "## 4. One-Sentence Review",
            "",
            "- TODO: summarize the video in one sentence.",
            "",
        ]
    )
    return "\n".join(lines)


def ytdlp_base_cmd(args: argparse.Namespace, url: str) -> list[str]:
    cmd = [args.yt_dlp_bin, "--no-playlist"]
    if args.cookies_from_browser:
        cmd += ["--cookies-from-browser", args.cookies_from_browser]
    cmd.append(url)
    return cmd


def run_ytdlp_json(args: argparse.Namespace, url: str) -> dict:
    if not shutil.which(args.yt_dlp_bin):
        raise RuntimeError(f"{args.yt_dlp_bin!r} not found on PATH")
    cmd = ytdlp_base_cmd(args, url)
    cmd.insert(1, "-J")
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"yt-dlp failed with exit code {proc.returncode}")
    return json.loads(proc.stdout)


def download_audio_ytdlp(args: argparse.Namespace, url: str, bvid: str, out_dir: pathlib.Path) -> pathlib.Path:
    if not shutil.which(args.yt_dlp_bin):
        raise RuntimeError(f"{args.yt_dlp_bin!r} not found on PATH")
    out_template = str(out_dir / f"{bvid}_audio.%(ext)s")
    cmd = [
        args.yt_dlp_bin,
        "--no-playlist",
        "-f",
        args.yt_dlp_format,
        "--no-progress",
        "--print",
        "after_move:filepath",
        "-o",
        out_template,
    ]
    if args.cookies_from_browser:
        cmd += ["--cookies-from-browser", args.cookies_from_browser]
    cmd.append(url)
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"yt-dlp failed with exit code {proc.returncode}")
    candidates = [pathlib.Path(line.strip()) for line in proc.stdout.splitlines() if line.strip()]
    for candidate in reversed(candidates):
        if candidate.exists():
            return candidate
    raise RuntimeError("yt-dlp did not report an existing audio output path")


def api_probe(bvid: str) -> tuple[dict, dict, dict]:
    view = request_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", bvid)
    if view.get("code") != 0:
        raise RuntimeError(f"view API failed: {view}")
    data = view["data"]
    cid = data["cid"]
    player = request_json(f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}", bvid)
    subtitles = (player.get("data") or {}).get("subtitle", {}).get("subtitles") or []
    view_subtitles = (data.get("subtitle") or {}).get("list") or []
    summary = {
        "backend_used": "api",
        "bvid": bvid,
        "aid": data.get("aid"),
        "cid": cid,
        "title": data.get("title"),
        "owner": (data.get("owner") or {}).get("name"),
        "duration": data.get("duration"),
        "duration_hhmmss": fmt_time(data.get("duration")),
        "desc": data.get("desc"),
        "subtitle_count": len(subtitles) or len(view_subtitles),
        "need_login_subtitle": (player.get("data") or {}).get("need_login_subtitle"),
        "outputs": {},
    }
    return summary, view, player


def ytdlp_probe(args: argparse.Namespace, bvid: str) -> tuple[dict, dict]:
    info = run_ytdlp_json(args, video_url(bvid))
    subtitles = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    summary = {
        "backend_used": "yt-dlp",
        "bvid": bvid,
        "aid": None,
        "cid": None,
        "title": info.get("title"),
        "owner": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
        "duration_hhmmss": fmt_time(info.get("duration")),
        "desc": info.get("description"),
        "subtitle_count": len(subtitles) or len(automatic),
        "need_login_subtitle": None,
        "outputs": {},
    }
    return summary, info


def transcribe_audio(audio: pathlib.Path, output: pathlib.Path, meta_output: pathlib.Path, bvid: str, args: argparse.Namespace) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SystemExit(
            "faster-whisper is not installed in this Python environment. "
            "Run inside /tmp/bili-asr-venv or install faster-whisper."
        ) from exc

    start = time.time()
    print(
        f"loading_model={args.model} device={args.device} compute_type={args.compute_type}",
        file=sys.stderr,
        flush=True,
    )
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    print(f"model_loaded_seconds={time.time() - start:.1f}", file=sys.stderr, flush=True)

    segments, info = model.transcribe(
        str(audio),
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": args.min_silence_ms},
    )
    count = 0
    with output.open("w", encoding="utf-8") as out:
        for segment in segments:
            record = {
                "id": segment.id,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            if count % 100 == 0:
                print(
                    f"segments={count} last_end={segment.end:.1f} elapsed={time.time() - start:.1f}",
                    file=sys.stderr,
                    flush=True,
                )

    meta = {
        "bvid": bvid,
        "audio": str(audio),
        "output": str(output),
        "segments": count,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "elapsed_seconds": round(time.time() - start, 1),
    }
    write_json(meta_output, meta)
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(
        prog=PACKAGE_NAME,
        description="Extract Bilibili metadata, subtitles, audio, local ASR transcripts, and Markdown study-note drafts.",
    )
    parser.add_argument("url_or_bvid")
    parser.add_argument("--out-dir", default="/tmp")
    parser.add_argument("--backend", choices=["auto", "api", "yt-dlp"], default="auto")
    parser.add_argument(
        "--browser-metadata-json",
        type=pathlib.Path,
        help=(
            "JSON captured from a logged-in Bilibili page context. When provided, "
            "this is used before public APIs and yt-dlp."
        ),
    )
    parser.add_argument("--yt-dlp-bin", default="yt-dlp")
    parser.add_argument("--yt-dlp-format", default="ba/bestaudio")
    parser.add_argument("--cookies-from-browser", help="Pass through to yt-dlp, e.g. chrome or safari")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--save-metadata", action="store_true")
    parser.add_argument("--download-audio", action="store_true")
    parser.add_argument("--download-subtitles", action="store_true")
    parser.add_argument("--transcribe", action="store_true")
    parser.add_argument(
        "--write-note",
        action="store_true",
        help="Write a Markdown study-note draft from subtitles or ASR transcript.",
    )
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--min-silence-ms", type=int, default=500)
    args = parser.parse_args()

    bvid = extract_bvid(args.url_or_bvid)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_metadata: dict[str, object] = {}
    api_error = None

    if args.browser_metadata_json:
        summary, raw_metadata = browser_probe(args.browser_metadata_json, bvid)
    elif args.backend in {"auto", "api"}:
        try:
            summary, view, player = api_probe(bvid)
            raw_metadata = {"view": view, "player": player}
        except Exception as exc:
            api_error = str(exc)
            if args.backend == "api":
                raise
    if not raw_metadata and args.backend in {"auto", "yt-dlp"}:
        summary, info = ytdlp_probe(args, bvid)
        raw_metadata = {"yt_dlp": info}
        if api_error:
            summary["api_error"] = api_error
    elif not raw_metadata:
        raise RuntimeError(api_error or "No metadata backend succeeded")

    if args.save_metadata or not args.metadata_only:
        metadata_path = out_dir / f"{bvid}_metadata.json"
        write_json(metadata_path, raw_metadata)
        summary["outputs"]["metadata"] = str(metadata_path)

    if args.download_subtitles:
        subtitles = subtitles_from_metadata(raw_metadata)
        if subtitles:
            sub = subtitles[0]
            sub_url = sub.get("subtitle_url") or sub.get("subtitleUrl")
            if sub_url and sub_url.startswith("//"):
                sub_url = "https:" + sub_url
            if sub_url:
                subtitle_json = request_json(sub_url, bvid)
                subtitle_path = out_dir / f"{bvid}_subtitles.json"
                subtitle_jsonl = out_dir / f"{bvid}_subtitle_transcript.jsonl"
                write_json(subtitle_path, subtitle_json)
                count = write_subtitle_jsonl(subtitle_json, subtitle_jsonl)
                summary["outputs"]["subtitle_json"] = str(subtitle_path)
                summary["outputs"]["subtitle_jsonl"] = str(subtitle_jsonl)
                summary["subtitle_segments"] = count
        elif summary["backend_used"] == "yt-dlp":
            summary["subtitle_note"] = (
                "yt-dlp detected subtitle metadata, but this script does not parse yt-dlp subtitle files yet. "
                "Use yt-dlp --write-subs/--write-auto-subs if subtitle extraction is required."
            )

    if args.metadata_only:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    audio_path = out_dir / f"{bvid}_audio.m4s"
    if args.download_audio or args.transcribe:
        if summary["backend_used"] in {"api", "browser"}:
            try:
                playurl = playurl_from_metadata(raw_metadata)
                if not playurl:
                    cid = summary.get("cid")
                    playurl = request_json(
                        f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=4048&fourk=1",
                        bvid,
                    )
                audios = ((playurl.get("data") or {}).get("dash") or {}).get("audio") or []
                if not audios:
                    raise RuntimeError("No audio streams found in playurl")
                audio = max(audios, key=lambda item: item.get("bandwidth") or 0)
                audio_url = audio.get("baseUrl") or audio.get("base_url")
                if not audio_url:
                    raise RuntimeError("Selected audio stream has no URL")
                bytes_written = download(audio_url, audio_path, bvid)
                summary["selected_audio"] = {
                    "backend": summary["backend_used"],
                    "id": audio.get("id"),
                    "bandwidth": audio.get("bandwidth"),
                    "mimeType": audio.get("mimeType"),
                    "codecs": audio.get("codecs"),
                }
                summary["audio_bytes"] = bytes_written
            except Exception as exc:
                if args.backend == "api":
                    raise
                summary["api_audio_error"] = str(exc)
                audio_path = download_audio_ytdlp(args, video_url(bvid), bvid, out_dir)
                summary["selected_audio"] = {"backend": "yt-dlp", "format": args.yt_dlp_format}
                summary["audio_bytes"] = audio_path.stat().st_size
        else:
            audio_path = download_audio_ytdlp(args, video_url(bvid), bvid, out_dir)
            summary["selected_audio"] = {"backend": "yt-dlp", "format": args.yt_dlp_format}
            summary["audio_bytes"] = audio_path.stat().st_size
        summary["outputs"]["audio"] = str(audio_path)

    if args.transcribe:
        transcript_path = out_dir / f"{bvid}_transcript.jsonl"
        meta_path = out_dir / f"{bvid}_transcript_meta.json"
        meta = transcribe_audio(audio_path, transcript_path, meta_path, bvid, args)
        summary["outputs"]["transcript"] = str(transcript_path)
        summary["outputs"]["transcript_meta"] = str(meta_path)
        summary["asr"] = meta

    if args.write_note:
        transcript_source = None
        transcript_for_note = None
        if summary["outputs"].get("subtitle_jsonl"):
            transcript_source = "subtitle"
            transcript_for_note = pathlib.Path(summary["outputs"]["subtitle_jsonl"])
        elif summary["outputs"].get("transcript"):
            transcript_source = "asr"
            transcript_for_note = pathlib.Path(summary["outputs"]["transcript"])
        if not transcript_for_note:
            raise RuntimeError("--write-note requires --download-subtitles or --transcribe to produce transcript text")
        note_path = out_dir / f"{bvid}_study_note.md"
        note_path.write_text(build_note_markdown(summary, transcript_for_note, transcript_source), encoding="utf-8")
        summary["outputs"]["note"] = str(note_path)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        raise
