"""Bridges calls made inside of pyscript with the Cmd2 host app while maintaining a reasonable
degree of isolation between the two"""

import argparse

class ArgparseFunctor:
    def __init__(self, cmd2_app, item, parser):
        self._cmd2_app = cmd2_app
        self._item = item
        self._parser = parser

        self._args = {}
        self.__current_subcommand_parser = parser

    def __getattr__(self, item):
        # look for sub-command
        for action in self.__current_subcommand_parser._actions:
            if not action.option_strings and isinstance(action, argparse._SubParsersAction):
                if item in action.choices:
                    # item matches the a sub-command, save our position in argparse,
                    # save the sub-command, return self to allow next level of traversal
                    self.__current_subcommand_parser = action.choices[item]
                    self._args[action.dest] = item
                    return self
        return super().__getatttr__(item)

    def __call__(self, *args, **kwargs):
        next_pos_index = 0

        has_subcommand = False
        consumed_kw = []
        for action in self.__current_subcommand_parser._actions:
            # is this a flag option?
            if action.option_strings:
                if action.dest in kwargs:
                    self._args[action.dest] = kwargs[action.dest]
                    consumed_kw.append(action.dest)
            else:
                if not isinstance(action, argparse._SubParsersAction):
                    if next_pos_index < len(args):
                        self._args[action.dest] = args[next_pos_index]
                        next_pos_index += 1
                else:
                    has_subcommand = True

        for kw in kwargs:
            if kw not in consumed_kw:
                raise TypeError('{}() got an unexpected keyword argument \'{}\''.format(
                    self.__current_subcommand_parser.prog, kw))

        if has_subcommand:
            return self
        else:
            return self._run()

    def _run(self):
        # look up command function
        func = getattr(self._cmd2_app, 'do_' + self._item)

        # reconstruct the cmd2 command from the python call
        cmd_str = ['']

        def traverse_parser(parser):
            for action in parser._actions:
                # was something provided for the argument
                if action.dest in self._args:
                    # was the argument a flag?
                    # TODO: Handle 'narg' and 'append' options
                    if action.option_strings:
                        cmd_str[0] += '"{}" "{}" '.format(action.option_strings[0], self._args[action.dest])
                    else:
                        cmd_str[0] += '"{}" '.format(self._args[action.dest])

                        if isinstance(action, argparse._SubParsersAction):
                            traverse_parser(action.choices[self._args[action.dest]])
        traverse_parser(self._parser)

        func(cmd_str[0])
        return self._cmd2_app._last_result


class PyscriptBridge(object):
    def __init__(self, cmd2_app):
        self._cmd2_app = cmd2_app
        self._last_result = None

    def __getattr__(self, item: str):
        commands = self._cmd2_app.get_all_commands()
        if item in commands:
            func = getattr(self._cmd2_app, 'do_' + item)

            try:
                parser = getattr(func, 'argparser')
            except AttributeError:
                def wrap_func(args=''):
                    func(args)
                    return self._cmd2_app._last_result
                return wrap_func
            else:
                return ArgparseFunctor(self._cmd2_app, item, parser)

        return super().__getattr__(item)

    def __call__(self, args):
        self._cmd2_app.onecmd_plus_hooks(args + '\n')
        self._last_result = self._cmd2_app._last_result
        return self._cmd2_app._last_result
