import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import QualityScaler as quality_scaler


class MediaPropertiesCacheTests(unittest.TestCase):
    def setUp(self):
        quality_scaler.MEDIA_PROPERTIES_CACHE.clear()
        quality_scaler.FILE_ICON_CACHE.clear()

    def test_second_read_is_served_from_cache(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as file:
            file_path = file.name
        self.addCleanup(os.remove, file_path)

        reader = MagicMock(return_value=(False, 100, 100, 0, 0.0))
        with patch.object(quality_scaler, "read_media_properties", reader):
            quality_scaler.read_media_properties_cached(file_path)
            quality_scaler.read_media_properties_cached(file_path)

        self.assertEqual(reader.call_count, 1)

    def test_modified_file_is_read_again(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as file:
            file_path = file.name
        self.addCleanup(os.remove, file_path)

        reader = MagicMock(return_value=(False, 100, 100, 0, 0.0))
        with patch.object(quality_scaler, "read_media_properties", reader):
            quality_scaler.read_media_properties_cached(file_path)
            # Simulate the file being overwritten: bump mtime into the future
            stamp = os.path.getmtime(file_path) + 100
            os.utime(file_path, (stamp, stamp))
            quality_scaler.read_media_properties_cached(file_path)

        self.assertEqual(reader.call_count, 2)
        # The stale entry must not linger in the cache
        self.assertEqual(len(quality_scaler.MEDIA_PROPERTIES_CACHE), 1)

    def test_stale_thumbnail_entry_is_replaced(self):
        quality_scaler.FILE_ICON_CACHE[("video.mp4", 1.0)] = "old-icon"
        quality_scaler.FILE_ICON_CACHE[("video.mp4", 2.0)] = "new-icon"

        with patch.object(quality_scaler, "os_path_getmtime", return_value=2.0):
            icon = quality_scaler.get_file_icon_cached("video.mp4")

        self.assertEqual(icon, "new-icon")
        self.assertEqual(list(quality_scaler.FILE_ICON_CACHE), [("video.mp4", 2.0)])

    def test_unreadable_file_uses_zero_mtime_key(self):
        with patch.object(quality_scaler, "os_path_getmtime", side_effect=OSError):
            key = quality_scaler.get_file_cache_key("missing.mp4")

        self.assertEqual(key, ("missing.mp4", 0.0))


if __name__ == "__main__":
    unittest.main()
