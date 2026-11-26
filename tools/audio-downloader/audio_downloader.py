import argparse
import asyncio
import errno
import hashlib
import json
import mimetypes
import os
import sys
import threading
import time
import uuid
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from audio_catalog import COURSES, build_catalog


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]
DOWNLOADS_DIR = APP_DIR / "downloads"
PREVIEW_DIR = DOWNLOADS_DIR / "_preview"
VENDOR_PATH = REPO_ROOT / "work" / "audio-tools" / "vendor"
DEFAULT_RATE = "-8%"
DEFAULT_VOICE = "en-US-JennyNeural"
DEFAULT_PORT = 8865

if VENDOR_PATH.exists():
    sys.path.insert(0, str(VENDOR_PATH))

try:
    import edge_tts
except ImportError as error:
    raise SystemExit(
        "缺少微软语音生成组件。请确认 work/audio-tools/vendor 目录仍存在。"
    ) from error


VOICES = [
    {
        "id": "en-US-JennyNeural",
        "name": "Jenny",
        "locale": "en-US",
        "region": "美式",
        "gender": "女声",
        "recommended": True,
    },
    {
        "id": "en-US-AriaNeural",
        "name": "Aria",
        "locale": "en-US",
        "region": "美式",
        "gender": "女声",
    },
    {
        "id": "en-US-AvaNeural",
        "name": "Ava",
        "locale": "en-US",
        "region": "美式",
        "gender": "女声",
    },
    {
        "id": "en-US-GuyNeural",
        "name": "Guy",
        "locale": "en-US",
        "region": "美式",
        "gender": "男声",
    },
    {
        "id": "en-US-AndrewNeural",
        "name": "Andrew",
        "locale": "en-US",
        "region": "美式",
        "gender": "男声",
    },
    {
        "id": "en-GB-SoniaNeural",
        "name": "Sonia",
        "locale": "en-GB",
        "region": "英式",
        "gender": "女声",
    },
    {
        "id": "en-GB-LibbyNeural",
        "name": "Libby",
        "locale": "en-GB",
        "region": "英式",
        "gender": "女声",
    },
    {
        "id": "en-GB-RyanNeural",
        "name": "Ryan",
        "locale": "en-GB",
        "region": "英式",
        "gender": "男声",
    },
    {
        "id": "en-GB-ThomasNeural",
        "name": "Thomas",
        "locale": "en-GB",
        "region": "英式",
        "gender": "男声",
    },
    {
        "id": "en-AU-NatashaNeural",
        "name": "Natasha",
        "locale": "en-AU",
        "region": "澳式",
        "gender": "女声",
    },
    {
        "id": "en-AU-WilliamMultilingualNeural",
        "name": "William",
        "locale": "en-AU",
        "region": "澳式",
        "gender": "男声",
    },
]
VOICE_IDS = {voice["id"] for voice in VOICES}

CATEGORIES = {
    "word": "词条发音",
    "training": "语境训练句",
    "acceptance": "验收句",
    "story": "故事朗读",
}

JOBS = {}
JOBS_LOCK = threading.Lock()
ACTIVE_JOB_ID = None


def _course_directory(course):
    if course not in COURSES:
        raise ValueError("不支持的课程")
    if course == "grade6":
        return DOWNLOADS_DIR
    return DOWNLOADS_DIR / course


def _catalog_for_categories(categories, course):
    selected = set(categories)
    return [
        item for item in build_catalog(REPO_ROOT, course=course)
        if item["kind"] in selected
    ]


def _voice_directory(voice, course="grade6"):
    if voice not in VOICE_IDS:
        raise ValueError("不支持的微软音色")
    return _course_directory(course) / voice


def is_valid_audio(path):
    path = Path(path)
    return path.is_file() and path.stat().st_size > 500


async def _edge_synthesize(text, output_path, voice):
    communicate = edge_tts.Communicate(text, voice, rate=DEFAULT_RATE)
    output_path = Path(output_path)
    temp_path = output_path.with_name(
        f".{output_path.name}.{threading.get_ident()}.tmp"
    )
    try:
        await communicate.save(str(temp_path))
        if not is_valid_audio(temp_path):
            raise RuntimeError("微软语音返回了空音频")
        os.replace(temp_path, output_path)
    finally:
        temp_path.unlink(missing_ok=True)


