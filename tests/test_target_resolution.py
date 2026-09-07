import unittest
from unittest.mock import patch

import QualityScaler as quality_scaler


class FakeProbeProcess:
    def __init__(self, output: bytes):
        self._output = output

    def communicate(self, timeout=None):
        return self._output, b""


class CalculateOutputFactorForTargetTests(unittest.TestCase):
    def test_landscape_video_matches_target_on_height(self):
        # 640x480 (4:3) + 4x model -> 2560x1920, 1080p preset -> 1440x1080
        factor = quality_scaler.calculate_output_factor_for_target(
            source_width=640,
            source_height=480,
            input_resize_factor=1.0,
            upscale_factor=4,
            target_size=1080,
        )

        self.assertEqual(factor, 0.5625)
        self.assertEqual((round(2560 * factor), round(1920 * factor)), (1440, 1080))

    def test_portrait_video_matches_target_on_width(self):
        # 480x640 portrait + 4x model -> 1920x2560, 1080p preset -> 1080x1440
        factor = quality_scaler.calculate_output_factor_for_target(
            source_width=480,
            source_height=640,
            input_resize_factor=1.0,
            upscale_factor=4,
            target_size=1080,
        )

        self.assertEqual(factor, 0.5625)
        self.assertEqual((round(1920 * factor), round(2560 * factor)), (1080, 1440))

    def test_landscape_16_9_matches_4k_preset_on_height(self):
        factor = quality_scaler.calculate_output_factor_for_target(
            source_width=1920,
            source_height=1080,
            input_resize_factor=1.0,
            upscale_factor=2,
            target_size=2160,
        )

        self.assertEqual((round(3840 * factor), round(2160 * factor)), (3840, 2160))

    def test_custom_aspect_ratio_preserved_for_portrait(self):
        # 900x1200 (3:4) + 4x model -> 3600x4800, 2K preset (1440) -> 1440x1920
        factor = quality_scaler.calculate_output_factor_for_target(
            source_width=900,
            source_height=1200,
            input_resize_factor=1.0,
            upscale_factor=4,
            target_size=1440,
        )

        self.assertEqual((round(3600 * factor), round(4800 * factor)), (1440, 1920))

    def test_input_resize_factor_is_part_of_the_chain(self):
        factor = quality_scaler.calculate_output_factor_for_target(
            source_width=1920,
            source_height=1080,
            input_resize_factor=0.5,
            upscale_factor=4,
            target_size=2160,
        )

        # 1080 * 0.5 * 4 = 2160 -> no extra output scaling needed
        self.assertEqual(factor, 1.0)

    def test_invalid_inputs_return_identity_factor(self):
        self.assertEqual(
            quality_scaler.calculate_output_factor_for_target(0, 0, 1.0, 4, 1080), 1.0
        )
        self.assertEqual(
            quality_scaler.calculate_output_factor_for_target(640, 480, 1.0, 4, 0), 1.0
        )


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
