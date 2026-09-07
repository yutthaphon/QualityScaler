# Python GUI responsiveness changes

The existing Python / CustomTkinter frontend and ONNX models are retained.
Pre-existing output-naming changes in the working tree are preserved.

## Implemented

- A virtual list keeps at most 16 file cards instantiated. Removing a file
  preserves surviving cards and updates only the affected list window.
- Metadata, thumbnail decoding, resume scans, folder discovery and output-drive
  checks run in bounded background jobs. Workers return plain data / PIL images;
  Tk objects are created and updated on the UI thread.
- Preview failures are isolated to a card with a retry action. Extreme aspect
  ratios cannot produce a zero-pixel thumbnail dimension.
- File caches have bounded capacity, constant-time version invalidation and no
  method cache retaining FileWidget instances. Raw preview data is independent
  of target-ratio settings.
- Settings changes coalesce into one delayed refresh. Labels and progress bars
  update in place. Changes to input scale, target ratio and the first source
  refresh their dependent values. Target presets are calculated per card.
- Resume scans are cached separately from layout. Completion records capture
  the settings at job submission and include source version and output location.
- Static resume indicators do not replay animations when settings change.
  Active-file highlighting changes only affected visible cards.
- The empty panel and Start/Stop button are reused. CLEAN/removal is guarded
  while a job is starting or running.
- Log rendering appends and trims lines instead of replacing the entire text;
  polling has a per-tick budget and respects the reader's scroll position.
- Status monitoring never calls Tk from its worker thread. Final/error events
  are not overwritten by a latest-value queue.
- Stop runs cleanup asynchronously, retains cancellation until the next run,
  waits for the status monitor, and reaps owned processes and observed children.
  A cleanup failure leaves the operation available for retry.
- Shutdown stops work before destroying Tcl objects and cancels scheduled
  callbacks without deleting another widget's Tcl command. Probe timeouts kill
  and reap the probe; active UI probes are also stopped during shutdown.
- Frame workers save before reporting completion. Image arrays no longer pass
  through the Manager queue, and there is no unbounded save-executor backlog.
  Save failures propagate; encoding rejects missing expected frames.
- Images and preferences are published using temporary files and atomic replace.
  An interrupted frame write does not replace a previously complete frame.
- Tile blending reuses the accumulator for normalization instead of allocating
  another full-size float image. Full output accumulators are still required.
- Duration formatting carries rounded seconds correctly. Cancelling the file
  picker leaves the application ready. Hover styling uses public button options.

## Verification

On 2026-09-07, all 86 tests passed on Windows / Python 3.14. Compilation and
the whitespace check below also passed. This is functional regression evidence,
not a before/after frame-rate benchmark.

Run from the repository root:

```powershell
python -m unittest discover -s tests -q
python -m compileall -q QualityScaler.py quality_scaler_runtime.py tools/gui_smoke.py
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check
```

The regression suite covers real Tk widget construction (with hidden windows),
1,000-item virtualization, deletion while preview futures remain unfinished,
scrolling to late files, stable label/button identities, debouncing, per-card
errors/retry, incremental logs, shutdown, bounded caches/jobs, atomic writes,
real image decoding and deterministic tile pixels. The process lifecycle test
starts and stops its own Windows process and child. Frame-save tests use a fake
AI engine to check ordering, error propagation and IPC payloads.

`requirements-tested.txt` records the installed direct dependency versions used
for these checks. It is not a complete transitive dependency lock.

For an interactive synthetic list:

```powershell
python tools/gui_smoke.py
```

This harness uses synthetic previews, does not write user preferences or process
videos, and closes automatically after three minutes.

## Limits of the evidence

- Windows Computer Use could not connect to its native pipe, so no screenshot
  or visual-QA claim is made. Hidden-widget tests do not establish frame rate.
- Real GPU inference, long-video throughput, peak RAM/VRAM and packaged EXE
  performance have not been benchmarked. Saving within each worker trades
  separate save-thread overlap for bounded memory and simpler failure handling.
- Very slow or stuck native decoders can occupy a preview worker. Pending jobs
  are bounded; daemon preview workers cannot prevent the Python app from exiting.
- Tile blending still holds full-size output accumulators. Streaming stripes
  would be a separate algorithm change requiring additional image-quality tests.
