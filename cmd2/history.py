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
    ex_listformat = '  Ex:  {}\n'

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

    def pr(self, verbose: bool) -> str:
        """Represent a HistoryItem in a pretty fashion suitable for printing.

        :return: pretty print string version of a HistoryItem
        """
        ret_str = self.listformat.format(self.idx, str(self).rstrip())
        if verbose and self != self.expanded:
            ret_str += self.ex_listformat.format(self.expanded.rstrip())

        return ret_str


class History(list):
    """ A list of HistoryItems that knows how to respond to user requests. """

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
        """Parses the input string search for a span pattern and if if found, returns a slice from the History list.

        :param raw: string potentially containing a span of the forms a..b, a:b, a:, ..b
        :return: slice from the History list
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

    def get(self, getme: Optional[Union[int, str]]=None) -> List[HistoryItem]:
        """Get an item or items from the History list using 1-based indexing.

        :param getme: optional item(s) to get (either an integer index or string to search for)
        :return: list of HistoryItems matching the retrieval criteria
        """
        if not getme:
            return self
        try:
            getme = int(getme)
            if getme < 0:
                return self[:(-1 * getme)]
            else:
                return [self[getme - 1]]
        except IndexError:
            return []
        except ValueError:
            range_result = self.rangePattern.search(getme)
            if range_result:
                start = range_result.group('start') or None
                end = range_result.group('start') or None
                if start:
                    start = int(start) - 1
                if end:
                    end = int(end)
                return self[start:end]

            getme = getme.strip()

            if getme.startswith(r'/') and getme.endswith(r'/'):
                finder = re.compile(getme[1:-1], re.DOTALL | re.MULTILINE | re.IGNORECASE)

                def isin(hi):
                    """Listcomp filter function for doing a regular expression search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    return finder.search(hi)
            else:
                def isin(hi):
                    """Listcomp filter function for doing a case-insensitive string search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    return utils.norm_fold(getme) in utils.norm_fold(hi)
            return [itm for itm in self if isin(itm)]
