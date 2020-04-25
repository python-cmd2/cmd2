#!/usr/bin/env python3
# coding=utf-8
"""A simple example cmd2 application demonstrating the following:
     1) Colorizing/stylizing output
     2) Using multiline commands
     3) Persistent history
     4) How to run an initialization script at startup
     5) How to group and categorize commands when displaying them in help
     6) Opting-in to using the ipy command to run an IPython shell
     7) Allowing access to your application in py and ipy
     8) Displaying an intro banner upon starting your application
     9) Using a custom prompt
    10) How to make custom attributes settable at runtime
"""
import cmd2
from cmd2 import bg, fg, style


class BasicApp(cmd2.Cmd):
    CUSTOM_CATEGORY = 'My Custom Commands'

    def __init__(self):
        super().__init__(multiline_commands=['echo'], persistent_history_file='cmd2_history.dat',
                         startup_script='scripts/startup.txt', use_ipython=True)

        # Prints an intro banner once upon application startup
        self.intro = style('Welcome to cmd2!', fg=fg.red, bg=bg.white, bold=True)

        # Show this as the prompt when asking for input
        self.prompt = 'myapp> '

        # Used as prompt for multiline commands after the first line
        self.continuation_prompt = '... '

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = 'cmd2 Built-in Commands'

        # Color to output text in with echo command
        self.foreground_color = 'cyan'

        # Make echo_fg settable at runtime
        self.add_settable(cmd2.Settable('foreground_color', str, 'Foreground color to use with echo command',
                                        choices=fg.colors()))

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_intro(self, _):
        """Display the intro banner"""
        self.poutput(self.intro)

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_echo(self, arg):
        """Example of a multiline command"""
        self.poutput(style(arg, fg=self.foreground_color))


if __name__ == '__main__':
    app = BasicApp()
    app.cmdloop()
