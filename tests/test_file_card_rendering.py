import unittest

import QualityScaler as quality_scaler


class FakeFileWidget:
    def __init__(self, file_count):
        self.file_list = [f"file-{index}" for index in range(file_count)]
        self.ui_components = []
        self.rendered = []
        self.idle_callbacks = []

    def _create_file_card(self, file_path):
        self.rendered.append(file_path)
        return {"file_path": file_path}

    def after_idle(self, callback):
        self.idle_callbacks.append(callback)


class FileCardRenderingTests(unittest.TestCase):
    def test_large_file_list_yields_between_card_batches(self):
        widget = FakeFileWidget(file_count=10)

        quality_scaler.FileWidget._render_cards(widget)

        self.assertLess(len(widget.rendered), len(widget.file_list))
        self.assertEqual(len(widget.idle_callbacks), 1)

        while widget.idle_callbacks:
            widget.idle_callbacks.pop(0)()

        self.assertEqual(widget.rendered, widget.file_list)
        self.assertEqual(len(widget.ui_components), len(widget.file_list))


if __name__ == "__main__":
    unittest.main()
