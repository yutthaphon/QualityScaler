import unittest
import tempfile
from pathlib import Path
import numpy as np
from queue import Full
from threading import Event
from unittest.mock import Mock, patch

import QualityScaler as q
from quality_scaler_runtime import BackgroundJobs, FileLRU, atomic_destination


class RuntimeTests(unittest.TestCase):
    def test_real_extreme_aspect_image_preview_has_nonzero_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "thin.png")
            q.image_write(path, np.zeros((1, 5000, 3), dtype=np.uint8), file_extension=".png")
            preview = q.load_media_preview(path)
            self.assertEqual((preview["width"], preview["height"]), (5000, 1))
            self.assertEqual(preview["icon"].size, (60, 1))

    def test_tile_accumulation_matches_reference_pixels(self):
        engine = q.AI_upscale.__new__(q.AI_upscale)
        engine.upscale_factor = 2
        engine.tiles_resolution = 8
        pixels = np.random.default_rng(123).integers(0, 256, (19, 23, 3), dtype=np.uint8)
        engine.AI_upscale = lambda tile: np.repeat(np.repeat(tile, 2, axis=0), 2, axis=1)
        expected = engine.AI_upscale(pixels)
        actual = engine.AI_upscale_with_tilling(pixels)
        np.testing.assert_array_equal(actual, expected)

    def test_atomic_output_preserves_previous_file_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.jpg"
            path.write_bytes(b"complete frame")
            with self.assertRaises(OSError):
                with atomic_destination(path) as temporary:
                    Path(temporary).write_bytes(b"partial")
                    raise OSError("disk failure")
            self.assertEqual(path.read_bytes(), b"complete frame")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_cache_is_bounded_replaces_versions_and_keeps_recent(self):
        cache = FileLRU(limit=2)
        cache[("a", 1)] = 1
        cache[("b", 1)] = 2
        self.assertEqual(cache[("a", 1)], 1)
        cache[("c", 1)] = 3
        self.assertNotIn(("b", 1), cache)
        cache[("a", 2)] = 4
        self.assertNotIn(("a", 1), cache)
        self.assertEqual(len(cache), 2)
        cache.clear()
        self.assertEqual(cache._paths, {})

    def test_background_queue_is_bounded_and_cancels_pending_on_close(self):
        entered, release = Event(), Event()
        jobs = BackgroundJobs(workers=1, capacity=1)
        def slow():
            entered.set()
            release.wait(2)
        try:
            running = jobs.submit(slow)
            self.assertTrue(entered.wait(1))
            pending = jobs.submit(lambda: 2)
            with self.assertRaises(Full):
                jobs.submit(lambda: 3)
            jobs.close()
            self.assertTrue(pending.cancelled())
        finally:
            release.set()
            jobs.close()
        running.result(timeout=2)

    def test_probe_timeout_kills_and_reaps_process(self):
        process = Mock()
        process.communicate.side_effect = [q.subprocess_TimeoutExpired("probe", 1), (b"", b"")]
        with self.assertRaises(q.subprocess_TimeoutExpired):
            q.communicate_with_cleanup(process, 1)
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.call_count, 2)

    def test_failed_image_encoding_is_reported(self):
        with patch.object(q, "opencv_imencode", return_value=(False, None)):
            with self.assertRaises(OSError):
                q.image_write("unused.jpg", None)

    def test_duration_carries_seconds_into_minutes(self):
        self.assertIn("1m 0s", q.FileWidget._format_source_meta(None, True, 10, 10, 1499, 25))


if __name__ == "__main__":
    unittest.main()
