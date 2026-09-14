## Example for testing nested input, secret input, and select input.  Also demonstrates
## how to suspend the bottom toolbar and hand off the terminal to a guest.

import time

from getting_started import BasicApp


class ManualApp(BasicApp):
    def do_nested(self, _arg):
        value = self.read_input("Value> ", choices=["alpha", "beta"], history=["alpha", "beta"])
        self.poutput(repr(value))

    def do_secret(self, _arg):
        self.read_secret("Dummy secret> ")
        self.poutput("Secret accepted; value not displayed")

    def do_choose(self, _arg):
        self.poutput(self.select(["alpha", "beta"], "Choose> "))

    def do_quiet(self, _arg):
        time.sleep(10)

    def do_partial(self, _arg):
        self.stdout.write("PARTIAL")
        self.stdout.flush()
        time.sleep(10)
        self.stdout.write("END\n")
        self.stdout.flush()

    def do_handoff(self, arg):
        with self.suspend_bottom_toolbar():
            with self.suspend_bottom_toolbar():
                input("Guest owns terminal; resize, then Enter> ")
            if arg.strip() == "fail":
                raise RuntimeError("Intentional guest failure")


if __name__ == "__main__":
    ManualApp().cmdloop()
