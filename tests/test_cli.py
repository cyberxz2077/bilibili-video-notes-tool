import json
import unittest
from pathlib import Path

from bilivideo_notes.cli import build_note_markdown, extract_bvid, fmt_time, write_subtitle_jsonl


class CliTests(unittest.TestCase):
    def test_extract_bvid_from_url(self):
        self.assertEqual(extract_bvid("https://www.bilibili.com/video/BV1WEVV6yEgf/?t=1"), "BV1WEVV6yEgf")

    def test_extract_bvid_rejects_invalid(self):
        with self.assertRaises(SystemExit):
            extract_bvid("https://example.com/no-bvid")

    def test_fmt_time(self):
        self.assertEqual(fmt_time(65), "01:05")
        self.assertEqual(fmt_time(None), "00:00")

    def test_subtitle_jsonl_and_note(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subtitle = {
                "body": [
                    {"from": 0, "to": 2, "content": "第一句"},
                    {"from": 3, "to": 5, "content": "第二句"},
                ]
            }
            transcript = tmp_path / "sub.jsonl"
            self.assertEqual(write_subtitle_jsonl(subtitle, transcript), 2)
            rows = [json.loads(line) for line in transcript.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["text"], "第一句")

            note = build_note_markdown(
                {
                    "title": "测试视频",
                    "bvid": "BV1WEVV6yEgf",
                    "owner": "测试UP",
                    "duration": 5,
                    "duration_hhmmss": "00:05",
                },
                transcript,
                "subtitle",
            )
            self.assertIn("# 测试视频", note)
            self.assertIn("第一句 第二句", note)


if __name__ == "__main__":
    unittest.main()
