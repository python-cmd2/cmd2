# coding=utf-8
"""
History management classes
"""

import re

from typing import List, Union

from . import utils
from .parsing import Statement


class HistoryItem(str):
    """Class used to represent one command in the History list"""
    listformat = ' {:>4}  {}\n'
    ex_listformat = ' {:>4}x {}\n'

    def __new__(cls, statement: Statement):
        """Create a new instance of HistoryItem

        We must override __new__ because we are subclassing `str` which is
        immutable and takes a different number of arguments as Statement.
        """
        hi = super().__new__(cls, statement.raw)
        hi.statement = statement
        hi.idx = None
        return hi

    @property
    def expanded(self) -> str:
        """Return the command as run which includes shortcuts and aliases resolved plus any changes made in hooks"""
        return self.statement.expanded_command_line

    def pr(self, script=False, expanded=False, verbose=False) -> str:
        """Represent a HistoryItem in a pretty fashion suitable for printing.

        If you pass verbose=True, script and expanded will be ignored

        :return: pretty print string version of a HistoryItem
        """
        if verbose:
            ret_str = self.listformat.format(self.idx, str(self).rstrip())
            if self != self.expanded:
                ret_str += self.ex_listformat.format(self.idx, self.expanded.rstrip())
        else:
            if script:
                # display without entry numbers
                if expanded or self.statement.multiline_command:
                    ret_str = self.expanded.rstrip()
                else:
                    ret_str = str(self)
            else:
                # display a numbered list
                if expanded or self.statement.multiline_command:
                    ret_str = self.listformat.format(self.idx, self.expanded.rstrip())
                else:
                    ret_str = self.listformat.format(self.idx, str(self).rstrip())
        return ret_str


class History(list):
    """A list of HistoryItems that knows how to respond to user requests.

    Here are some key methods:

    select() - parse user input and return a list of relevant history items
    str_search() - return a list of history items which contain the given string
    regex_search() - return a list of history items which match a given regex
    get() - return a single element of the list, using 1 based indexing
    span() - given a 1-based slice, return the appropriate list of history items

    """

    # noinspection PyMethodMayBeStatic
    def _zero_based_index(self, onebased: Union[int, str]) -> int:
        """Convert a one-based index to a zero-based index."""
        result = int(onebased)
        if result > 0:
            result -= 1
        return result

    def append(self, new: Statement) -> None:
        """Append a HistoryItem to end of the History list

        :param new: command line to convert to HistoryItem and add to the end of the History list
        """
        new = HistoryItem(new)
        list.append(self, new)
        new.idx = len(self)

    def get(self, index: Union[int, str]) -> HistoryItem:
        """Get item from the History list using 1-based indexing.

        :param index: optional item to get (index as either integer or string)
        :return: a single HistoryItem
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

    def span(self, span: str) -> List[HistoryItem]:
        """Return an index or slice of the History list,

        :param span: string containing an index or a slice
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
        0 based numbering. Programmers can usually grok either. Which reminds me,
        there are only two hard problems in programming:

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
            result = self[:end]
        elif start is not None:
            # there was no separator so it's either a posative or negative integer
            result = [self[start]]
        else:
            # we just have a separator, return the whole list
            result = self[:]
        return result

    def str_search(self, search: str) -> List[HistoryItem]:
        """Find history items which contain a given string

        :param search: the string to search for
        :return: a list of history items, or an empty list if the string was not found
        """
        def isin(history_item):
            """filter function for string search of history"""
            sloppy = utils.norm_fold(search)
            return sloppy in utils.norm_fold(history_item) or sloppy in utils.norm_fold(history_item.expanded)
        return [item for item in self if isin(item)]

    def regex_search(self, regex: str) -> List[HistoryItem]:
        """Find history items which match a given regular expression

        :param regex: the regular expression to search for.
        :return: a list of history items, or an empty list if the string was not found
        """
        regex = regex.strip()
        if regex.startswith(r'/') and regex.endswith(r'/'):
            regex = regex[1:-1]
        finder = re.compile(regex, re.DOTALL | re.MULTILINE)

        def isin(hi):
            """filter function for doing a regular expression search of history"""
            return finder.search(hi) or finder.search(hi.expanded)
        return [itm for itm in self if isin(itm)]
