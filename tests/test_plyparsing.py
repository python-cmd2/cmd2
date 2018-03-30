# coding=utf-8
"""
Unit/functional testing for ply based parsing in cmd2
"""

import pytest
import ply.lex as lex
import ply.yacc as yacc

class Cmd2Command():
    pass

class Cmd2Lexer():
    """a ply.lex lexer for the cmd2 syntax.
    Once initial development is completed, this code
    should be moved into cmd2.Cmd()

    Unlike most python classes, the order of the methods matters here. The ply module
    uses introspection to create an ordered list of grammer rules, so rearranging methods
    impacts functionality.
    """
    def __init__(self):
        self.results = Cmd2Command()

    tokens = (
        'WORD', 'DQWORD', 'SQWORD',
    )

    t_WORD = r"[-A-z0-9_]+"
    t_DQWORD = r'"(?:[^"\\]|\\.)*"'
    t_SQWORD = r"'(?:[^'\\]|\\.)*'"

    def t_error(self, t):
        print("Illegal command")
        t.lexer.skip(1)

    def build_lexer(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def p_arglist_add_argument(self, p):
        'command : command word'
        p[0] = '{} {}'.format(p[1], p[2])
        self.results.command = p[0]

    def p_arglist_argument(self, p):
        'command : word'
        p[0] = p[1]
        self.results.command = p[0]

    def p_argument_word(self, p):
        'word : WORD'
        p[0] = p[1]

    def p_argument_dqword(self, p):
        'word : DQWORD'
        p[0] = p[1]

    def p_argument_sqword(self, p):
        'word : SQWORD'
        p[0] = p[1]

    def p_error(self, p):
        print("Syntax error in input!")

    def build_parser(self, **kwargs):
        self.parser = yacc.yacc(module=self, **kwargs)


@pytest.fixture
def cl():
    cl = Cmd2Lexer()
    cl.build_lexer()
    cl.build_parser()
    return cl

def test_lex_word(cl):
    cl.lexer.input('plainword')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'plainword'
    assert not cl.lexer.token()

def test_lex_dqword(cl):
    cl.lexer.input('"one word"')
    tok = cl.lexer.token()
    assert tok.type == 'DQWORD'
    assert tok.value == '"one word"'
    assert not cl.lexer.token()

def test_lex_sqword(cl):
    cl.lexer.input("'one word'")
    tok = cl.lexer.token()
    assert tok.type == 'SQWORD'
    assert tok.value == "'one word'"
    assert not cl.lexer.token()
    
def test_lex_command_with_args(cl):
    cl.lexer.input('123456 with args')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == '123456'
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'with'
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'args'

def test_parse_command(cl):
    cl.parser.parse('plainword')
    assert cl.results.command == 'plainword'

def test_parse_command_with_args(cl):
    cl.parser.parse('command with args')
    assert cl.results.command == 'command with args'

def test_parse_command_with_dqarg(cl):
    cl.parser.parse('command "with   dqarg"')
    assert cl.results.command == 'command "with   dqarg"'

def test_parse_command_with_sqarg(cl):
    cl.parser.parse("command 'with     sqarg'")
    assert cl.results.command == "command 'with     sqarg'"

def test_parse_command_with_dqarg_and_arg(cl):
    cl.parser.parse('command "with   dqarg" onemore   lastone')
    assert cl.results.command == 'command "with   dqarg" onemore lastone'

def test_parse_command_with_sqarg_and_arg(cl):
    cl.parser.parse("command 'with   dqarg' onemore   lastone")
    assert cl.results.command == "command 'with   dqarg' onemore lastone"
