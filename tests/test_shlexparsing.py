# coding=utf-8
"""
Unit/functional testing for ply based parsing in cmd2

Todo List
- case sensitive flag
- checkout Cmd2.parseline() function which parses and expands shortcuts and such
  this code should probably be included in CommandParser
- get rid of legalChars
- move remaining tests in test_parsing.py to test_cmd2.py
- rename test_shlexparsing.py to test_parsing.py
- look at parsed() - expands aliases and shortcuts, see if it can be refactored

Notes:

- valid comment styles:
    - C-style -> /* comment */
    - Python/Shell style -> # comment
- we now ignore self.identchars, which breaks backwards compatibility with the cmd in the standard library


Changelog Items:
- if self.default_to_shell is true, then redirection and piping is now properly passed to the shell, previously it was truncated
- object passed to do_* methods has changed. It no longer is the pyparsing object, it's a new Statement object. A side effect of this is that we now have a clean interface between the parsing logic and the rest of cmd2. If we need to change the parser in the future, we can do it without breaking anything. The parser is now self.statement_parser instead of self.command_parser.
- input redirection no longer supported. Use the load command instead.
- submenus now call all hooks, it used to just call precmd and postcmd

"""
