Initialization
==============

Here is a basic example ``cmd2`` application which demonstrates many
capabilities which you may wish to utilize while initializing the app::

    #!/usr/bin/env python3
    # coding=utf-8
    """A simple example cmd2 appliction demonstrating the following:
        1) Colorizing/stylizing output
        2) Using multiline commands
        3) Persistent history
        4) How to run an initialization script at startup
        5) How to group and categorize commands when displaying them in help
        6) Opting-in to using the ipy command to run an IPython shell
        7) Allowing access to your application in py and ipy
        8) Displaying an intro banner upon starting your application
        9) Using a custom prompt
    """
    import cmd2
    from cmd2 import style


    class BasicApp(cmd2.Cmd):
        CUSTOM_CATEGORY = 'My Custom Commands'

        def __init__(self):
            super().__init__(multiline_commands=['echo'], persistent_history_file='cmd2_history.dat',
                             startup_script='scripts/startup.txt', use_ipython=True)

            self.intro = style('Welcome to cmd2!', fg='red', bg='white', bold=True)
            self.prompt = 'myapp> '

            # Allow access to your application in py and ipy via self
            self.locals_in_py = True

            # Set the default category name
            self.default_category = 'cmd2 Built-in Commands'

        @cmd2.with_category(CUSTOM_CATEGORY)
        def do_intro(self, _):
            """Display the intro banner"""
            self.poutput(self.intro)

        @cmd2.with_category(CUSTOM_CATEGORY)
        def do_echo(self, arg):
            """Example of a multiline command"""
            self.poutput(arg)


    if __name__ == '__main__':
        app = BasicApp()
        app.cmdloop()
