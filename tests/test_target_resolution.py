import unittest
from unittest.mock import patch

import QualityScaler as quality_scaler


class FakeProbeProcess:
    def __init__(self, output: bytes):
        self._output = output

    def communicate(self, timeout=None):
        return self._output, b""


class SquarePixelHelpersTests(unittest.TestCase):
    def test_ntsc_dvd_storage_size_becomes_display_4_3(self):
        self.assertEqual(
            quality_scaler.get_square_pixel_dimensions(720, 480, 8 / 9), (640, 480)
        )

    def test_anamorphic_hd_size_becomes_display_16_9(self):
        self.assertEqual(
            quality_scaler.get_square_pixel_dimensions(1440, 1080, 4 / 3), (1920, 1080)
        )

    def test_square_pixels_are_left_untouched(self):
        self.assertEqual(
            quality_scaler.get_square_pixel_dimensions(720, 480, 1.0), (720, 480)
        )

    def test_unknown_aspect_ratio_is_treated_as_square(self):
        self.assertEqual(
            quality_scaler.get_square_pixel_dimensions(720, 480, 0.0), (720, 480)
        )

    def test_odd_display_width_is_rounded_to_even(self):
        width, _height = quality_scaler.get_square_pixel_dimensions(701, 480, 8 / 9)
        self.assertEqual(width % 2, 0)

    def test_filter_is_empty_for_square_pixels(self):
        self.assertEqual(quality_scaler.get_square_pixel_filter(720, 480, 1.0), "")

    def test_filter_stretches_anamorphic_frames(self):
        self.assertEqual(
            quality_scaler.get_square_pixel_filter(720, 480, 8 / 9),
            "scale=640:480,setsar=1",
        )


class VideoFrameExtractionCommandTests(unittest.TestCase):
    def test_extraction_without_anamorphic_correction_keeps_fps_only(self):
        command = quality_scaler.build_video_frame_extraction_command(
            "source.vob", "frames/frame_%03d.jpg", 25.0
        )

        self.assertEqual(command[command.index("-vf") + 1], "fps=25.0")

    def test_extraction_applies_square_pixel_filter_before_fps(self):
        command = quality_scaler.build_video_frame_extraction_command(
            "source.vob",
            "frames/frame_%03d.jpg",
            25.0,
            "scale=640:480,setsar=1",
        )

        self.assertEqual(command[command.index("-vf") + 1], "scale=640:480,setsar=1,fps=25.0")


class SampleAspectRatioProbeTests(unittest.TestCase):
    def run_probe(self, output: bytes):
        return quality_scaler.get_video_sample_aspect_ratio("source.vob")

    def test_anamorphic_sar_is_parsed(self):
        with patch.object(quality_scaler, "subprocess_Popen", return_value=FakeProbeProcess(b"8:9\n")):
            self.assertAlmostEqual(self.run_probe(b"8:9"), 8 / 9)

    def test_square_sar_returns_one(self):
        with patch.object(quality_scaler, "subprocess_Popen", return_value=FakeProbeProcess(b"1:1\n")):
            self.assertEqual(self.run_probe(b"1:1"), 1.0)

    def test_unspecified_sar_returns_one(self):
        with patch.object(quality_scaler, "subprocess_Popen", return_value=FakeProbeProcess(b"N/A, 0:1\n")):
            self.assertEqual(self.run_probe(b"N/A"), 1.0)

    def test_probe_failure_returns_one(self):
        with patch.object(quality_scaler, "subprocess_Popen", side_effect=OSError("no ffprobe")):
            self.assertEqual(self.run_probe(b""), 1.0)


if __name__ == "__main__":
    unittest.main()
