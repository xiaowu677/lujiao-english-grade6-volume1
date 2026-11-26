import asyncio
import socket
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from audio_catalog import build_catalog
from audio_downloader import (
    _edge_synthesize,
    create_server,
    generate_items,
    is_valid_audio,
    write_archive,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class AudioServerTest(unittest.TestCase):
    def test_server_moves_to_the_next_port_when_preferred_port_is_busy(self):
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            occupied.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_EXCLUSIVEADDRUSE,
                1,
            )
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        preferred_port = occupied.getsockname()[1]

        try:
            server = create_server("127.0.0.1", preferred_port, attempts=10)
            try:
                self.assertNotEqual(server.server_address[1], preferred_port)
                self.assertGreater(server.server_address[1], preferred_port)
            finally:
                server.server_close()
        finally:
            occupied.close()

    def test_audio_cache_only_accepts_non_empty_mp3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "speech.mp3"
            target.write_bytes(b"")
            self.assertFalse(is_valid_audio(target))
            target.write_bytes(b"ID3" + b"\0" * 600)
            self.assertTrue(is_valid_audio(target))

    def test_edge_synthesis_never_keeps_empty_audio(self):
        class EmptyCommunicate:
            def __init__(self, text, voice, rate):
                self.output_path = None

            async def save(self, output_path):
                Path(output_path).write_bytes(b"")

        class ValidCommunicate:
            def __init__(self, text, voice, rate):
                self.output_path = None

            async def save(self, output_path):
                Path(output_path).write_bytes(b"ID3" + b"\0" * 600)

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "speech.mp3"
            with patch("audio_downloader.edge_tts.Communicate", EmptyCommunicate):
                with self.assertRaises(RuntimeError):
                    asyncio.run(
                        _edge_synthesize(
                            "test",
                            target,
                            "en-US-JennyNeural",
                        )
                    )
            self.assertFalse(target.exists())

            with patch("audio_downloader.edge_tts.Communicate", ValidCommunicate):
                asyncio.run(
                    _edge_synthesize(
                        "test",
                        target,
                        "en-US-JennyNeural",
                    )
                )
            self.assertGreater(target.stat().st_size, 500)

    def test_generation_writes_audio_and_skips_existing_files(self):
        catalog = build_catalog(REPO_ROOT)[:3]

        async def fake_synthesize(text, output_path):
            output_path.write_bytes(b"ID3" + b"\0" * 600 + text.encode("utf-8"))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            first = asyncio.run(
                generate_items(
                    catalog,
                    output_dir,
                    "en-US-JennyNeural",
                    synthesize=fake_synthesize,
                )
            )
            second = asyncio.run(
                generate_items(
                    catalog,
                    output_dir,
                    "en-US-JennyNeural",
                    synthesize=fake_synthesize,
                )
            )

            self.assertEqual(first["generated"], 3)
            self.assertEqual(first["skipped"], 0)
            self.assertEqual(second["generated"], 0)
            self.assertEqual(second["skipped"], 3)
            self.assertTrue((output_dir / "manifest.json").exists())
            for item in catalog:
                self.assertTrue((output_dir / item["filename"]).exists())

    def test_archive_contains_audio_and_manifest(self):
        catalog = build_catalog(REPO_ROOT)[:2]

        async def fake_synthesize(text, output_path):
            output_path.write_bytes(b"ID3" + b"\0" * 600 + text.encode("utf-8"))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "en-US-JennyNeural"
            archive_path = root / "voice.zip"
            asyncio.run(
                generate_items(
                    catalog,
                    output_dir,
                    "en-US-JennyNeural",
                    synthesize=fake_synthesize,
                )
            )
            write_archive(output_dir, archive_path)

            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())

            self.assertIn("manifest.json", names)
            for item in catalog:
                self.assertIn(item["filename"], names)


if __name__ == "__main__":
    unittest.main()
