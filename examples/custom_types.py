"""Some useful argument types.

Note that these types can be used with other argparse-compatible libraries, including
"argparse" itself.

The 'type' parameter to ArgumentParser.add_argument() must be a callable object,
typically a function. That function is called to convert the string to the Python type available
in the 'namespace' passed to your "do_xyz" command function. Thus, "type=int" works because
int("53") returns the integer value 53. If that callable object / function raises an exception
due to invalid input, the name ("repr") of the object/function will be printed in the error message
to the user. Using lambda, functools.partial, or the like will generate a callable object with a
rather opaque repr so it can be useful to have a one-line function rather than relying on a lambda,
even for a short expression.

For "types" that have some context/state, using a class with a __call__ method, and overriding
the __repr__ method, allows you to produce an error message that provides that information
to the user.
"""

from collections.abc import Iterable

import cmd2

_int_suffixes = {
    # SI number suffixes (unit prefixes):
    "K": 1_000,
    "M": 1_000_000,
    "G": 1_000_000_000,
    "T": 1_000_000_000_000,
    "P": 1_000_000_000_000_000,
    # IEC number suffixes (unit prefixes):
    "Ki": 1024,
    "Mi": 1024 * 1024,
    "Gi": 1024 * 1024 * 1024,
    "Ti": 1024 * 1024 * 1024 * 1024,
    "Pi": 1024 * 1024 * 1024 * 1024 * 1024,
}


def integer(value_str: str) -> int:
    """Will accept any base, and optional suffix like '64K'."""
    multiplier = 1
    # If there is a matching suffix, use its multiplier:
    for suffix, suffix_multiplier in _int_suffixes.items():
        if value_str.endswith(suffix):
            value_str = value_str.removesuffix(suffix)
            multiplier = suffix_multiplier
            break

    return int(value_str, 0) * multiplier


def hexadecimal(value_str: str) -> int:
    """Parse hexidecimal integer, with optional '0x' prefix."""
    return int(value_str, base=16)


class Range:
    """Useful as type for large ranges, when 'choices=range(maxval)' would be excessively large."""

    def __init__(self, firstval: int, secondval: int | None = None) -> None:
        """Construct a Range, with same syntax as 'range'.

        :param firstval: either the top end of range (if 'secondval' is missing), or the bottom end
        :param secondval: top end of range (one higher than maximum value)
        """
        if secondval is None:
            self.bottom = 0
            self.top = firstval
        else:
            self.bottom = firstval
            self.top = secondval

        self.range_str = f"[{self.bottom}..{self.top - 1}]"

    def __repr__(self) -> str:
        """Will be printed as the 'argument type' to user on syntax or range error."""
        return f"Range{self.range_str}"

    def __call__(self, arg: str) -> int:
        """Parse the string argument and checks validity."""
        val = integer(arg)
        if self.bottom <= val < self.top:
            return val
        raise ValueError(f"Value '{val}' not within {self.range_str}")


class IntSet:
    """Set of integers from a specified range.

    e.g. '5', '1-3,8', 'all'
    """

    def __init__(self, firstval: int, secondval: int | None = None) -> None:
        """Construct an IntSet, with same syntax as 'range'.

        :param firstval: either the top end of range (if 'secondval' is missing), or the bottom end
        :param secondval: top end of range (one higher than maximum value)
        """
        if secondval is None:
            self.bottom = 0
            self.top = firstval
        else:
            self.bottom = firstval
            self.top = secondval

        self.range_str = f"[{self.bottom}..{self.top - 1}]"

    def __repr__(self) -> str:
        """Will be printed as the 'argument type' to user on syntax or range error."""
        return f"IntSet{self.range_str}"

    def __call__(self, arg: str) -> Iterable[int]:
        """Parse a string into an iterable returning ints."""
        if arg == 'all':
            return range(self.bottom, self.top)

        out = []
        for piece in arg.split(','):
            if '-' in piece:
                a, b = [int(x) for x in piece.split('-', 2)]
                if a < self.bottom:
                    raise ValueError(f"Value '{a}' not within {self.range_str}")
                if b >= self.top:
                    raise ValueError(f"Value '{b}' not within {self.range_str}")
                out += list(range(a, b + 1))
            else:
                val = int(piece)
                if not self.bottom <= val < self.top:
                    raise ValueError(f"Value '{val}' not within {self.range_str}")
                out += [val]
        return out


if __name__ == '__main__':
    import argparse
    import sys

    class CustomTypesExample(cmd2.Cmd):
        example_parser = cmd2.Cmd2ArgumentParser()
        example_parser.add_argument(
            '--value', '-v', type=integer, help='Integer value, with optional K/M/G/Ki/Mi/Gi/... suffix'
        )
        example_parser.add_argument('--memory-address', '-m', type=hexadecimal, help='Memory address in hex')
        example_parser.add_argument('--year', type=Range(1900, 2000), help='Year between 1900-1999')
        example_parser.add_argument(
            '--index', dest='index_list', type=IntSet(100), help='One or more indexes 0-99. e.g. "1,3,5", "10,30-50", "all"'
        )

        @cmd2.with_argparser(example_parser)
        def do_example(self, args: argparse.Namespace) -> None:
            """The example command."""
            if args.value is not None:
                self.poutput(f"Value: {args.value}")
            if args.memory_address is not None:
                # print the value as hex, with leading "0x" + 16 hex digits + three '_' group separators:
                self.poutput(f"Address: {args.memory_address:#021_x}")
            if args.year is not None:
                self.poutput(f"Year: {args.year}")
            if args.index_list is not None:
                for index in args.index_list:
                    self.poutput(f"Process index {index}")

    app = CustomTypesExample()
    sys.exit(app.cmdloop())
