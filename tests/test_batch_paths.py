import os
import tempfile
import unittest

import QualityScaler as quality_scaler


class BatchPathTests(unittest.TestCase):
    def test_discovers_supported_files_recursively_in_path_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = os.path.join(directory, "input")
            os.makedirs(os.path.join(root, "Season 02"))
            os.makedirs(os.path.join(root, "Season 01"))
            paths = [
                os.path.join(root, "cover.PNG"),
                os.path.join(root, "Season 01", "episode.mp4"),
                os.path.join(root, "Season 02", "notes.txt"),
                os.path.join(root, "Season 02", "episode.jpg.bak"),
            ]
            for path in paths:
                with open(path, "wb") as file:
                    file.write(b"test")

            self.assertEqual(
                quality_scaler.discover_supported_files(root),
                [
                    os.path.join(root, "cover.PNG"),
                    os.path.join(root, "Season 01", "episode.mp4"),
                ],
            )

    def test_selected_output_folder_preserves_source_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = os.path.join(directory, "input")
            source_path = os.path.join(source_root, "Season 01", "episode.mp4")
            output_root = os.path.join(directory, "output")

            self.assertEqual(
                quality_scaler._build_output_path_base(
                    source_path,
                    output_root,
                    source_root=source_root,
                ),
                os.path.join(output_root, "Season 01", "episode"),
            )

    def test_video_frame_outputs_are_separate_from_raw_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            work_directory = os.path.join(directory, "episode_RealESRGANx4_InputR50_OutputR100")
            raw_frame_path = os.path.join(work_directory, "Raw", "frame_001.jpg")

            self.assertEqual(
                quality_scaler.build_upscaled_frame_path(
                    raw_frame_path,
                    os.path.join(work_directory, "Upscale"),
                    "RealESRGANx4",
                    0.5,
                    1.0,
                    0,
                ),
                os.path.join(
                    work_directory,
                    "Upscale",
                    "frame_001_RealESRGANx4_InputR-50_OutputR-100.jpg",
                ),
            )


if __name__ == "__main__":
    unittest.main()
