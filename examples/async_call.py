#!/usr/bin/env python
"""A simple example demonstrating calling an async function from a cmd2 app."""

import asyncio
import concurrent.futures
import threading

import cmd2

_event_loop = None
_event_lock = threading.Lock()


def run_async(coro) -> concurrent.futures.Future:
    """
    Await a coroutine from a synchronous function/method.
    """

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

    return asyncio.run_coroutine_threadsafe(coro, _event_loop)


async def async_wait(duration: float) -> float:
    """
    Example async function that is called from a synchronous cmd2 command
    """
    await asyncio.sleep(duration)
    return duration


class AsyncCallExample(cmd2.Cmd):
    """
    A simple cmd2 application.
    Demonstrates how to run an async function from a cmd2 command.
    """

    def do_async_wait(self, _: str) -> None:
        """
        Waits asynchronously.  Example cmd2 command that calls an async function.
        """

        waitable = run_async(async_wait(0.1))
        self.poutput('Begin waiting...')
        # Wait for coroutine to complete and get its return value:
        res = waitable.result()
        self.poutput(f'Done waiting: {res}')
        return

    def do_hello_world(self, _: str) -> None:
        """
        Prints a simple greeting.  Just a typical (synchronous) cmd2 command
        """
        self.poutput('Hello World')


async def main() -> int:
    """
    Having this async ensures presence of the top level event loop.
    """
    app = AsyncCallExample()
    app.set_window_title("Call to an Async Function Test")
    return app.cmdloop()


if __name__ == '__main__':
    import sys

    sys.exit(asyncio.run(main(), debug=True))
