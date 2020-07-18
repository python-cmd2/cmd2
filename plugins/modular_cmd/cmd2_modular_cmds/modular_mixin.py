#
# coding=utf-8
"""External test interface plugin"""

import inspect
import types
from typing import (
    Callable,
    Iterable,
    List,
    Optional,
    TYPE_CHECKING
)

import cmd2
from cmd2.constants import COMMAND_FUNC_PREFIX, COMPLETER_FUNC_PREFIX, HELP_FUNC_PREFIX

from .command_definition import CommandSet, _REGISTERED_COMMANDS, _partial_passthru

if TYPE_CHECKING:  # pragma: no cover
    _Base = cmd2.Cmd
else:
    _Base = object


class ModularCommandsMixin(_Base):
    """A cmd2 plugin (mixin class) that adds support for grouping commands into CommandSets"""

    def __init__(self,
                 *args,
                 command_sets: Optional[Iterable[CommandSet]] = None,
                 auto_load_commands: bool = True,
                 **kwargs):
        """

        :type self: cmd2.Cmd
        :param args:
        :param kwargs:
        """
        # code placed here runs before cmd2 initializes
        super().__init__(*args, **kwargs)

        # code placed here runs after cmd2 initializes
        # Load modular commands
        self._installed_functions = []  # type: List[str]
        self._installed_command_sets = []  # type: List[CommandSet]
        if command_sets:
            for command_set in command_sets:
                self.install_command_set(command_set)

        if auto_load_commands:
            self._autoload_commands()

    def _autoload_commands(self) -> None:
        """
        Load modular command definitions.
        :return: None
        """

        # start by loading registered functions as commands
        for cmd_name in _REGISTERED_COMMANDS.keys():
            self.install_registered_command(cmd_name)

        # Search for all subclasses of CommandSet, instantiate them if they weren't provided in the constructor
        all_commandset_defs = CommandSet.__subclasses__()
        existing_commandset_types = [type(command_set) for command_set in self._installed_command_sets]
        for cmdset_type in all_commandset_defs:
            init_sig = inspect.signature(cmdset_type.__init__)
            if cmdset_type in existing_commandset_types or \
                    len(init_sig.parameters) != 1 or \
                    'self' not in init_sig.parameters:
                continue
            cmdset = cmdset_type()
            self.install_command_set(cmdset)

    def install_command_set(self, cmdset: CommandSet):
        """
        Installs a CommandSet, loading all commands defined in the CommandSet

        :param cmdset: CommandSet to load
        :return: None
        """
        existing_commandset_types = [type(command_set) for command_set in self._installed_command_sets]
        if type(cmdset) in existing_commandset_types:
            raise ValueError('CommandSet ' + type(cmdset).__name__ + ' is already installed')

        cmdset.on_register(self)
        methods = inspect.getmembers(
            cmdset,
            predicate=lambda meth: (inspect.ismethod(meth) or isinstance(meth, Callable)) and
                                   meth.__name__.startswith(COMMAND_FUNC_PREFIX))

        installed_attributes = []
        try:
            for method in methods:
                command = method[0][len(COMMAND_FUNC_PREFIX):]
                command_wrapper = _partial_passthru(method[1], self)

                self.__install_command_function(command, command_wrapper, type(cmdset).__name__)
                installed_attributes.append(method[0])

                completer_func_name = COMPLETER_FUNC_PREFIX + command
                cmd_completer = getattr(cmdset, completer_func_name, None)
                if cmd_completer is not None:
                    completer_wrapper = _partial_passthru(cmd_completer, self)
                    self.__install_completer_function(command, completer_wrapper)
                    installed_attributes.append(completer_func_name)

                help_func_name = HELP_FUNC_PREFIX + command
                cmd_help = getattr(cmdset, help_func_name, None)
                if cmd_help is not None:
                    help_wrapper = _partial_passthru(cmd_help, self)
                    self.__install_help_function(command, help_wrapper)
                    installed_attributes.append(help_func_name)

            self._installed_command_sets.append(cmdset)
        except Exception:
            for attrib in installed_attributes:
                delattr(self, attrib)
            raise

    def __install_command_function(self, command, command_wrapper, context=''):
        cmd_func_name = COMMAND_FUNC_PREFIX + command

        # Make sure command function doesn't share naem with existing attribute
        if hasattr(self, cmd_func_name):
            raise ValueError('Attribute already exists: {} ({})'.format(cmd_func_name, context))

        # Check if command has an invalid name
        valid, errmsg = self.statement_parser.is_valid_command(command)
        if not valid:
            raise ValueError("Invalid command name {!r}: {}".format(command, errmsg))

        # Check if command shares a name with an alias
        if command in self.aliases:
            self.pwarning("Deleting alias '{}' because it shares its name with a new command".format(command))
            del self.aliases[command]

        # Check if command shares a name with a macro
        if command in self.macros:
            self.pwarning("Deleting macro '{}' because it shares its name with a new command".format(command))
            del self.macros[command]

        setattr(self, cmd_func_name, command_wrapper)

    def __install_completer_function(self, cmd_name, cmd_completer):
        completer_func_name = COMPLETER_FUNC_PREFIX + cmd_name

        if hasattr(self, completer_func_name):
            raise ValueError('Attribute already exists: {}'.format(completer_func_name))
        setattr(self, completer_func_name, cmd_completer)

    def __install_help_function(self, cmd_name, cmd_completer):
        help_func_name = HELP_FUNC_PREFIX + cmd_name

        if hasattr(self, help_func_name):
            raise ValueError('Attribute already exists: {}'.format(help_func_name))
        setattr(self, help_func_name, cmd_completer)

    def uninstall_command_set(self, cmdset: CommandSet):
        """
        Uninstalls a CommandSet and unloads all associated commands
        :param cmdset: CommandSet to uninstall
        """
        if cmdset in self._installed_command_sets:
            methods = inspect.getmembers(
                cmdset,
                predicate=lambda meth: inspect.ismethod(meth) and meth.__name__.startswith(COMMAND_FUNC_PREFIX))

            for method in methods:
                cmd_name = method[0][len(COMMAND_FUNC_PREFIX):]

                delattr(self, COMMAND_FUNC_PREFIX + cmd_name)

                if hasattr(self, COMPLETER_FUNC_PREFIX + cmd_name):
                    delattr(self, COMPLETER_FUNC_PREFIX + cmd_name)
                if hasattr(self, HELP_FUNC_PREFIX + cmd_name):
                    delattr(self, HELP_FUNC_PREFIX + cmd_name)

            cmdset.on_unregister(self)
            self._installed_command_sets.remove(cmdset)

    def install_registered_command(self, cmd_name: str):
        cmd_completer = None
        cmd_help = None

        if cmd_name not in _REGISTERED_COMMANDS:
            raise KeyError('Command ' + cmd_name + ' has not been registered')

        cmd_func = _REGISTERED_COMMANDS[cmd_name]

        module = inspect.getmodule(cmd_func)

        module_funcs = [mf for mf in inspect.getmembers(module) if inspect.isfunction(mf[1])]
        for mf in module_funcs:
            if mf[0] == COMPLETER_FUNC_PREFIX + cmd_name:
                cmd_completer = mf[1]
            elif mf[0] == HELP_FUNC_PREFIX + cmd_name:
                cmd_help = mf[1]
            if cmd_completer is not None and cmd_help is not None:
                break

        self.install_command_function(cmd_name, cmd_func, cmd_completer, cmd_help)

    def install_command_function(self,
                                 cmd_name: str,
                                 cmd_func: Callable,
                                 cmd_completer: Optional[Callable],
                                 cmd_help: Optional[Callable]):
        """
        Installs a command by passing in functions for the command, completion, and help

        :param cmd_name: name of the command to install
        :param cmd_func: function to handle the command
        :param cmd_completer: completion function for the command
        :param cmd_help: help generator for the command
        :return: None
        """
        self.__install_command_function(cmd_name, types.MethodType(cmd_func, self))

        self._installed_functions.append(cmd_name)
        if cmd_completer is not None:
            self.__install_completer_function(cmd_name, types.MethodType(cmd_completer, self))
        if cmd_help is not None:
            self.__install_help_function(cmd_name, types.MethodType(cmd_help, self))

    def uninstall_command(self, cmd_name: str):
        """
        Uninstall an installed command and any associated completer or help functions
        :param cmd_name: Command to uninstall
        """
        if cmd_name in self._installed_functions:
            delattr(self, COMMAND_FUNC_PREFIX + cmd_name)

            if hasattr(self, COMPLETER_FUNC_PREFIX + cmd_name):
                delattr(self, COMPLETER_FUNC_PREFIX + cmd_name)
            if hasattr(self, HELP_FUNC_PREFIX + cmd_name):
                delattr(self, HELP_FUNC_PREFIX + cmd_name)
            self._installed_functions.remove(cmd_name)
