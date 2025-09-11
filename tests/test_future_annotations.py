from __future__ import annotations

import cmd2

from .conftest import normalize, run_cmd


def test_hooks_work_with_future_annotations() -> None:
    class HookApp(cmd2.Cmd):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.register_cmdfinalization_hook(self.hook)

        def hook(self: cmd2.Cmd, data: cmd2.plugin.CommandFinalizationData) -> cmd2.plugin.CommandFinalizationData:
            if self.in_script():
                self.poutput("WE ARE IN SCRIPT")
            return data

    hook_app = HookApp()
    out, _err = run_cmd(hook_app, '')
    expected = normalize('')
    assert out == expected
