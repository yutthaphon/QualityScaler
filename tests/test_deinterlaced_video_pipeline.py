import os
import tempfile
import unittest
from unittest.mock import patch

import QualityScaler as quality_scaler


class DeinterlacedVideoPipelineTests(unittest.TestCase):
    def create_task(self, directory, selected_deinterlace):
        return quality_scaler.VideoUpscaleTask(
            video_path=os.path.join(directory, "source.vob"),
            selected_output_path=directory,
            selected_AI_model="RealESRGANx4",
            selected_AI_multithreading=1,
            selected_gpu="0",
            tiles_resolution=1024,
            input_resize_factor=1.0,
            output_resize_factor=1.0,
            selected_sharpening_amount=0.0,
            selected_video_extension=".mkv",
            selected_video_codec="x264",
            selected_deinterlace=selected_deinterlace,
        )

    def test_deinterlace_modes_do_not_share_raw_frame_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(quality_scaler, "get_video_fps", return_value=29.97):
                off_task = self.create_task(directory, "OFF")
                ivtc_task = self.create_task(directory, "IVTC")

        self.assertNotEqual(off_task.raw_frames_directory, ivtc_task.raw_frames_directory)

    def test_manual_filter_extracts_frames_from_lossless_intermediate_video(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = os.path.join(directory, "source.vob")
            work_directory = os.path.join(directory, "source_work")

            frame_source = quality_scaler.get_video_frame_source(
                source_path,
                work_directory,
                quality_scaler.DEINTERLACE_FILTERS["IVTC"],
            )

        self.assertEqual(frame_source, os.path.join(work_directory, "Deinterlaced.mkv"))

    def test_lossless_intermediate_command_applies_the_selected_filter(self):
        command = quality_scaler.build_deinterlaced_video_command(
            "source.vob",
            "Deinterlaced.mkv",
            quality_scaler.DEINTERLACE_FILTERS["IVTC"],
        )

        self.assertEqual(command[command.index("-i") + 1], "source.vob")
        self.assertEqual(command[command.index("-vf") + 1], quality_scaler.DEINTERLACE_FILTERS["IVTC"])
        self.assertEqual(command[command.index("-c:v") + 1], "ffv1")
        self.assertEqual(command[-1], "Deinterlaced.mkv")


if __name__ == "__main__":
    unittest.main()
