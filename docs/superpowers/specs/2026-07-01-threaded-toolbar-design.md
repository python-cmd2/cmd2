# Threaded Toolbar Update Design

## Goal

Improve the performance of `get_bottom_toolbar` in `examples/getting_started.py` by offloading heavy
operations (terminal size fetching and datetime formatting) to a background thread. This will
prevent micro-stuttering during rapid typing, as `get_bottom_toolbar` is called on every keystroke
by `prompt_toolkit`.

## Architecture

We will implement a producer/consumer pattern using a background thread and a lock.

### 1. State Management

- Add instance variables to `BasicApp`:
    - `_toolbar_lock`: A `threading.Lock` to protect shared state.
    - `_toolbar_text_left`: Cached script name (`sys.argv[0]`).
    - `_toolbar_time_str`: Cached, formatted datetime string.
    - `_toolbar_cols`: Cached terminal width.
    - `_stop_bg_thread`: A `threading.Event` (or boolean flag) to signal the thread to exit.
    - `_bg_thread`: The `threading.Thread` instance.

### 2. The Background Worker

- Create a method `_update_toolbar_task(self)`:
    - Runs in a `while not self._stop_bg_thread.is_set():` loop.
    - Sleeps for `0.25` seconds per iteration (slightly faster than the `0.5` UI refresh interval).
    - Fetches the current time and formats it.
    - Fetches the terminal width via `get_app().output.get_size().columns`.
        - _Note: Needs a fallback mechanism if `get_app()` isn't fully initialized._
    - Acquires `_toolbar_lock` and updates `_toolbar_time_str` and `_toolbar_cols`.

### 3. The UI Callback

- Update `get_bottom_toolbar(self) -> AnyFormattedText`:
    - Acquires `_toolbar_lock`.
    - Reads the cached left text, time string, and columns.
    - Releases the lock.
    - Calculates the padding dynamically based on the cached columns.
    - Returns the `prompt_toolkit` formatted text array.

### 4. Lifecycle Management

- **Startup:** Start the thread in `preloop()` (which runs right before the prompt loop begins).
- **Shutdown:** Signal `_stop_bg_thread` and `join()` the thread in `postloop()` (which runs right
  after the prompt loop ends).

## Trade-offs

- **Pros:** The UI callback becomes a simple lock acquisition and string length calculation,
  completely removing I/O and complex object creation from the critical path of the keystroke loop.
- **Cons:** Introduces concurrency concepts (threads, locks, events) to a "getting started" script,
  raising the complexity floor.
