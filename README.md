# bilibili-video-notes-tool
一个用于提取哔哩哔哩视频学习资料的 Python CLI 工具。支持获取视频元数据、下载公开视频字幕、仅下载音频、调用本地 faster-whisper 进行 ASR 转写，并可生成 Markdown 学习笔记草稿。默认优先使用 Bilibili 公共 API，失败时可通过 yt-dlp 和浏览器 cookies 回退处理。适合课程学习、视频资料整理、Obsidian 笔记流和个人知识库构建。
