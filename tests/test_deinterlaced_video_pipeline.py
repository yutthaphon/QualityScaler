import io
import os
import tempfile
import unittest
from collections import deque
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

    def test_lossless_intermediate_command_reports_processed_frames(self):
        command = quality_scaler.build_deinterlaced_video_command(
            "source.vob",
            "Deinterlaced.mkv",
            quality_scaler.DEINTERLACE_FILTERS["IVTC"],
        )

        self.assertEqual(command[command.index("-progress") + 1], "pipe:1")

    def test_cuda_intermediate_command_downloads_deinterlaced_frames(self):
        command = quality_scaler.build_deinterlaced_video_command(
            "source.vob",
            "Deinterlaced.mkv",
            "bwdif_cuda=mode=send_frame:parity=auto:deint=all",
            use_cuda=True,
        )

        self.assertEqual(command[command.index("-hwaccel") + 1], "cuda")
        self.assertEqual(command[command.index("-hwaccel_output_format") + 1], "cuda")
        self.assertEqual(
            command[command.index("-vf") + 1],
            "bwdif_cuda=mode=send_frame:parity=auto:deint=all,hwdownload,format=nv12",
        )

    @patch.object(quality_scaler, "is_video_interlaced", return_value=True)
    def test_auto_mode_uses_cuda_bwdif_when_requested(self, _is_video_interlaced):
        deinterlace_filter = quality_scaler.get_deinterlace_filter(
            "Auto",
            "source.vob",
            use_cuda=True,
        )

        self.assertEqual(
            deinterlace_filter,
            "bwdif_cuda=mode=send_frame:parity=auto:deint=all",
        )

    def test_ivtc_remains_cpu_filter_when_cuda_is_requested(self):
        deinterlace_filter = quality_scaler.get_deinterlace_filter(
            "IVTC",
            "source.vob",
            use_cuda=True,
        )

        self.assertEqual(
            deinterlace_filter,
            "fieldmatch=mode=pcn_ub:combmatch=full,yadif=deint=interlaced,decimate",
        )

    def test_ffmpeg_error_reader_keeps_the_latest_error_lines(self):
        errors = deque(maxlen=2)

        quality_scaler.collect_ffmpeg_errors(
            io.BytesIO(b"first failure\nsecond failure\nthird failure\n"),
            errors,
        )

        self.assertEqual(list(errors), ["second failure", "third failure"])


if __name__ == "__main__":
    unittest.main()