async def generate_items(
    catalog,
    output_dir,
    voice,
    *,
    synthesize=None,
    concurrency=4,
    on_progress=None,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    results = []

    async def generate_one(item):
        nonlocal completed
        output_path = output_dir / item["filename"]

        if is_valid_audio(output_path):
            completed += 1
            if on_progress:
                on_progress(completed, len(catalog), item, "skipped")
            return {"status": "skipped", "id": item["id"]}

        async with semaphore:
            last_error = None
            for attempt in range(3):
                temp_path = output_dir / f".{item['id']}.{os.getpid()}.tmp.mp3"
                try:
                    if synthesize:
                        await synthesize(item["text"], temp_path)
                    else:
                        await _edge_synthesize(item["text"], temp_path, voice)
                    if not is_valid_audio(temp_path):
                        raise RuntimeError("生成的音频文件异常")
                    os.replace(temp_path, output_path)
                    completed += 1
                    if on_progress:
                        on_progress(completed, len(catalog), item, "generated")
                    return {"status": "generated", "id": item["id"]}
                except Exception as error:
                    last_error = error
                    temp_path.unlink(missing_ok=True)
                    await asyncio.sleep(1 + attempt)

        completed += 1
        if on_progress:
            on_progress(completed, len(catalog), item, "failed")
        return {
            "status": "failed",
            "id": item["id"],
            "text": item["text"],
            "error": str(last_error),
        }

    results = await asyncio.gather(*(generate_one(item) for item in catalog))
    manifest = {
        "version": 1,
        "voice": voice,
        "rate": DEFAULT_RATE,
        "count": len(catalog),
        "items": [
            {
                "id": item["id"],
                "kind": item["kind"],
                "text": item["text"],
                "file": item["filename"],
                "sources": item["sources"],
            }
            for item in catalog
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "generated": sum(result["status"] == "generated" for result in results),
        "skipped": sum(result["status"] == "skipped" for result in results),
        "failed": sum(result["status"] == "failed" for result in results),
        "failures": [result for result in results if result["status"] == "failed"],
    }


def write_archive(output_dir, archive_path):
    output_dir = Path(output_dir)
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in sorted(output_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in {".mp3", ".json"}:
                archive.write(path, arcname=path.name)
    return archive_path


def create_server(host, preferred_port, attempts=20):
    last_error = None
    for port in range(preferred_port, min(65536, preferred_port + attempts)):
        try:
            return ThreadingHTTPServer((host, port), AudioToolHandler)
        except OSError as error:
            is_port_in_use = (
                error.errno in {errno.EADDRINUSE, errno.EACCES}
                or getattr(error, "winerror", None) in {10013, 10048}
            )
            if not is_port_in_use:
                raise
            last_error = error
    raise OSError(
        f"{preferred_port} 起连续 {attempts} 个端口均被占用"
    ) from last_error


def _set_job(job_id, **updates):
    with JOBS_LOCK:
        JOBS[job_id].update(updates)


def _start_job(voice, categories, course):
    global ACTIVE_JOB_ID
    voice_dir = _voice_directory(voice, course)
    catalog = _catalog_for_categories(categories, course)
    if not catalog:
        raise ValueError("请至少选择一个生成类别")

    with JOBS_LOCK:
        if ACTIVE_JOB_ID and JOBS.get(ACTIVE_JOB_ID, {}).get("status") == "running":
            raise RuntimeError("已有一个生成任务正在进行")
        job_id = uuid.uuid4().hex
        JOBS[job_id] = {
            "id": job_id,
            "status": "running",
            "voice": voice,
            "course": course,
            "categories": list(categories),
            "total": len(catalog),
            "completed": 0,
            "generated": 0,
            "skipped": 0,
            "failed": 0,
            "current": "",
            "error": "",
            "startedAt": time.time(),
            "finishedAt": None,
        }
        ACTIVE_JOB_ID = job_id

    def on_progress(completed, total, item, status):
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["completed"] = completed
            job["total"] = total
            job["current"] = item["text"]
            if status in {"generated", "skipped", "failed"}:
                job[status] += 1

    def worker():
        global ACTIVE_JOB_ID
        try:
            result = asyncio.run(
                generate_items(
                    catalog,
                    voice_dir,
                    voice,
                    on_progress=on_progress,
                )
            )
            _set_job(
                job_id,
                status="complete",
                generated=result["generated"],
                skipped=result["skipped"],
                failed=result["failed"],
                failures=result["failures"][:20],
                finishedAt=time.time(),
            )
        except Exception as error:
            _set_job(
                job_id,
                status="failed",
                error=str(error),
                finishedAt=time.time(),
            )
        finally:
            with JOBS_LOCK:
                if ACTIVE_JOB_ID == job_id:
                    ACTIVE_JOB_ID = None

    threading.Thread(target=worker, daemon=True).start()
    return JOBS[job_id]


class AudioToolHandler(BaseHTTPRequestHandler):
    server_version = "WordQuestAudioTool/1.0"

    def log_message(self, format_string, *args):
        return

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type=None, download_name=None):
        path = Path(path)
        if not path.is_file():
            self._send_json({"error": "文件不存在"}, HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        if download_name:
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{download_name}"',
            )
        self.end_headers()
        with path.open("rb") as file:
            while chunk := file.read(64 * 1024):
                self.wfile.write(chunk)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path in {"/", "/index.html"}:
            self._send_file(APP_DIR / "index.html", "text/html; charset=utf-8")
            return

        if parsed.path == "/api/meta":
            course_stats = {}
            for course, config in COURSES.items():
                catalog = build_catalog(REPO_ROOT, course=course)
                counts = {}
                for item in catalog:
                    counts[item["kind"]] = counts.get(item["kind"], 0) + 1
                course_stats[course] = {
                    "label": config["label"],
                    "total": len(catalog),
                    "counts": counts,
                }
            self._send_json(
                {
                    "courses": course_stats,
                    "defaultCourse": "grade6",
                    "categories": CATEGORIES,
                    "voices": VOICES,
                    "defaultVoice": DEFAULT_VOICE,
                    "rate": DEFAULT_RATE,
                    "downloadsDir": str(DOWNLOADS_DIR),
                }
            )
            return

        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.removeprefix("/api/jobs/")
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if not job:
                    self._send_json(
                        {"error": "生成任务不存在"},
                        HTTPStatus.NOT_FOUND,
                    )
                    return
                snapshot = dict(job)
            self._send_json(snapshot)
            return

        if parsed.path == "/api/items":
            voice = query.get("voice", [DEFAULT_VOICE])[0]
            course = query.get("course", ["grade6"])[0]
            category = query.get("category", ["all"])[0]
            search = query.get("search", [""])[0].strip().lower()
            offset = max(0, int(query.get("offset", ["0"])[0]))
            limit = min(100, max(1, int(query.get("limit", ["50"])[0])))
            try:
                output_dir = _voice_directory(voice, course)
            except ValueError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            catalog = build_catalog(REPO_ROOT, course=course)
            if category != "all":
                catalog = [item for item in catalog if item["kind"] == category]
            if search:
                catalog = [
                    item
                    for item in catalog
                    if search in item["text"].lower()
                    or any(search in source.lower() for source in item["sources"])
                ]
            page = catalog[offset : offset + limit]
            items = [
                {
                    **item,
                    "ready": (output_dir / item["filename"]).exists(),
                }
                for item in page
            ]
            self._send_json(
                {
                    "course": course,
                    "total": len(catalog),
                    "offset": offset,
                    "items": items,
                }
            )
            return

        if parsed.path == "/api/preview":
            voice = query.get("voice", [DEFAULT_VOICE])[0]
            course = query.get("course", ["grade6"])[0]
            text = query.get("text", ["Hello, welcome to Word Quest."])[0][:500]
            try:
                _voice_directory(voice, course)
            except ValueError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            preview_dir = PREVIEW_DIR / course
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_id = hashlib.sha256(
                f"{course}\0{voice}\0{text}".encode("utf-8")
            ).hexdigest()[:16]
            preview_path = preview_dir / f"{voice}-{preview_id}.mp3"
            if not is_valid_audio(preview_path):
                preview_path.unlink(missing_ok=True)
                try:
                    asyncio.run(
                        _edge_synthesize(text, preview_path, voice)
                    )
                except Exception as error:
                    self._send_json(
                        {"error": f"试听生成失败：{error}"},
                        HTTPStatus.BAD_GATEWAY,
                    )
                    return
            self._send_file(preview_path, "audio/mpeg")
            return

        if parsed.path.startswith("/audio/"):
            parts = parsed.path.split("/", 4)
            if len(parts) != 5:
                self._send_json({"error": "无效的音频地址"}, HTTPStatus.BAD_REQUEST)
                return
            course = parts[2]
            voice = parts[3]
            filename = Path(parts[4]).name
            try:
                output_dir = _voice_directory(voice, course)
            except ValueError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_file(output_dir / filename, "audio/mpeg")
            return

        if parsed.path == "/api/archive":
            voice = query.get("voice", [DEFAULT_VOICE])[0]
            course = query.get("course", ["grade6"])[0]
            try:
                output_dir = _voice_directory(voice, course)
            except ValueError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            if not output_dir.exists():
                self._send_json({"error": "尚未生成该音色的音频"}, HTTPStatus.NOT_FOUND)
                return
            archive_path = DOWNLOADS_DIR / f"WordQuest-{course}-{voice}.zip"
            write_archive(output_dir, archive_path)
            self._send_file(archive_path, "application/zip", archive_path.name)
            return

        self._send_json({"error": "页面不存在"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if urlparse(self.path).path != "/api/generate":
            self._send_json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json_body()
            voice = payload.get("voice", DEFAULT_VOICE)
            course = payload.get("course", "grade6")
            categories = payload.get("categories", [])
            if not isinstance(categories, list):
                raise ValueError("生成类别格式错误")
            job = _start_job(voice, categories, course)
            self._send_json(job, HTTPStatus.CREATED)
        except (ValueError, RuntimeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)


def main():
    parser = argparse.ArgumentParser(description="单词星球微软语音下载工具")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    server = create_server(args.host, args.port)
    actual_port = server.server_address[1]
    url = f"http://{args.host}:{actual_port}/"
    print(f"音频下载工具已启动：{url}")
    if actual_port != args.port:
        print(f"端口 {args.port} 已被占用，已自动改用 {actual_port}。")
    print("关闭此窗口即可停止工具。")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
