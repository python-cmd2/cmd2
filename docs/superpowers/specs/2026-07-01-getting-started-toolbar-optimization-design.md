# Getting Started Bottom Toolbar Optimization Design

## Objective

Optimize the `get_bottom_toolbar` callback in `examples/getting_started.py` to prevent potential
micro-stutters during high-frequency typing. The callback currently performs heavy operations (time
formatting and terminal size fetching) on every UI refresh.

## Architecture & State Management

- **Background Worker**: We will introduce a background daemon thread that periodically updates the
  timestamp and terminal width.
- **Thread Safety**: A `threading.Lock` will be used to protect the shared state (`_toolbar_now` and
  `_toolbar_cols`) between the background thread and the main prompt-toolkit UI thread.

## Component Details

### `BasicApp.__init__`

- Initialize `self._toolbar_lock = threading.Lock()`.
- Initialize `self._toolbar_now` to an empty string.
- Initialize `self._toolbar_cols` to a default integer (e.g., 80).
- Start a daemon background thread executing a new method: `self._update_toolbar_info`.

### `BasicApp._update_toolbar_info` (Background Thread)

- Runs in an infinite loop (`while True`).
- Fetches the current time in ISO format with 0.01s precision.
- Fetches the terminal width using `shutil.get_terminal_size().columns`. (We cannot use
  `get_app().output.get_size()` because `get_app()` relies on a thread-local context and would
  return a `DummyApplication` inside the background thread).
- Acquires `self._toolbar_lock` and updates `self._toolbar_now` and `self._toolbar_cols`.
- Sleeps for `0.1` seconds to throttle the updates without significantly delaying visual accuracy.

### `BasicApp.get_bottom_toolbar` (Main UI Thread)

- Acquires `self._toolbar_lock`.
- Reads `self._toolbar_now` and `self._toolbar_cols`.
- Calculates padding based on the fetched columns and the static `left_text`.
- Returns the `AnyFormattedText` structure.

## Testing & Validation

- Run `examples/getting_started.py` manually to ensure the bottom toolbar updates properly and
  resizes correctly when the terminal width changes.
- Ensure that fast typing does not exhibit noticeable UI stutter.
- Verify `make check` and `make test` pass without regressions.
