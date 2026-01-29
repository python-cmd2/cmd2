# Async Commands

`cmd2` is built on top of the Python Standard Library's `cmd` module, which is inherently
synchronous. This means that `do_*` command methods are expected to be synchronous functions.

However, you can still integrate asynchronous code (using `asyncio` and `async`/`await`) into your
`cmd2` application by running an `asyncio` event loop in a background thread and bridging calls to
it.

## The `with_async_loop` Decorator

A clean way to handle this is to define a decorator that wraps your `async def` commands. This
decorator handles:

1.  Starting a background thread with an `asyncio` loop (if not already running).
2.  Submitting the command's coroutine to that loop.
3.  Waiting for the result (synchronously) so that the `cmd2` interface behaves as expected
    (blocking until the command completes).

### Example Implementation

Here is an example of how to implement such a decorator and use it in your application.

```python
import asyncio
import functools
import threading
from typing import Any, Callable
import cmd2

# Global event loop and lock
_event_loop = None
_event_lock = threading.Lock()

def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create the background event loop."""
    global _event_loop

    if _event_loop is None:
        with _event_lock:
            if _event_loop is None:
                _event_loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=_event_loop.run_forever,
                    name='Async Runner',
                    daemon=True,
                )
                thread.start()
    return _event_loop

def with_async_loop(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to run a command method asynchronously in a background thread."""
    @functools.wraps(func)
    def wrapper(self: cmd2.Cmd, *args: Any, **kwargs: Any) -> Any:
        loop = _get_event_loop()
        coro = func(self, *args, **kwargs)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    return wrapper

class AsyncApp(cmd2.Cmd):
    @with_async_loop
    async def do_my_async(self, _: cmd2.Statement) -> None:
        self.poutput("Starting async work...")
        await asyncio.sleep(1.0)
        self.poutput("Async work complete!")
```

## See Also

- [async_commands.py](https://github.com/python-cmd2/cmd2/blob/main/examples/async_commands.py) -
  Full example code.
- [async_call.py](https://github.com/python-cmd2/cmd2/blob/main/examples/async_call.py) - An
  alternative example showing how to make individual async calls without a decorator.
