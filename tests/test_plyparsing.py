# coding=utf-8
"""
Unit/functional testing for ply based parsing in cmd2
"""

import pytest
import ply.lex as lex
import ply.yacc as yacc

class Cmd2Lexer():
    """a ply.lex lexer for the cmd2 syntax.
    Once initial development is completed, this code
    should be moved into cmd2.Cmd()
    """
    tokens = (
        'WORD',
    )

    t_WORD = r"[A-Za-z_]+"

    def t_error(self, t):
        print("Illegal command")
        t.lexer.skip(1)

    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)


@pytest.fixture
def cl():
    cl = Cmd2Lexer()
    cl.build()
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
