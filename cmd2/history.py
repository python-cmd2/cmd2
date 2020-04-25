# coding=utf-8
"""
History management classes
"""

import re
from typing import List, Union

import attr

from . import utils
from .parsing import Statement


@attr.s(frozen=True)
class HistoryItem():
    """Class used to represent one command in the history list"""
    _listformat = ' {:>4}  {}'
    _ex_listformat = ' {:>4}x {}'

    statement = attr.ib(default=None, validator=attr.validators.instance_of(Statement))
    idx = attr.ib(default=None, validator=attr.validators.instance_of(int))

    def __str__(self):
        """A convenient human readable representation of the history item"""
        return self.statement.raw

    @property
    def raw(self) -> str:
        """The raw input from the user for this item.

        Proxy property for ``self.statement.raw``
        """
        return self.statement.raw

    @property
    def expanded(self) -> str:
        """Return the command as run which includes shortcuts and aliases resolved
        plus any changes made in hooks

        Proxy property for ``self.statement.expanded_command_line``
        """
        return self.statement.expanded_command_line

    def pr(self, script=False, expanded=False, verbose=False) -> str:
        """Represent this item in a pretty fashion suitable for printing.

        If you pass verbose=True, script and expanded will be ignored

        :return: pretty print string version of a HistoryItem
        """
        if verbose:
            raw = self.raw.rstrip()
            expanded = self.expanded

            ret_str = self._listformat.format(self.idx, raw)
            if raw != expanded:
                ret_str += '\n' + self._ex_listformat.format(self.idx, expanded)
        else:
            if expanded:
                ret_str = self.expanded
            else:
                ret_str = self.raw.rstrip()

                # In non-verbose mode, display raw multiline commands on 1 line
                if self.statement.multiline_command:
                    # This is an approximation and not meant to be a perfect piecing together of lines.
                    # All newlines will be converted to spaces, including the ones in quoted strings that
                    # are considered literals. Also if the final line starts with a terminator, then the
                    # terminator will have an extra space before it in the 1 line version.
                    ret_str = ret_str.replace('\n', ' ')

            # Display a numbered list if not writing to a script
            if not script:
                ret_str = self._listformat.format(self.idx, ret_str)

        return ret_str


