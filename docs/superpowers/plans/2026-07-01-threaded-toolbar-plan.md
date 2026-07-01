# Threaded Toolbar Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the performance of `get_bottom_toolbar` in `examples/getting_started.py` by
offloading terminal size fetching and datetime formatting to a background thread to prevent
micro-stuttering.

**Architecture:** Implement a producer/consumer pattern. A background thread (producer) calculates
the time and fetches the terminal width every 0.25 seconds. The UI callback (consumer) acquires a
lock, reads the cached values, calculates padding, and returns the formatted text to
`prompt_toolkit`.

**Tech Stack:** Python, `threading`, `prompt_toolkit`

## Global Constraints

- Must work with Python 3.8+ (implied by typical `cmd2` constraints).
- Use `uv` for script execution if needed, or `python -m` as it's just an example.
- Keep the example readable for beginners; avoid overly complex threading patterns beyond basic
  locks and events.

---

### Task 1: Add State Management to BasicApp

**Files:**

- Modify: `examples/getting_started.py`

**Interfaces:**

- Consumes: None
- Produces: Adds state variables `_toolbar_lock`, `_toolbar_text_left`, `_toolbar_time_str`,
  `_toolbar_cols`, `_stop_bg_thread`, and `_bg_thread` to `BasicApp`.

- [ ] **Step 1: Import threading**

```python
# Insert after existing imports in examples/getting_started.py
import threading
import time
```

- [ ] **Step 2: Initialize State in `__init__`**

```python
        # In BasicApp.__init__, after self.add_settable(...):

        # State for background toolbar updates
        self._toolbar_lock = threading.Lock()
        self._toolbar_text_left = sys.argv[0]
        self._toolbar_time_str = ""
        self._toolbar_cols = 80
        self._stop_bg_thread = threading.Event()
        self._bg_thread = None
```

- [ ] **Step 3: Commit**

```bash
git add examples/getting_started.py
git commit -m "feat(example): initialize state for threaded toolbar"
```

---

### Task 2: Implement the Background Worker Method

**Files:**

- Modify: `examples/getting_started.py`

**Interfaces:**

- Consumes: State variables from Task 1.
- Produces: Method `_update_toolbar_task()` on `BasicApp`.

- [ ] **Step 1: Write the worker method**

```python
    # Add this method to BasicApp in examples/getting_started.py
    def _update_toolbar_task(self) -> None:
        """Background task to pre-calculate toolbar variables."""
        while not self._stop_bg_thread.is_set():
            # Get the current time in ISO format with 0.01s precision
            dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
            now = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + dt.strftime("%z")

            # Fetch the terminal width
            try:
                cols = get_app().output.get_size().columns
            except (AttributeError, NotImplementedError):
                cols = 80  # Fallback if get_app() fails

            with self._toolbar_lock:
                self._toolbar_time_str = now
                self._toolbar_cols = cols

            time.sleep(0.25)
```

- [ ] **Step 2: Commit**

```bash
git add examples/getting_started.py
git commit -m "feat(example): add background worker for toolbar updates"
```

---

### Task 3: Manage Thread Lifecycle (Startup/Shutdown)

**Files:**

- Modify: `examples/getting_started.py`

**Interfaces:**

- Consumes: `_update_toolbar_task()` from Task 2.
- Produces: Overrides `preloop` and `postloop` to start and stop the thread.

- [ ] **Step 1: Override `preloop` to start thread**

```python
    # Add this method to BasicApp in examples/getting_started.py
    def preloop(self) -> None:
        """Runs right before the prompt loop begins."""
        super().preloop()
        self._stop_bg_thread.clear()
        self._bg_thread = threading.Thread(target=self._update_toolbar_task, daemon=True)
        self._bg_thread.start()
```

- [ ] **Step 2: Override `postloop` to stop thread**

```python
    # Add this method to BasicApp in examples/getting_started.py
    def postloop(self) -> None:
        """Runs right after the prompt loop ends."""
        self._stop_bg_thread.set()
        if self._bg_thread and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=1.0)
        super().postloop()
```

- [ ] **Step 3: Commit**

```bash
git add examples/getting_started.py
git commit -m "feat(example): manage background thread lifecycle"
```

---

### Task 4: Refactor the UI Callback

**Files:**

- Modify: `examples/getting_started.py`

**Interfaces:**

- Consumes: State variables protected by `_toolbar_lock`.
- Produces: Updated `get_bottom_toolbar` that is fast and non-blocking.

- [ ] **Step 1: Rewrite `get_bottom_toolbar`**

```python
    # Replace the existing get_bottom_toolbar method with this:
    def get_bottom_toolbar(self) -> AnyFormattedText:
        with self._toolbar_lock:
            left_text = self._toolbar_text_left
            now = self._toolbar_time_str
            cols = self._toolbar_cols

        # If time hasn't been calculated yet, provide a fallback
        if not now:
            now = "Loading..."

        padding_size = cols - len(left_text) - len(now) - 1
        if padding_size < 1:
            padding_size = 1
        padding = " " * padding_size

        return [
            ("ansigreen", left_text),
            ("", padding),
            ("ansicyan", now),
        ]
```

- [ ] **Step 2: Verify the script runs**

Run: `python examples/getting_started.py` (or `uv run python examples/getting_started.py` depending
on setup) Expected: The app starts, the bottom toolbar updates properly every half second, and rapid
typing feels smooth. (Exit with `quit`).

- [ ] **Step 3: Commit**

```bash
git add examples/getting_started.py
git commit -m "refactor(example): use cached variables in toolbar callback"
```
