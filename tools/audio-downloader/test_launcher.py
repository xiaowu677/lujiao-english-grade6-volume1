import re
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
LAUNCHER = APP_DIR / "启动音频下载工具.cmd"


class LauncherTest(unittest.TestCase):
    def test_launcher_uses_windows_safe_encoding_and_line_endings(self):
        content = LAUNCHER.read_bytes()

        self.assertTrue(content.isascii())
        self.assertIn(b"\r\n", content)
        self.assertIsNone(re.search(rb"(?<!\r)\n", content))


if __name__ == "__main__":
    unittest.main()
