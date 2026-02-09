import pytest
from abstra_lua.lexer import Lexer, TK
from abstra_lua.errors import LuaSyntaxError


class TestNumbers:
    def test_integer(self):
        tokens = Lexer("42").tokens
        assert tokens[0].kind == TK.NUMBER
        assert tokens[0].value == 42

    def test_float(self):
        tokens = Lexer("3.14").tokens
        assert tokens[0].value == 3.14

    def test_float_no_leading(self):
        tokens = Lexer(".5").tokens
        assert tokens[0].value == 0.5

    def test_float_exponent(self):
        tokens = Lexer("1e10").tokens
        assert tokens[0].value == 1e10

    def test_float_negative_exponent(self):
        tokens = Lexer("1.5e-3").tokens
        assert tokens[0].value == 1.5e-3

    def test_hex_integer(self):
        tokens = Lexer("0xFF").tokens
        assert tokens[0].value == 255

    def test_hex_float(self):
        tokens = Lexer("0x1.0p4").tokens
        assert tokens[0].value == 16.0

    def test_underscore_in_number(self):
        tokens = Lexer("1_000_000").tokens
        assert tokens[0].value == 1000000


class TestStrings:
    def test_double_quoted(self):
        tokens = Lexer('"hello"').tokens
        assert tokens[0].kind == TK.STRING
        assert tokens[0].value == "hello"

    def test_single_quoted(self):
        tokens = Lexer("'hello'").tokens
        assert tokens[0].value == "hello"

    def test_escape_sequences(self):
        tokens = Lexer(r'"hello\nworld"').tokens
        assert tokens[0].value == "hello\nworld"

    def test_escape_tab(self):
        tokens = Lexer(r'"a\tb"').tokens
        assert tokens[0].value == "a\tb"

    def test_escape_backslash(self):
        tokens = Lexer(r'"a\\b"').tokens
        assert tokens[0].value == "a\\b"

    def test_escape_hex(self):
        tokens = Lexer(r'"a\x41b"').tokens
        assert tokens[0].value == "aAb"

    def test_escape_decimal(self):
        tokens = Lexer(r'"a\065b"').tokens
        assert tokens[0].value == "aAb"

    def test_escape_unicode(self):
        tokens = Lexer(r'"a\u{41}b"').tokens
        assert tokens[0].value == "aAb"

    def test_escape_z_skip_whitespace(self):
        tokens = Lexer('"a\\z   b"').tokens
        assert tokens[0].value == "ab"

    def test_long_string_simple(self):
        tokens = Lexer("[[hello]]").tokens
        assert tokens[0].value == "hello"

    def test_long_string_with_level(self):
        tokens = Lexer("[==[hello]==]").tokens
        assert tokens[0].value == "hello"

    def test_long_string_multiline(self):
        tokens = Lexer("[[line1\nline2]]").tokens
        assert tokens[0].value == "line1\nline2"

    def test_long_string_skip_first_newline(self):
        tokens = Lexer("[[\nhello]]").tokens
        assert tokens[0].value == "hello"

    def test_unfinished_string(self):
        with pytest.raises(LuaSyntaxError):
            Lexer('"hello')

    def test_unfinished_long_string(self):
        with pytest.raises(LuaSyntaxError):
            Lexer("[[hello")


class TestKeywords:
    @pytest.mark.parametrize("kw,tk", [
        ("and", TK.AND), ("break", TK.BREAK), ("do", TK.DO),
        ("else", TK.ELSE), ("elseif", TK.ELSEIF), ("end", TK.END),
        ("false", TK.FALSE), ("for", TK.FOR), ("function", TK.FUNCTION),
        ("goto", TK.GOTO), ("if", TK.IF), ("in", TK.IN),
        ("local", TK.LOCAL), ("nil", TK.NIL), ("not", TK.NOT),
        ("or", TK.OR), ("repeat", TK.REPEAT), ("return", TK.RETURN),
        ("then", TK.THEN), ("true", TK.TRUE), ("until", TK.UNTIL),
        ("while", TK.WHILE),
    ])
    def test_keyword(self, kw, tk):
        tokens = Lexer(kw).tokens
        assert tokens[0].kind == tk

    def test_identifier(self):
        tokens = Lexer("myVar").tokens
        assert tokens[0].kind == TK.NAME
        assert tokens[0].value == "myVar"

    def test_identifier_with_underscore(self):
        tokens = Lexer("_private").tokens
        assert tokens[0].kind == TK.NAME

    def test_identifier_with_digits(self):
        tokens = Lexer("var123").tokens
        assert tokens[0].kind == TK.NAME


class TestOperators:
    @pytest.mark.parametrize("op,tk", [
        ("+", TK.PLUS), ("-", TK.MINUS), ("*", TK.STAR),
        ("/", TK.SLASH), ("//", TK.IDIV), ("%", TK.PERCENT),
        ("^", TK.CARET), ("#", TK.HASH), ("&", TK.AMP),
        ("~", TK.TILDE), ("|", TK.PIPE), ("<<", TK.LSHIFT),
        (">>", TK.RSHIFT), ("==", TK.EQ), ("~=", TK.NEQ),
        ("<", TK.LT), ("<=", TK.LE), (">", TK.GT), (">=", TK.GE),
        ("=", TK.ASSIGN), ("(", TK.LPAREN), (")", TK.RPAREN),
        ("{", TK.LBRACE), ("}", TK.RBRACE), ("[", TK.LBRACKET),
        ("]", TK.RBRACKET), ("::", TK.DCOLON), (";", TK.SEMICOLON),
        (":", TK.COLON), (",", TK.COMMA), (".", TK.DOT),
        ("..", TK.DOTDOT), ("...", TK.DOTS),
    ])
    def test_operator(self, op, tk):
        tokens = Lexer(op).tokens
        assert tokens[0].kind == tk


class TestComments:
    def test_single_line_comment(self):
        tokens = Lexer("-- this is a comment\n42").tokens
        assert tokens[0].kind == TK.NUMBER
        assert tokens[0].value == 42

    def test_multiline_comment(self):
        tokens = Lexer("--[[this is\na comment]]42").tokens
        assert tokens[0].kind == TK.NUMBER

    def test_multiline_comment_with_level(self):
        tokens = Lexer("--[==[comment]==]42").tokens
        assert tokens[0].kind == TK.NUMBER


class TestLineTracking:
    def test_line_numbers(self):
        tokens = Lexer("a\nb\nc").tokens
        assert tokens[0].line == 1
        assert tokens[1].line == 2
        assert tokens[2].line == 3


class TestEdgeCases:
    def test_empty_source(self):
        tokens = Lexer("").tokens
        assert tokens[0].kind == TK.EOF

    def test_whitespace_only(self):
        tokens = Lexer("   \t\n  ").tokens
        assert tokens[0].kind == TK.EOF

    def test_unexpected_char(self):
        with pytest.raises(LuaSyntaxError):
            Lexer("@")
