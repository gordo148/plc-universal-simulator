# Digital and Analog UI performance

## Test environment

- Fedora Linux 44, x86-64
- Python 3.14.6
- CustomTkinter 5.2.2
- PyInstaller 6.21.0
- 1600×1000×24 Xvfb display
- `time.perf_counter()` timings and `tracemalloc` Python allocation peaks
- Synthetic `TagDefinition` objects; no PLC, CSV file, or network driver

The harness is `scripts/stress_test_ui.py`. Results are single-run measurements on this host and should be compared directionally; desktop compositor and hardware results will vary.

## Root cause

The pooled implementation limited the number of visible rows, but each visible Digital row still allocated about 10 CTk objects and each Analog row about 23. Fifty Digital rows produced 511 measured CTk widgets; 25 Analog rows produced 587. Initial page creation took 1.82–2.50 seconds and stalled Tk's event loop for 0.82–1.18 seconds.

Constructor timings, not layout or model work, dominated. In representative baseline runs Digital entry construction consumed roughly 527 ms, labels 452 ms, option menus 277 ms, buttons 216 ms, and frames 138 ms; measured layout was only 16 ms. Analog entries consumed roughly 750–777 ms, labels 571–592 ms, frames 204–249 ms, buttons 217–252 ms, option menus 157–177 ms, and sliders 126–142 ms; layout was 21–24 ms. Tag-model generation remained below 6 ms at 5,000 tags.

The harness generated, parsed, and validated a temporary universal CSV containing 1,000 tags in 5.478 ms. CSV application remains staged: it updates the model and Tag Manager, and does not call simulation-tab generation.

No per-row `update_idletasks()`, `canvas.bbox("all")`, StringVar/IntVar creation, or variable traces were found. The old Digital rows did register repeated button/name callbacks. Project opening calls `generate_signals()` once; tab selection only refreshes a tab marked dirty. CSV staging does not call `generate_signals()` and its regression tests enforce that behavior.

## Architecture chosen

Both simulation tabs now use master-detail:

- A lightweight `ttk.Treeview` displays the current page of the table model.
- Digital owns one Toggle/Pulse editor and one ON/OFF button.
- Analog owns one slider and one profile editor.
- Selection rebinds the same editor widgets; it does not allocate row controls.
- Pagination remains to bound Treeview insertion and tag-value update work.
- The enabled tag model can contain 5,000 tags without creating 5,000 controls.

## Source timings

Times are milliseconds. “Create” is initial visible-page population, after persistent tab structure creation.

| Tab | Tags | Before create | After create | Before page | After page | Before 50→25 | After 50→25 | After values |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Digital | 100 | 1819.397 | 2.874 | 76.759 | 2.511 | 46.863 | 2.303 | 0.972 |
| Digital | 500 | 2088.261 | 3.290 | 107.822 | 3.169 | 49.154 | 2.872 | 0.899 |
| Digital | 1000 | 2228.678 | 4.260 | 67.219 | 4.109 | 69.773 | 3.747 | 0.814 |
| Digital | 5000 | 2310.838 | 12.240 | 121.337 | 12.325 | 71.349 | 11.504 | 0.935 |
| Analog | 100 | 2329.566 | 3.763 | 107.172 | 2.936 | 113.823 | 2.864 | 2.081 |
| Analog | 500 | 2435.013 | 4.382 | 89.727 | 3.730 | 89.916 | 3.365 | 2.239 |
| Analog | 1000 | 2496.387 | 6.048 | 107.104 | 5.742 | 115.238 | 10.584 | 6.046 |

All after-change results meet the requested budgets. Operations completed faster than the 10 ms responsiveness heartbeat in most runs, so no event-loop stall was sampled after the change.

## Widget and memory comparison

| Tab | Before widgets | After widgets | Before peak MiB | After peak MiB |
|---|---:|---:|---:|---:|
| Digital | 511 | 16 | 3.93–4.36 | 0.21–0.29 |
| Analog | 587 | 36 | 4.36–4.75 | 0.39–0.40 |

The counts cover CTk widgets. Treeview and its ttk scrollbar are intentionally lightweight and are not included in the CTk count. The memory figure is `tracemalloc` peak during each isolated tab run, not whole-process RSS.

## Packaged comparison

The same harness was built with PyInstaller and run against the same X display. Packaged Digital creation ranged from 2.871 to 14.647 ms and Analog from 5.390 to 6.509 ms. Source ranges were 2.874–12.240 ms and 3.763–6.048 ms. The small mixed differences are normal run-to-run variation; source mode is not materially slower and was not the cause.

## Reproduction

```bash
# Desktop session
python scripts/stress_test_ui.py --architecture legacy --output /tmp/ui-before.json
python scripts/stress_test_ui.py --output /tmp/ui-after.json

# Headless Linux
xvfb-run -a python scripts/stress_test_ui.py --output /tmp/ui-after.json

# Packaged harness
python -m PyInstaller --noconfirm --clean --name stress-test-ui scripts/stress_test_ui.py
xvfb-run -a dist/stress-test-ui/stress-test-ui --output /tmp/ui-packaged.json
```

## Remaining limitations

- Treeview refresh currently validates/filters the full tag list, so 5,000-tag page changes rise to about 12–15 ms. This remains below budget.
- Measurements are single-run and Xvfb does not include a desktop compositor.
- The CSV timing covers parsing and validation, not time spent choosing a file in the native file dialog.
