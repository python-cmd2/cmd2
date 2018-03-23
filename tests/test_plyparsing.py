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
    """
    def __init__(self):
        self.command = Cmd2Command()

    tokens = (
        'WORD',
    )

    t_WORD = r"[A-Za-z_]+"

    def t_error(self, t):
        print("Illegal command")
        t.lexer.skip(1)

    def build_lexer(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def p_command_and_args(self, p):
        'command_and_args : command arglist'
        self.command.command = p[1]
        self.command.args = p[2]
        p[0] = self.command

    def p_command(self, p):
        'command : WORD'
        self.command.command = p[1]
        p[0] = p[1]

    def p_arglist(self, p):
        'arglist : arglist WORD'
        p[0] = '{} {}'.format(p[1], p[2])

    def p_arg(self, p):
        'arglist : WORD'
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

def test_lex_single_word(cl):
    cl.lexer.input('plainword')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'plainword'

def test_lex_command_with_args(cl):
    cl.lexer.input('command with args')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'command'
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'with'
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'args'

def test_parse_single_word(cl):
    cl.parser.parse('plainword')
    assert cl.command.command == 'plainword'

def test_parse_command_with_args(cl):
    cl.parser.parse('command with args')
    assert cl.command.command == 'command'
    assert cl.command.args == 'with args'
