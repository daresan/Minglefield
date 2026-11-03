import unittest
from pathlib import PurePosixPath

from server.platform_user_paths import PlatformPathError, user_paths


class PlatformUserPathsTests(unittest.TestCase):
    def test_windows_uses_localappdata_not_home(self):
        result = user_paths(platform="win32",
                            environ={"LOCALAPPDATA": "C:\\Users\\Shadow\\AppData\\Local"},
                            home="C:\\Users\\Other")
        self.assertEqual(str(result["install"]), "C:\\Users\\Shadow\\AppData\\Local\\Programs\\Minglefield")
        self.assertEqual(str(result["data"]), "C:\\Users\\Shadow\\AppData\\Local\\Minglefield")

    def test_windows_missing_localappdata_fails_closed(self):
        with self.assertRaises(PlatformPathError):
            user_paths(platform="win32", environ={}, home="/tmp/user")

    def test_linux_xdg(self):
        result = user_paths(platform="linux", environ={"XDG_DATA_HOME": "/var/tmp/xdg"},
                            home="/home/test")
        self.assertEqual(result["data"], PurePosixPath("/var/tmp/xdg/minglefield"))
        self.assertEqual(result["install"], PurePosixPath("/home/test/.local/opt/minglefield"))

    def test_linux_relative_xdg_rejected(self):
        with self.assertRaises(PlatformPathError):
            user_paths(platform="linux", environ={"XDG_DATA_HOME": "relative"}, home="/home/test")

    def test_macos_application_support(self):
        result = user_paths(platform="darwin", environ={}, home="/Users/test")
        self.assertEqual(result["data"], PurePosixPath("/Users/test/Library/Application Support/Minglefield"))
        self.assertEqual(result["install"], PurePosixPath("/Users/test/Applications/Minglefield.app"))

    def test_unsupported_os_rejected(self):
        with self.assertRaises(PlatformPathError):
            user_paths(platform="plan9", environ={}, home="/home/test")


if __name__ == "__main__":
    unittest.main()
