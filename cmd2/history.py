# coding=utf-8
"""
History management classes
"""

import re

from typing import List, Optional, Union

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
    def _zero_based_index(self, onebased: int) -> int:
        """Convert a one-based index to a zero-based index."""
        result = onebased
        if result > 0:
            result -= 1
        return result

    def _to_index(self, raw: str) -> Optional[int]:
        if raw:
            result = self._zero_based_index(int(raw))
        else:
            result = None
        return result

    spanpattern = re.compile(r'^\s*(?P<start>-?\d+)?\s*(?P<separator>:|(\.{2,}))?\s*(?P<end>-?\d+)?\s*$')

    def span(self, raw: str) -> List[HistoryItem]:
        """Parses the input string and return a slice from the History list.

        :param raw: string potentially containing a span
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
        0 based numbering. Programmers can grok either. Which reminds me, there
        are only two hard problems in programming:

        - naming
        - cache invalidation
        - off by one errors

        """
        if raw.lower() in ('*', '-', 'all'):
            raw = ':'
        results = self.spanpattern.search(raw)
        if not results:
            raise IndexError
        if not results.group('separator'):
            return [self[self._to_index(results.group('start'))]]
        start = self._to_index(results.group('start')) or 0  # Ensure start is not None
        end = self._to_index(results.group('end'))
        reverse = False
        if end is not None:
            if end < start:
                (start, end) = (end, start)
                reverse = True
            end += 1
        result = self[start:end]
        if reverse:
            result.reverse()
        return result

    rangePattern = re.compile(r'^\s*(?P<start>[\d]+)?\s*-\s*(?P<end>[\d]+)?\s*$')

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
            raise IndexError
        elif index < 0:
            return self[index]
        else:
            return self[index - 1]



    def str_search(self, search: str) -> List[HistoryItem]:
        pass

    def regex_search(self, regex: str) -> List[HistoryItem]:
            regex = regex.strip()

            if regex.startswith(r'/') and regex.endswith(r'/'):
                finder = re.compile(regex[1:-1], re.DOTALL | re.MULTILINE | re.IGNORECASE)

                def isin(hi):
                    """Listcomp filter function for doing a regular expression search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    return finder.search(hi) or finder.search(hi.expanded)
            else:
                def isin(hi):
                    """Listcomp filter function for doing a case-insensitive string search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    srch = utils.norm_fold(regex)
                    return srch in utils.norm_fold(hi) or srch in utils.norm_fold(hi.expanded)
            return [itm for itm in self if isin(itm)]
