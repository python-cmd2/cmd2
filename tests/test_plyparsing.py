# coding=utf-8
"""
Unit/functional testing for ply based parsing in cmd2

Notes:

- Shortcuts may have to be discarded, or handled in a different way than they
  are with pyparsing.
- 

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
        'HASHCOMMENT', 'CCOMMENT', 'WORD', 'DQWORD', 'SQWORD',
    )

    def t_HASHCOMMENT(self, t):
        r'\#.*'
        # no return value, token discarded
        pass
    
    def t_CCOMMENT(self, t):
        r'/\*.*\*/'
        # no return value, token discarded
        pass

    def t_WORD(self, t):
        r'[-\w$%\.:\?@!]+'
        return t
    
    def t_DQWORD(self, t):
        r'"(?:[^"\\]|\\.)*"'
        return t
    
    def t_SQWORD(self, t):
        r"'(?:[^'\\]|\\.)*'"
        return t

    # def t_PIPE(self, t):
    #     r'[|]'
    #     return t

    def t_error(self, t):
        print("Illegal command")
        t.lexer.skip(1)

    def build_lexer(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def p_wordlist_add_word(self, p):
        'wordlist : wordlist word'
        p[0] = '{} {}'.format(p[1], p[2])
        self.results.command = p[0]

    def p_wordlist_word(self, p):
        'wordlist : word'
        p[0] = p[1]
        self.results.command = p[0]

    def p_word_word(self, p):
        'word : WORD'
        p[0] = p[1]

    def p_word_dqword(self, p):
        'word : DQWORD'
        p[0] = p[1]

    def p_word_sqword(self, p):
        'word : SQWORD'
        p[0] = p[1]

    def p_command_and_pipe(self, p):
        "pipeline : wordlist '|' wordlist"
        p[0] = '{} | {}'.format(p[1], p[3])        
        self.results.command = p[1]
        self.results.pipeTo = p[3]

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

def test_lex_dotword(cl):
    cl.lexer.input('dot.word')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'dot.word'
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

def test_lex_hashcomment(cl):
    cl.lexer.input('hi # this is all a comment')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'hi'
    assert not cl.lexer.token()

def test_lex_ccomment(cl):
    cl.lexer.input('hi /* comment */ there')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'hi'
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'there'
    assert not cl.lexer.token()

def test_lex_command_pipe(cl):
    cl.parser.parse('command | pipeto')
    tok = cl.lexer.token()
    assert tok.type == 'WORD'
    assert tok.value == 'command'
    tok = cl.lexer.token()
    assert tok.type == 'PIPETO'
    assert tok.value == '| pipeto'
    assert not cl.lexer.token()
    
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

def test_parse_command_with_comment(cl):
    cl.parser.parse('command # with a comment')
    assert cl.results.command == 'command'

def test_parse_command_with_simple_pipe(cl):
    cl.parser.parse('command | pipeto')
    assert cl.results.command == 'command'
    assert cl.results.pipeTo == '| pipeto'

# def test_parse_command_with_complex_pipe(cl):
#     cl.parser.parse('command "with   some" args | pipeto "with  the" args')
#     assert cl.results.command == 'command "with   some" args'
#     assert cl.results.pipeTo == '| pipeto "with  the" args'
