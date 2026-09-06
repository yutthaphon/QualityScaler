from io import StringIO
from queue import Queue

import unittest

import QualityScaler as quality_scaler


class RealtimeLogBufferTests(unittest.TestCase):
    def test_discards_oldest_entries_at_selected_limit(self):
        buffer = quality_scaler.RealtimeLogBuffer(limit=3)

        for entry in ("extracting", "upscaling", "encoding", "complete"):
            buffer.append(entry)

        self.assertEqual(buffer.entries(), ("upscaling", "encoding", "complete"))

    def test_reducing_limit_keeps_the_newest_entries(self):
        buffer = quality_scaler.RealtimeLogBuffer(limit=5)
        for entry in ("one", "two", "three", "four"):
            buffer.append(entry)

        buffer.set_limit(2)

        self.assertEqual(buffer.entries(), ("three", "four"))

    def test_clear_removes_all_visible_entries(self):
        buffer = quality_scaler.RealtimeLogBuffer(limit=2)
        buffer.append("extracting")
        buffer.append("upscaling")

        buffer.clear()

        self.assertEqual(buffer.entries(), ())

    def test_writer_forwards_complete_lines_to_the_log_queue(self):
        terminal_output = StringIO()
        log_queue = Queue()
        writer = quality_scaler.RealtimeLogWriter(terminal_output, log_queue)

        writer.write("Upscaling")
        writer.write(" video\n")

        self.assertEqual(terminal_output.getvalue(), "Upscaling video\n")
        self.assertEqual(log_queue.get_nowait(), "Upscaling video")


if __name__ == "__main__":
    unittest.main()
