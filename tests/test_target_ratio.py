import unittest

import QualityScaler as quality_scaler


class TargetRatioDimensionsTests(unittest.TestCase):
    def test_auto_uses_sar_corrected_display_size(self):
        # 720x480 NTSC DVD flagged 4:3 (SAR 8:9) -> displayed 640x480
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(720, 480, "Auto", 8 / 9),
            (640, 480),
        )

    def test_auto_keeps_square_pixels(self):
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(1920, 1080, "Auto", 1.0),
            (1920, 1080),
        )

    def test_original_ignores_the_sar_flag(self):
        # For files whose SAR metadata is wrong: keep the stored pixels
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(720, 480, "Original", 8 / 9),
            (720, 480),
        )

    def test_forced_ratio_landscape_keeps_height(self):
        # 1920x1080 locked to 4:3 -> 1440x1080
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(1920, 1080, "4:3"),
            (1440, 1080),
        )

    def test_forced_ratio_wider_than_source(self):
        # 1440x1080 locked to 16:9 -> 1920x1080
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(1440, 1080, "16:9"),
            (1920, 1080),
        )

    def test_forced_ratio_portrait_keeps_width(self):
        # 1080x1920 portrait locked to 4:3 (i.e. 3:4) -> 1080x1440
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(1080, 1920, "4:3"),
            (1080, 1440),
        )

    def test_forced_ratio_square(self):
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(1920, 1080, "1:1"),
            (1080, 1080),
        )

    def test_forced_ratio_21_9(self):
        self.assertEqual(
            quality_scaler.get_target_ratio_dimensions(1920, 1080, "21:9"),
            (2520, 1080),
        )

    def test_odd_width_is_rounded_to_even(self):
        # 427x320 landscape locked to 16:9 -> 569x320 -> 570x320
        width, height = quality_scaler.get_target_ratio_dimensions(427, 320, "16:9")
        self.assertEqual(width % 2, 0)
        self.assertEqual((width, height), (570, 320))

    def test_odd_height_is_rounded_to_even(self):
        # 320x427 portrait locked to 16:9 (i.e. 9:16) -> 320x569 -> 320x570
        width, height = quality_scaler.get_target_ratio_dimensions(320, 427, "16:9")
        self.assertEqual(height % 2, 0)
        self.assertEqual((width, height), (320, 570))


class RatioLockFilterTests(unittest.TestCase):
    def test_no_filter_when_dimensions_already_match(self):
        self.assertEqual(
            quality_scaler.get_ratio_lock_filter(1920, 1080, 1.0, "Auto"),
            "",
        )
        self.assertEqual(
            quality_scaler.get_ratio_lock_filter(1440, 1080, 1.0, "4:3"),
            "",
        )

    def test_filter_stretches_anamorphic_source_in_auto(self):
        self.assertEqual(
            quality_scaler.get_ratio_lock_filter(720, 480, 8 / 9, "Auto"),
            "scale=640:480,setsar=1",
        )

    def test_filter_locks_16_9_on_4_3_source(self):
        self.assertEqual(
            quality_scaler.get_ratio_lock_filter(1440, 1080, 1.0, "16:9"),
            "scale=1920:1080,setsar=1",
        )

    def test_original_returns_empty_filter_even_with_sar(self):
        self.assertEqual(
            quality_scaler.get_ratio_lock_filter(720, 480, 8 / 9, "Original"),
            "",
        )


class NameSuffixRatioTests(unittest.TestCase):
    def test_auto_ratio_adds_no_tag(self):
        suffix = quality_scaler._build_name_suffix("RealESRGANx4", 0.5, 2.0, 0.3, "Auto")
        self.assertNotIn("_Ratio-", suffix)

    def test_forced_ratio_is_tagged(self):
        suffix = quality_scaler._build_name_suffix("RealESRGANx4", 0.5, 2.0, 0.3, "4:3")
        self.assertIn("_Ratio-4:3", suffix)

    def test_default_ratio_is_auto(self):
        suffix = quality_scaler._build_name_suffix("RealESRGANx4", 0.5, 2.0, 0.3)
        self.assertNotIn("_Ratio-", suffix)


class TargetRatioOptionListTests(unittest.TestCase):
    def test_option_list_order(self):
        self.assertEqual(
            quality_scaler.target_ratio_list,
            ["Auto", "Original", "1:1", "4:3", "16:9", "21:9"],
        )

    def test_forced_options_have_ratio_values(self):
        for option in ("1:1", "4:3", "16:9", "21:9"):
            self.assertIn(option, quality_scaler.TARGET_RATIOS)
        self.assertNotIn("Auto", quality_scaler.TARGET_RATIOS)
        self.assertNotIn("Original", quality_scaler.TARGET_RATIOS)


if __name__ == "__main__":
    unittest.main()
