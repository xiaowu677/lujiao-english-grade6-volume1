import asyncio
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "audio-downloader"))

from audio_catalog import build_catalog  # noqa: E402
from audio_downloader import generate_items  # noqa: E402


VOICE = "en-GB-SoniaNeural"
TARGET = (
    REPO_ROOT
    / "outputs"
    / "assets"
    / "audio"
    / "g7-v1"
    / VOICE
)


async def main():
    catalog = build_catalog(REPO_ROOT, course="grade7")

    def on_progress(done, total, item, status):
        if done == 1 or done == total or done % 25 == 0:
            print(
                f"[{done}/{total}] {status}: {item['kind']} {item['text'][:60]}",
                flush=True,
            )

    result = await generate_items(
        catalog,
        TARGET,
        VOICE,
        concurrency=6,
        on_progress=on_progress,
    )
    print(result, flush=True)
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
