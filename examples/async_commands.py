#!/usr/bin/env python
"""A simple example demonstrating how to run async commands in a cmd2 app.

It also demonstrates how to configure keybindings to run a handler method on
key-combo press and how to display colored output above the prompt.
"""

import asyncio
import functools
import random
import shutil
import threading
from collections.abc import Callable
from typing import (
    Any,
)

from prompt_toolkit import ANSI, print_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from rich.text import Text

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


def with_async_loop(func: Callable[..., Any], cancel_on_interrupt: bool = True) -> Callable[..., Any]:
    """Decorate an async ``do_*`` command method to give it access to the event loop.


    This decorator wraps a do_* command method. When the command is executed,
    it submits the coroutine returned by the method to a background asyncio loop
    and waits for the result synchronously (blocking the cmd2 loop, as expected
    for a synchronous command).

    :param func: do_* method to wrap
    :param cancel_on_interrupt: if True, cancel any running async task on an interrupt;
                                if False, leave any async task running
    """

    @functools.wraps(func)
    def wrapper(self: cmd2.Cmd, *args: Any, **kwargs: Any) -> Any:
        loop = _get_event_loop()
        coro = func(self, *args, **kwargs)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result()
        except KeyboardInterrupt:
            if cancel_on_interrupt:
                future.cancel()
            raise

    return wrapper


class AsyncCommandsApp(cmd2.Cmd):
    """Example cmd2 application with async commands."""

    def __init__(self) -> None:
        super().__init__()
        self.intro = 'Welcome to the Async Commands example. Type "help" to see available commands.'

        if self.session.key_bindings is None:
            self.session.key_bindings = KeyBindings()

        # Add a custom key binding for <CTRL>+T that calls a method so it has access to self
        @self.session.key_bindings.add('c-t')
        def _(_event: Any) -> None:
            self.handle_control_t(_event)

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

    def handle_control_t(self, _event) -> None:
        """Handler method for <CTRL>+T key press.

        Prints 'fnord' above the prompt in a random color and random position.
        """
        word = 'fnord'

        # Generate a random RGB color tuple
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)

        # Get terminal width to calculate padding for right-alignment
        cols, _ = shutil.get_terminal_size()
        extra_width = cols - len(word) - 1
        padding_size = random.randint(0, extra_width)
        padding = ' ' * padding_size

        # Use rich to generate the the overall text to print out
        text = Text()
        text.append(padding)
        text.append(word, style=f'rgb({r},{g},{b})')

        print_formatted_text(ANSI(cmd2.rich_utils.rich_text_to_string(text)))


if __name__ == '__main__':
    import sys

    app = AsyncCommandsApp()
    sys.exit(app.cmdloop())
