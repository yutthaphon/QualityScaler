"""Interactive synthetic GUI check; does not read videos or write preferences.

Run from the repository root: python tools/gui_smoke.py
"""
import sys
from pathlib import Path
from queue import Queue

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import QualityScaler as q
from PIL import Image


def main():
    root = q.CTk()
    root.title("QualityScaler - synthetic GUI smoke")
    root.geometry("650x900")
    for size in (8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24):
        setattr(q, f"bold{size}", q.CTkFont(family="Segoe UI", size=size, weight="bold"))
    q.clear_icon = None
    state = q.AppState(q.UserPreferences())
    state.window = root
    state.info_message = q.StringVar(master=root, value="Synthetic preview")
    state.selected_input_resize_factor = q.StringVar(master=root, value="50")
    state.selected_output_resize_factor = q.StringVar(master=root, value="100")
    state.selected_output_path = q.StringVar(master=root, value=q.OUTPUT_PATH_CODED)
    state.ui_jobs = q.BackgroundJobs()
    state.process_status_q = Queue()
    q.app_state = state
    def preview(path):
        return dict(key=(path, 1), is_video=True, width=1920, height=1080, frames=1500,
                    fps=25.0, sar=1.0, icon=Image.new("RGB", (60, 34), "#438568"))
    q.load_media_preview = preview
    q.scan_resume_progress = lambda directory: 42
    state.selected_file_list = [f"Sample video {number:04d}.mp4" for number in range(1000)]
    widget = q.FileWidget(root, state.selected_file_list, 4, 50, 100)
    state.file_widget = widget
    widget.pack(fill="both", expand=True)
    def close():
        state.closing = True
        state.ui_jobs.close()
        widget.destroy()
        q.cancel_tk_callbacks(root)
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    root.after(180000, close)
    root.mainloop()


if __name__ == "__main__":
    main()
