#
# -*- coding: utf-8 -*-
"""Machinery for running and validating transcripts.

If the user wants to run a transcript (see docs/transcript.rst),
we need a mechanism to run each command in the transcript as
a unit test, comparing the expected output to the actual output.

This file contains the classess necessary to make that work. These
classes are used in cmd2.py::run_transcript_tests()
"""
import re
import glob
import unittest
from typing import Tuple

from . import utils


class Cmd2TestCase(unittest.TestCase):
    """A unittest class used for transcript testing.

    Subclass this, setting CmdApp, to make a unittest.TestCase class
    that will execute the commands in a transcript file and expect the
    results shown.

    See example.py
    """
    cmdapp = None

    def fetchTranscripts(self):
        self.transcripts = {}
        for fileset in self.cmdapp.testfiles:
            for fname in glob.glob(fileset):
                tfile = open(fname)
                self.transcripts[fname] = iter(tfile.readlines())
                tfile.close()
        if not len(self.transcripts):
            raise Exception("No test files found - nothing to test.")

    def setUp(self):
        if self.cmdapp:
            self.fetchTranscripts()

            # Trap stdout
            self._orig_stdout = self.cmdapp.stdout
            self.cmdapp.stdout = utils.StdSim(self.cmdapp.stdout)

    def runTest(self):  # was testall
        if self.cmdapp:
            its = sorted(self.transcripts.items())
            for (fname, transcript) in its:
                self._test_transcript(fname, transcript)

    def _test_transcript(self, fname: str, transcript):
        line_num = 0
        finished = False
        line = utils.strip_ansi(next(transcript))
        line_num += 1
        while not finished:
            # Scroll forward to where actual commands begin
            while not line.startswith(self.cmdapp.visible_prompt):
                try:
                    line = utils.strip_ansi(next(transcript))
                except StopIteration:
                    finished = True
                    break
                line_num += 1
            command = [line[len(self.cmdapp.visible_prompt):]]
            try:
                line = next(transcript)
            except StopIteration:
                line = ''
            # Read the entirety of a multi-line command
            while line.startswith(self.cmdapp.continuation_prompt):
                command.append(line[len(self.cmdapp.continuation_prompt):])
                try:
                    line = next(transcript)
                except StopIteration as exc:
                    msg = 'Transcript broke off while reading command beginning at line {} with\n{}'.format(line_num,
                                                                                                            command[0])
                    raise StopIteration(msg) from exc
                line_num += 1
            command = ''.join(command)
            # Send the command into the application and capture the resulting output
            # TODO: Should we get the return value and act if stop == True?
            self.cmdapp.onecmd_plus_hooks(command)
            result = self.cmdapp.stdout.read()
            # Read the expected result from transcript
            if utils.strip_ansi(line).startswith(self.cmdapp.visible_prompt):
                message = '\nFile {}, line {}\nCommand was:\n{}\nExpected: (nothing)\nGot:\n{}\n'.format(
                          fname, line_num, command, result)
                self.assertTrue(not (result.strip()), message)
                continue
            expected = []
            while not utils.strip_ansi(line).startswith(self.cmdapp.visible_prompt):
                expected.append(line)
                try:
                    line = next(transcript)
                except StopIteration:
                    finished = True
                    break
                line_num += 1
            expected = ''.join(expected)

            # transform the expected text into a valid regular expression
            expected = self._transform_transcript_expected(expected)
            message = '\nFile {}, line {}\nCommand was:\n{}\nExpected:\n{}\nGot:\n{}\n'.format(
                      fname, line_num, command, expected, result)
            self.assertTrue(re.match(expected, result, re.MULTILINE | re.DOTALL), message)

    def _transform_transcript_expected(self, s: str) -> str:
        r"""Parse the string with slashed regexes into a valid regex.

        Given a string like:

            Match a 10 digit phone number: /\d{3}-\d{3}-\d{4}/

        Turn it into a valid regular expression which matches the literal text
        of the string and the regular expression. We have to remove the slashes
        because they differentiate between plain text and a regular expression.
        Unless the slashes are escaped, in which case they are interpreted as
        plain text, or there is only one slash, which is treated as plain text
        also.

        Check the tests in tests/test_transcript.py to see all the edge
        cases.
        """
        regex = ''
        start = 0

        while True:
            (regex, first_slash_pos, start) = self._escaped_find(regex, s, start, False)
            if first_slash_pos == -1:
                # no more slashes, add the rest of the string and bail
                regex += re.escape(s[start:])
                break
            else:
                # there is a slash, add everything we have found so far
                # add stuff before the first slash as plain text
                regex += re.escape(s[start:first_slash_pos])
                start = first_slash_pos + 1
                # and go find the next one
                (regex, second_slash_pos, start) = self._escaped_find(regex, s, start, True)
                if second_slash_pos > 0:
                    # add everything between the slashes (but not the slashes)
                    # as a regular expression
                    regex += s[start:second_slash_pos]
                    # and change where we start looking for slashed on the
                    # turn through the loop
                    start = second_slash_pos + 1
                else:
                    # No closing slash, we have to add the first slash,
                    # and the rest of the text
                    regex += re.escape(s[start - 1:])
                    break
        return regex

    @staticmethod
    def _escaped_find(regex: str, s: str, start: int, in_regex: bool) -> Tuple[str, int, int]:
        """Find the next slash in {s} after {start} that is not preceded by a backslash.

        If we find an escaped slash, add everything up to and including it to regex,
        updating {start}. {start} therefore serves two purposes, tells us where to start
        looking for the next thing, and also tells us where in {s} we have already
        added things to {regex}

        {in_regex} specifies whether we are currently searching in a regex, we behave
        differently if we are or if we aren't.
        """
        while True:
            pos = s.find('/', start)
            if pos == -1:
                # no match, return to caller
                break
            elif pos == 0:
                # slash at the beginning of the string, so it can't be
                # escaped. We found it.
                break
            else:
                # check if the slash is preceeded by a backslash
                if s[pos - 1:pos] == '\\':
                    # it is.
                    if in_regex:
                        # add everything up to the backslash as a
                        # regular expression
                        regex += s[start:pos - 1]
                        # skip the backslash, and add the slash
                        regex += s[pos]
                    else:
                        # add everything up to the backslash as escaped
                        # plain text
                        regex += re.escape(s[start:pos - 1])
                        # and then add the slash as escaped
                        # plain text
                        regex += re.escape(s[pos])
                    # update start to show we have handled everything
                    # before it
                    start = pos + 1
                    # and continue to look
                else:
                    # slash is not escaped, this is what we are looking for
                    break
        return regex, pos, start

    def tearDown(self):
        if self.cmdapp:
            # Restore stdout
            self.cmdapp.stdout = self._orig_stdout