class History(list):
    """A list of :class:`~cmd2.history.HistoryItem` objects with additional methods
    for searching and managing the list.

    :class:`~cmd2.Cmd` instantiates this class into the :data:`~cmd2.Cmd.history`
    attribute, and adds commands to it as a user enters them.

    See :ref:`features/history:History` for information about the built-in command
    which allows users to view, search, run, and save previously entered commands.

    Developers interested in accessing previously entered commands can use this
    class to gain access to the historical record.
    """
    def __init__(self, seq=()) -> None:
        super().__init__(seq)
        self.session_start_index = 0

    def start_session(self) -> None:
        """Start a new session, thereby setting the next index as the first index in the new session."""
        self.session_start_index = len(self)

    # noinspection PyMethodMayBeStatic
    def _zero_based_index(self, onebased: Union[int, str]) -> int:
        """Convert a one-based index to a zero-based index."""
        result = int(onebased)
        if result > 0:
            result -= 1
        return result

    def append(self, new: Statement) -> None:
        """Append a new statement to the end of the History list.

        :param new: Statement object which will be composed into a HistoryItem
                    and added to the end of the list
        """
        history_item = HistoryItem(new, len(self) + 1)
        super().append(history_item)

    def clear(self) -> None:
        """Remove all items from the History list."""
        super().clear()
        self.start_session()

    def get(self, index: Union[int, str]) -> HistoryItem:
        """Get item from the History list using 1-based indexing.

        :param index: optional item to get (index as either integer or string)
        :return: a single :class:`~cmd2.history.HistoryItem`
        """
        index = int(index)
        if index == 0:
            raise IndexError('The first command in history is command 1.')
        elif index < 0:
            return self[index]
        else:
            return self[index - 1]

    # This regular expression parses input for the span() method. There are five parts:
    #
    #    ^\s*                          matches any whitespace at the beginning of the
    #                                  input. This is here so you don't have to trim the input
    #
    #    (?P<start>-?[1-9]{1}\d*)?     create a capture group named 'start' which matches an
    #                                  optional minus sign, followed by exactly one non-zero
    #                                  digit, and as many other digits as you want. This group
    #                                  is optional so that we can match an input string like '..2'.
    #                                  This regex will match 1, -1, 10, -10, but not 0 or -0.
    #
    #    (?P<separator>:|(\.{2,}))?    create a capture group named 'separator' which matches either
    #                                  a colon or two periods. This group is optional so we can
    #                                  match a string like '3'
    #
    #    (?P<end>-?[1-9]{1}\d*)?       create a capture group named 'end' which matches an
    #                                  optional minus sign, followed by exactly one non-zero
    #                                  digit, and as many other digits as you want. This group is
    #                                  optional so that we can match an input string like ':'
    #                                  or '5:'. This regex will match 1, -1, 10, -10, but not
    #                                  0 or -0.
    #
    #    \s*$                          match any whitespace at the end of the input. This is here so
    #                                  you don't have to trim the input
    #
    spanpattern = re.compile(r'^\s*(?P<start>-?[1-9]\d*)?(?P<separator>:|(\.{2,}))?(?P<end>-?[1-9]\d*)?\s*$')

    def span(self, span: str, include_persisted: bool = False) -> List[HistoryItem]:
        """Return an index or slice of the History list,

        :param span: string containing an index or a slice
        :param include_persisted: if True, then retrieve full results including from persisted history
        :return: a list of HistoryItems

        This method can accommodate input in any of these forms:

            a
            -a
            a..b or a:b
            a.. or a:
            ..a or :a
            -a.. or -a:
            ..-a or :-a

        Different from native python indexing and slicing of arrays, this method
        uses 1-based array numbering. Users who are not programmers can't grok
        zero based numbering. Programmers can sometimes grok zero based numbering.
        Which reminds me, there are only two hard problems in programming:

        - naming
        - cache invalidation
        - off by one errors

        """
        if span.lower() in ('*', '-', 'all'):
            span = ':'
        results = self.spanpattern.search(span)
        if not results:
            # our regex doesn't match the input, bail out
            raise ValueError('History indices must be positive or negative integers, and may not be zero.')

        sep = results.group('separator')
        start = results.group('start')
        if start:
            start = self._zero_based_index(start)
        end = results.group('end')
        if end:
            end = int(end)
            # modify end so it's inclusive of the last element
            if end == -1:
                # -1 as the end means include the last command in the array, which in pythonic
                # terms means to not provide an ending index. If you put -1 as the ending index
                # python excludes the last item in the list.
                end = None
            elif end < -1:
                # if the ending is smaller than -1, make it one larger so it includes
                # the element (python native indices exclude the last referenced element)
                end += 1

        if start is not None and end is not None:
            # we have both start and end, return a slice of history
            result = self[start:end]
        elif start is not None and sep is not None:
            # take a slice of the array
            result = self[start:]
        elif end is not None and sep is not None:
            if include_persisted:
                result = self[:end]
            else:
                result = self[self.session_start_index:end]
        elif start is not None:
            # there was no separator so it's either a positive or negative integer
            result = [self[start]]
        else:
            # we just have a separator, return the whole list
            if include_persisted:
                result = self[:]
            else:
                result = self[self.session_start_index:]
        return result

    def str_search(self, search: str, include_persisted: bool = False) -> List[HistoryItem]:
        """Find history items which contain a given string

        :param search: the string to search for
        :param include_persisted: if True, then search full history including persisted history
        :return: a list of history items, or an empty list if the string was not found
        """
        def isin(history_item):
            """filter function for string search of history"""
            sloppy = utils.norm_fold(search)
            inraw = sloppy in utils.norm_fold(history_item.raw)
            inexpanded = sloppy in utils.norm_fold(history_item.expanded)
            return inraw or inexpanded

        search_list = self if include_persisted else self[self.session_start_index:]
        return [item for item in search_list if isin(item)]

    def regex_search(self, regex: str, include_persisted: bool = False) -> List[HistoryItem]:
        """Find history items which match a given regular expression

        :param regex: the regular expression to search for.
        :param include_persisted: if True, then search full history including persisted history
        :return: a list of history items, or an empty list if the string was not found
        """
        regex = regex.strip()
        if regex.startswith(r'/') and regex.endswith(r'/'):
            regex = regex[1:-1]
        finder = re.compile(regex, re.DOTALL | re.MULTILINE)

        def isin(hi):
            """filter function for doing a regular expression search of history"""
            return finder.search(hi.raw) or finder.search(hi.expanded)

        search_list = self if include_persisted else self[self.session_start_index:]
        return [itm for itm in search_list if isin(itm)]

    def truncate(self, max_length: int) -> None:
        """Truncate the length of the history, dropping the oldest items if necessary

        :param max_length: the maximum length of the history, if negative, all history
                           items will be deleted
        :return: nothing
        """
        if max_length <= 0:
            # remove all history
            del self[:]
        elif len(self) > max_length:
            last_element = len(self) - max_length
            del self[0:last_element]
