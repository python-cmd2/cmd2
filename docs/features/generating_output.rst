Generating Output
=================

how to generate output

- poutput
- perror
- paging
- exceptions
- color support

Output Redirection
------------------

As in a Unix shell, output of a command can be redirected:

  - sent to a file with ``>``, as in ``mycommand args > filename.txt``
  - appended to a file with ``>>``, as in ``mycommand args >> filename.txt``
  - piped (``|``) as input to operating-system commands, as in
    ``mycommand args | wc``



.. note::

   If you wish to disable cmd2's output redirection and pipes features, you can
   do so by setting the ``allow_redirection`` attribute of your ``cmd2.Cmd``
   class instance to ``False``.  This would be useful, for example, if you want
   to restrict the ability for an end user to write to disk or interact with
   shell commands for security reasons::

       from cmd2 import Cmd
       class App(Cmd):
           def __init__(self):
               self.allow_redirection = False

   cmd2's parser will still treat the ``>``, ``>>``, and `|` symbols as output
   redirection and pipe symbols and will strip arguments after them from the
   command line arguments accordingly.  But output from a command will not be
   redirected to a file or piped to a shell command.

If you need to include any of these redirection characters in your command, you
can enclose them in quotation marks, ``mycommand 'with > in the argument'``.


