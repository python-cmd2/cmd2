import unittest
from unittest.mock import MagicMock, patch

import cmd2
import cmd2.cmd2  # to patch vt100_support
from cmd2 import rich_utils as ru


class TestAsyncAlert(unittest.TestCase):
    def test_async_alert_strips_ansi_when_allow_style_is_never(self):
        app = cmd2.Cmd()

        # Patch vt100_support to True
        with patch('cmd2.cmd2.vt100_support', True):
            # Patch threading functions
            mock_current_thread = MagicMock()
            mock_current_thread.name = "NotMainThread"

            with (
                patch('threading.current_thread', return_value=mock_current_thread),
                patch('threading.main_thread', return_value=MagicMock()),
                patch('cmd2.cmd2.rl_get_display_prompt', return_value='(Cmd) '),
                patch('cmd2.cmd2.readline.get_line_buffer', return_value=''),
                patch('cmd2.cmd2.rl_get_point', return_value=0),
                patch('cmd2.cmd2.rl_force_redisplay'),
                patch('sys.stdout', new_callable=MagicMock) as mock_stdout,
            ):
                # Set allow_style to NEVER
                app.allow_style = ru.AllowStyle.NEVER

                # Styled message
                msg = "\033[31mError\033[0m"

                # Call async_alert
                app.async_alert(msg)

                # Capture calls to write
                # mock_stdout.write.call_args_list -> [call(str), call(str)...]
                # We look at all written strings
                written_content = "".join([call.args[0] for call in mock_stdout.write.call_args_list])

                # Check that ANSI codes for color are NOT present
                if "\033[31m" in written_content:
                    raise AssertionError(f"Found ANSI color code in output: {written_content!r}")
                if "Error" not in written_content:
                    raise AssertionError(f"Message 'Error' not found in output: {written_content!r}")


if __name__ == '__main__':
    unittest.main()
