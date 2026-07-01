# Getting Started Bottom Toolbar Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize the bottom toolbar refresh logic in `examples/getting_started.py` to prevent
micro-stutters during high-frequency typing.

**Architecture:** Introduce a background daemon thread that periodically updates the timestamp and
terminal width, storing them in thread-safe instance variables protected by a lock, which the UI
callback then reads.

**Tech Stack:** Python 3, `threading`, `shutil`, `datetime`, `prompt_toolkit`.

## Global Constraints

- Run `make check` and `make test` before committing.
- Do not use `get_app()` in the background thread. Use `shutil.get_terminal_size().columns`.

---

### Task 1: Initialize State and Background Thread

**Files:**

- Modify: `examples/getting_started.py`

**Interfaces:**

- Consumes: None
- Produces: `self._toolbar_lock`, `self._toolbar_now`, `self._toolbar_cols`, and a running
  background thread calling `self._update_toolbar_info`.

- [ ] **Step 1: Import required modules**

```python
import shutil
import threading
import time
```

Add these to the top of `examples/getting_started.py` if not already present.

- [ ] **Step 2: Add state initialization to `__init__`**

In `examples/getting_started.py`, inside `BasicApp.__init__`, add the state variables:

```python
        # Bottom toolbar state
        self._toolbar_lock = threading.Lock()
        self._toolbar_now = ""
        self._toolbar_cols = 80
```

- [ ] **Step 3: Define the background worker method**

Add `_update_toolbar_info` to `BasicApp`:

```python
    def _update_toolbar_info(self) -> None:
        """Background thread to update toolbar information."""
        while True:
            dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
            now = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + dt.strftime("%z")

            # Use shutil to get terminal size safely from a background thread
            cols = shutil.get_terminal_size().columns

            with self._toolbar_lock:
                self._toolbar_now = now
                self._toolbar_cols = cols

            time.sleep(0.1)
```

- [ ] **Step 4: Start the background thread**

In `BasicApp.__init__`, after initializing the state, start the daemon thread:

```python
        # Start background thread to update toolbar info
        self._toolbar_thread = threading.Thread(target=self._update_toolbar_info, daemon=True)
        self._toolbar_thread.start()
```

- [ ] **Step 5: Run basic validation**

Run: `python3 examples/getting_started.py` Expected: The app starts successfully and functions
normally.

- [ ] **Step 6: Commit**

```bash
make check
git add examples/getting_started.py
git commit -m "feat(examples): add background thread for toolbar info"
```

---

### Task 2: Refactor `get_bottom_toolbar` Callback

**Files:**

- Modify: `examples/getting_started.py`

**Interfaces:**

- Consumes: `self._toolbar_lock`, `self._toolbar_now`, `self._toolbar_cols`
- Produces: Formatted output for `get_bottom_toolbar`

- [ ] **Step 1: Update `get_bottom_toolbar` to read from state**

In `examples/getting_started.py`, replace the contents of `get_bottom_toolbar` with:

```python
    def get_bottom_toolbar(self) -> AnyFormattedText:
        left_text = sys.argv[0]

        with self._toolbar_lock:
            now = self._toolbar_now
            cols = self._toolbar_cols

        # During the very first UI render, the background thread might not have populated 'now' yet.
        # Fallback to an empty string or immediate fetch if necessary, but empty string is fine
        # since the next render (0.1s later) will have it.
        if not now:
            dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
            now = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + dt.strftime("%z")

        padding_size = cols - len(left_text) - len(now) - 1
        if padding_size < 1:
            padding_size = 1
        padding = " " * padding_size

        # Return formatted text for prompt-toolkit
        return [
            ("ansigreen", left_text),
            ("", padding),
            ("ansicyan", now),
        ]
```

- [ ] **Step 2: Run basic validation**

Run: `python3 examples/getting_started.py` Expected: The app starts, the bottom toolbar displays the
timestamp dynamically and right-aligns correctly when resizing the terminal.

- [ ] **Step 3: Run project tests**

Run: `make test` Expected: PASS

- [ ] **Step 4: Commit**

```bash
make check
git add examples/getting_started.py
git commit -m "refactor(examples): optimize get_bottom_toolbar to use cached info"
```
