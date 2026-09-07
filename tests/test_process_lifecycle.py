import time
import subprocess
import sys
import unittest
from queue import Queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

import QualityScaler as q


def spawn_test_child(channel):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
    channel.put(child.pid)
    child.wait()


class ProcessingLifecycleTests(unittest.TestCase):
    def test_stop_reaps_a_real_owned_process(self):
        previous = q.app_state
        state = q.AppState(q.UserPreferences())
        state.info_message = Mock()
        state.event_stop_upscale_process = Event()
        state.process_status_q = Queue()
        state.video_frames_and_info_q = Queue()
        channel = q.multiprocessing_Queue()
        process = q.multiprocessing_Process(target=spawn_test_child, args=(channel,))
        process.start()
        pid = process.pid
        child_pid = channel.get(timeout=10)
        state.process_upscale_orchestrator = process
        q.app_state = state
        try:
            started = time.monotonic()
            q.stop_upscale_process()
            self.assertLess(time.monotonic() - started, 0.2)
            event = state.ui_events.get(timeout=12)
            self.assertEqual(event, ("stopped", q.STOP_STATUS))
            import psutil
            self.assertFalse(psutil.pid_exists(pid))
            self.assertFalse(psutil.pid_exists(child_pid))
        finally:
            try:
                if process.is_alive():
                    process.kill()
                    process.join(3)
                process.close()
            except ValueError:
                pass
            channel.close()
            channel.join_thread()
            q.app_state = previous

    def run_frame_worker(self, save_error=None):
        status = Queue()
        stop = Event()
        calls = []
        frame = object()
        task = SimpleNamespace(selected_AI_model="test", selected_gpu="Auto",
                               input_resize_factor=1.0, tiles_resolution=64,
                               selected_sharpening_amount=0)
        def save(*args, **kwargs):
            calls.append("saved")
            self.assertTrue(status.empty())
            if save_error:
                raise save_error
        engine = Mock()
        engine.AI_orchestration.return_value = frame
        with patch.object(q, "configure_realtime_logging"), patch.object(q, "psutil_Process"), \
             patch.object(q, "AI_upscale", return_value=engine), patch.object(q, "image_read", return_value=frame), \
             patch.object(q, "image_write", side_effect=save):
            q.upscale_video_frames_async(None, status, stop, task, [("in.jpg", "out.jpg")])
        return calls, status

    def test_frame_pixels_never_cross_ipc_and_status_follows_successful_save(self):
        calls, queue = self.run_frame_worker()
        self.assertEqual(calls, ["saved"])
        record = queue.get_nowait()
        self.assertEqual(record["upscaled_frame_path"], "out.jpg")
        self.assertNotIn("upscaled_frame", record)

    def test_save_failure_propagates_to_the_worker_owner(self):
        with self.assertRaisesRegex(OSError, "disk full"):
            self.run_frame_worker(OSError("disk full"))


if __name__ == "__main__":
    unittest.main()
