#
# Cmd2 unit/functional testing
#
# Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
# Released under MIT license, see LICENSE file

from pytest import fixture

import cmd2


class StdOut(object):
    def __init__(self):
        self.clear()

    def write(self, s):
        self.buffer += s

    def read(self):
        raise NotImplementedError

    def clear(self):
        self.buffer = ''


def _normalize(block):
    # normalize a block of text to perform comparison
    assert isinstance(block, str)
    block = block.strip('\n')
    return [line.rstrip() for line in block.splitlines()]


def run_cmd(app, cmd):
    app.stdout.clear()
    app.onecmd_plus_hooks(cmd)
    out = app.stdout.buffer
    app.stdout.clear()
    return _normalize(out)


@fixture
def base_app():
    c = cmd2.Cmd()
    c.stdout = StdOut()
    return c
