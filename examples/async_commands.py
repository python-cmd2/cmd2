#!/usr/bin/env python
"""A simple example demonstrating how to run async commands in a cmd2 app."""

import asyncio
import functools
import threading
from collections.abc import Callable
from typing import (
    Any,
)

import cmd2

# Global event loop and lock
_event_loop: asyncio.AbstractEventLoop | None = None
_event_lock = threading.Lock()


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create the background event loop."""
    global _event_loop  # noqa: PLW0603

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
    """Decorator to run a command method asynchronously in a background thread.

    This decorator wraps a do_* command method. When the command is executed,
    it submits the coroutine returned by the method to a background asyncio loop
    and waits for the result synchronously (blocking the cmd2 loop, as expected
    for a synchronous command).
    """

    @functools.wraps(func)
    def wrapper(self: cmd2.Cmd, *args: Any, **kwargs: Any) -> Any:
        loop = _get_event_loop()
        coro = func(self, *args, **kwargs)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    return wrapper


class AsyncCommandsApp(cmd2.Cmd):
    """Example cmd2 application with async commands."""

    def __init__(self) -> None:
        super().__init__()
        self.intro = 'Welcome to the Async Commands example. Type "help" to see available commands.'

    @with_async_loop
    async def do_my_async(self, _: cmd2.Statement) -> None:
        """An example async command that simulates work."""
        self.poutput("Starting async work...")
        # simulate some async I/O
        await asyncio.sleep(1.0)
        self.poutput("Async work complete!")

    @with_async_loop
    async def do_fetch(self, _: cmd2.Statement) -> None:
        """Simulate fetching data asynchronously."""
        self.poutput("Fetching data...")
        data = await self._fake_fetch()
        self.poutput(f"Received: {data}")

    async def _fake_fetch(self) -> str:
        await asyncio.sleep(0.5)
        return "Some Data"

    def do_sync_command(self, _: cmd2.Statement) -> None:
        """A normal synchronous command."""
        self.poutput("This is a normal synchronous command.")


if __name__ == '__main__':
    import sys

    app = AsyncCommandsApp()
    sys.exit(app.cmdloop())
