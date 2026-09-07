import time
import unittest
from concurrent.futures import Future
from queue import Queue
from threading import Event
from unittest.mock import patch

import QualityScaler as q


class DeferredJobs:
    def __init__(self):
        self.calls = []

    def submit(self, function, *args):
        future = Future()
        self.calls.append((function, args, future))
        return future

    def close(self):
        for _, _, future in self.calls:
            future.cancel()


class GuiResponsivenessTests(unittest.TestCase):
    def setUp(self):
        self.old_state = q.app_state
        self.root = q.CTk()
        self.root.withdraw()
        self.root.geometry("1100x850")
        for size in (8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24):
            setattr(q, f"bold{size}", q.CTkFont(size=size))
        for name in ("clear_icon", "logo_git", "logo_telegram", "log_icon", "stop_icon", "upscale_icon", "info_icon"):
            setattr(q, name, None)
        state = q.AppState(q.UserPreferences())
        state.window = self.root
        state.info_message = q.StringVar(master=self.root, value="Ready")
        state.selected_input_resize_factor = q.StringVar(master=self.root, value="50")
        state.selected_output_resize_factor = q.StringVar(master=self.root, value="100")
        state.selected_output_path = q.StringVar(master=self.root, value=q.OUTPUT_PATH_CODED)
        state.selected_VRAM_limiter = q.StringVar(master=self.root, value="4")
        state.selected_video_codec = q.StringVar(master=self.root, value=state.preferences.video_codec)
        state.ui_jobs = DeferredJobs()
        state.process_status_q = Queue()
        state.video_frames_and_info_q = Queue()
        state.event_stop_upscale_process = Event()
        q.app_state = state
        self.widget = None

    def tearDown(self):
        if q.app_state.ui_closed:
            q.app_state = self.old_state
            return
        if q.app_state.refresh_timer is not None:
            self.root.after_cancel(q.app_state.refresh_timer)
        if self.widget is not None and self.widget.winfo_exists():
            self.widget.destroy()
        q.cancel_tk_callbacks(self.root)
        self.root.destroy()
        q.app_state = self.old_state

    def make_widget(self, count):
        paths = [f"video-{index}.mp4" for index in range(count)]
        q.app_state.selected_file_list = paths
        self.widget = q.FileWidget(self.root, paths, 4, 50, 100)
        q.app_state.file_widget = self.widget
        self.widget.pack(fill="both", expand=True)
        self.root.update()
        return self.widget

    def pump(self, duration=0.12):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.002)

    def test_thousand_files_only_create_a_window_of_cards(self):
        widget = self.make_widget(1000)
        self.assertEqual(len(widget.ui_components), q.FileWidget.WINDOW_SIZE)
        self.assertEqual(len(widget.file_list), 1000)
        self.pump()
        self.assertLessEqual(len(widget.pending_media), 2)
        self.assertTrue(all(not item["loaded"] for item in widget.ui_components))

    def test_full_app_reuses_action_button_and_empty_panel(self):
        with patch.object(q.App, "_load_widgets", None, create=True), \
             patch.object(q.App, "_action_button", None, create=True):
            q.App(self.root)
            self.root.update()
            button = q.App._action_button
            panel = q.App._load_widgets
            child_count = len(self.root.winfo_children())
            for _ in range(10):
                q.App.place_stop_button()
                q.App.place_upscale_button()
                q.App.place_loadFile_section()
            self.assertIs(q.App._action_button, button)
            self.assertIs(q.App._load_widgets, panel)
            self.assertEqual(len(self.root.winfo_children()), child_count)

    def test_remove_preserves_other_cards_and_event_loop_with_slow_preview(self):
        widget = self.make_widget(20)
        self.pump()
        survivors = {item["file_path"]: item["card"] for item in widget.ui_components}
        removed = widget.file_list[2]
        widget._remove_file(removed)
        self.root.update()
        self.assertNotIn(removed, widget.file_list)
        for item in widget.ui_components:
            if item["file_path"] in survivors:
                self.assertIs(item["card"], survivors[item["file_path"]])
        fired = []
        self.root.after(1, lambda: fired.append(True))
        self.pump(0.03)
        self.assertEqual(fired, [True])

    def test_scroll_reaches_late_files_without_materializing_entire_list(self):
        widget = self.make_widget(1000)
        widget._parent_canvas.yview_moveto(0.8)
        self.pump()
        self.assertGreater(widget._visible_start, 700)
        self.assertLessEqual(len(widget.ui_components), widget.WINDOW_SIZE)

    def test_loaded_preview_updates_existing_labels_and_ratio(self):
        widget = self.make_widget(3)
        self.pump()
        data = dict(key=("video-0.mp4", 1), is_video=True, width=1920, height=1080,
                    frames=1500, fps=25.0, sar=1.0, icon=None)
        widget.pending_media["video-0.mp4"].set_result(data)
        self.pump()
        item = next(item for item in widget.ui_components if item["file_path"] == "video-0.mp4")
        labels = tuple(item["pipeline"])
        q.app_state.preferences.target_ratio = "4:3"
        widget.refresh_pipeline()
        self.assertEqual(item["width"], 1440)
        self.assertEqual(tuple(item["pipeline"]), labels)
        self.assertIn("1440×1080", item["meta_label"].cget("text"))

    def test_failed_preview_does_not_stop_other_items_and_can_retry(self):
        widget = self.make_widget(3)
        self.pump()
        widget.pending_media["video-0.mp4"].set_exception(ValueError("broken video"))
        self.pump()
        item = next(item for item in widget.ui_components if item["file_path"] == "video-0.mp4")
        self.assertTrue(item["error"])
        self.assertIn("video-2.mp4", widget.pending_media)
        widget._retry_preview("video-0.mp4")
        self.assertFalse(item["error"])

    def test_input_change_when_target_off_still_schedules_one_refresh(self):
        widget = self.make_widget(2)
        q.app_state.preferences.target_resolution = "OFF"
        for _ in range(5):
            q.update_output_scale_for_target_resolution()
        with patch.object(widget, "refresh_pipeline") as refresh:
            self.pump(0.25)
        self.assertEqual(refresh.call_count, 1)

    def test_clean_is_disabled_during_active_job(self):
        widget = self.make_widget(2)
        q.app_state.process_upscale_orchestrator = object()
        widget._destroy_()
        self.assertTrue(widget.winfo_exists())
        self.assertEqual(len(widget.file_list), 2)
        q.app_state.process_upscale_orchestrator = None

    def test_completion_uses_job_snapshot_even_if_controls_change(self):
        widget = self.make_widget(2)
        config = q.build_processing_config()
        self.assertIsNotNone(config)
        source_key = ("video-0.mp4", 123)
        widget.media_data["video-0.mp4"] = dict(key=source_key)
        old_key = q._completed_video_key("video-0.mp4")
        q.app_state.active_config = config
        q.app_state.selected_output_path.set("D:/another-output")
        q.app_state.preferences.target_ratio = "4:3"
        q.handle_ui_event("file_completed", dict(path="video-0.mp4", source_key=source_key))
        self.assertIn(old_key, q.app_state.completed_video_files)
        self.assertNotIn(q._completed_video_key("video-0.mp4"), q.app_state.completed_video_files)

    def test_stop_returns_without_sleeping_on_ui_thread(self):
        self.make_widget(2)
        started = time.monotonic()
        q.stop_upscale_process()
        self.assertLess(time.monotonic() - started, 0.2)
        kind, reason = q.app_state.ui_events.get(timeout=2)
        self.assertEqual((kind, reason), ("stopped", q.STOP_STATUS))
        self.assertTrue(q.app_state.event_stop_upscale_process.is_set())

    def test_close_finishes_cleanup_before_destroying_tk(self):
        self.make_widget(5)
        q.app_state.process_log_q = Queue()
        with patch.object(q, "save_user_choices_in_json"):
            q.on_app_close()
        self.assertTrue(self.root.winfo_exists())
        kind, reason = q.app_state.ui_events.get(timeout=2)
        with patch.object(q, "allow_sleep"):
            q.handle_ui_event(kind, reason)
        self.assertTrue(q.app_state.ui_closed)

    def test_log_render_appends_and_trims_without_replacing_unchanged_lines(self):
        from types import SimpleNamespace
        textbox = q.CTkTextbox(self.root)
        view = SimpleNamespace(textbox=textbox)
        buffer = q.app_state.log_buffer
        buffer.set_limit(3)
        buffer.append("one")
        buffer.append("two")
        q.RealtimeLogWindow.render(view)
        buffer.append("three")
        with patch.object(textbox, "delete", wraps=textbox.delete) as delete:
            q.RealtimeLogWindow.render(view)
            delete.assert_not_called()
        buffer.append("four")
        q.RealtimeLogWindow.render(view)
        self.assertEqual(textbox.get("1.0", "end-1c"), "two\nthree\nfour\n")
        buffer.clear()
        q.RealtimeLogWindow.render(view)
        self.assertEqual(textbox.get("1.0", "end-1c"), "")
        textbox.destroy()


if __name__ == "__main__":
    unittest.main()
