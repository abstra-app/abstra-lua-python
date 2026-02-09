from __future__ import annotations
from enum import Enum, auto
from .errors import LuaSyntaxError


class TK(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    NAME = auto()
    # Keywords
    AND = auto()
    BREAK = auto()
    DO = auto()
    ELSE = auto()
    ELSEIF = auto()
    END = auto()
    FALSE = auto()
    FOR = auto()
    FUNCTION = auto()
    GOTO = auto()
    IF = auto()
    IN = auto()
    LOCAL = auto()
    NIL = auto()
    NOT = auto()
    OR = auto()
    REPEAT = auto()
    RETURN = auto()
    THEN = auto()
    TRUE = auto()
    UNTIL = auto()
    WHILE = auto()
    # Symbols
    PLUS = auto()       # +
    MINUS = auto()      # -
    STAR = auto()       # *
    SLASH = auto()      # /
    IDIV = auto()       # //
    PERCENT = auto()    # %
    CARET = auto()      # ^
    HASH = auto()       # #
    AMP = auto()        # &
    TILDE = auto()      # ~
    PIPE = auto()       # |
    LSHIFT = auto()     # <<
    RSHIFT = auto()     # >>
    EQ = auto()         # ==
    NEQ = auto()        # ~=
    LT = auto()         # <
    LE = auto()         # <=
    GT = auto()         # >
    GE = auto()         # >=
    ASSIGN = auto()     # =
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    LBRACKET = auto()   # [
    RBRACKET = auto()   # ]
    DCOLON = auto()     # ::
    SEMICOLON = auto()  # ;
    COLON = auto()      # :
    COMMA = auto()      # ,
    DOT = auto()        # .
    DOTDOT = auto()     # ..
    DOTS = auto()       # ...
    EOF = auto()


KEYWORDS = {
    "and": TK.AND, "break": TK.BREAK, "do": TK.DO, "else": TK.ELSE,
    "elseif": TK.ELSEIF, "end": TK.END, "false": TK.FALSE, "for": TK.FOR,
    "function": TK.FUNCTION, "goto": TK.GOTO, "if": TK.IF, "in": TK.IN,
    "local": TK.LOCAL, "nil": TK.NIL, "not": TK.NOT, "or": TK.OR,
    "repeat": TK.REPEAT, "return": TK.RETURN, "then": TK.THEN,
    "true": TK.TRUE, "until": TK.UNTIL, "while": TK.WHILE,
}


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind: TK, value: object, line: int):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, line={self.line})"


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.tokens: list[Token] = []
        self._tokenize()

    def _char(self) -> str:
        return self.source[self.pos] if self.pos < len(self.source) else ""

    def _peek(self, offset: int = 1) -> str:
        p = self.pos + offset
        return self.source[p] if p < len(self.source) else ""

    def _advance(self) -> str:
        ch = self.source[self.pos]
        if ch == "\n":
            self.line += 1
        self.pos += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self.pos < len(self.source) and self.source[self.pos] == expected:
            self._advance()
            return True
        return False

    def _error(self, msg: str):
        raise LuaSyntaxError(msg, self.line)

    def _skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self._char()
            if ch in " \t\r\f\v":
                self._advance()
            elif ch == "\n":
                self._advance()
            elif ch == "-" and self._peek() == "-":
                self._skip_comment()
            else:
                break

    def _skip_comment(self):
        self.pos += 2  # skip --
        if self._char() == "[":
            level = self._count_long_bracket()
            if level >= 0:
                self._read_long_string(level)
                return
        # short comment
        while self.pos < len(self.source) and self._char() != "\n":
            self._advance()

    def _count_long_bracket(self) -> int:
        """Check for [=*[ pattern starting at current pos. Returns level or -1."""
        save = self.pos
        if self._char() != "[":
            return -1
        self.pos += 1
        level = 0
        while self.pos < len(self.source) and self.source[self.pos] == "=":
            level += 1
            self.pos += 1
        if self.pos < len(self.source) and self.source[self.pos] == "[":
            self.pos = save
            return level
        self.pos = save
        return -1

    def _read_long_string(self, level: int) -> str:
        # skip opening [=*[
        self.pos += 2 + level
        # skip immediate newline
        if self.pos < len(self.source) and self.source[self.pos] == "\n":
            self.line += 1
            self.pos += 1
        elif (
            self.pos < len(self.source)
            and self.source[self.pos] == "\r"
        ):
            self.pos += 1
            if self.pos < len(self.source) and self.source[self.pos] == "\n":
                self.pos += 1
            self.line += 1

        closing = "]" + "=" * level + "]"
        buf: list[str] = []
        while self.pos < len(self.source):
            if self.source[self.pos :].startswith(closing):
                self.pos += len(closing)
                return "".join(buf)
            ch = self._advance()
            buf.append(ch)
        self._error("unfinished long string")
        return ""  # unreachable

    def _read_string(self, quote: str) -> str:
        self._advance()  # skip opening quote
        buf: list[str] = []
        while self.pos < len(self.source):
            ch = self._char()
            if ch == quote:
                self._advance()
                return "".join(buf)
            if ch == "\n" or ch == "\r":
                self._error("unfinished string")
            if ch == "\\":
                self._advance()
                esc = self._char()
                if esc == "a":
                    buf.append("\a"); self._advance()
                elif esc == "b":
                    buf.append("\b"); self._advance()
                elif esc == "f":
                    buf.append("\f"); self._advance()
                elif esc == "n":
                    buf.append("\n"); self._advance()
                elif esc == "r":
                    buf.append("\r"); self._advance()
                elif esc == "t":
                    buf.append("\t"); self._advance()
                elif esc == "v":
                    buf.append("\v"); self._advance()
                elif esc == "\\":
                    buf.append("\\"); self._advance()
                elif esc == "'":
                    buf.append("'"); self._advance()
                elif esc == '"':
                    buf.append('"'); self._advance()
                elif esc == "\n":
                    buf.append("\n"); self._advance()
                elif esc == "\r":
                    self._advance()
                    if self._char() == "\n":
                        self._advance()
                    buf.append("\n")
                elif esc == "x":
                    self._advance()
                    hex_str = ""
                    for _ in range(2):
                        if self.pos < len(self.source) and self._char() in "0123456789abcdefABCDEF":
                            hex_str += self._advance()
                        else:
                            self._error("invalid escape sequence")
                    buf.append(chr(int(hex_str, 16)))
                elif esc == "u":
                    self._advance()
                    if self._char() != "{":
                        self._error("invalid escape sequence")
                    self._advance()
                    hex_str = ""
                    while self.pos < len(self.source) and self._char() != "}":
                        hex_str += self._advance()
                    if self._char() != "}":
                        self._error("invalid escape sequence")
                    self._advance()
                    buf.append(chr(int(hex_str, 16)))
                elif esc == "z":
                    self._advance()
                    while self.pos < len(self.source) and self._char() in " \t\n\r\f\v":
                        if self._char() == "\n":
                            self.line += 1
                        self._advance()
                elif esc.isdigit():
                    digits = ""
                    for _ in range(3):
                        if self.pos < len(self.source) and self._char().isdigit():
                            digits += self._advance()
                        else:
                            break
                    val = int(digits)
                    if val > 255:
                        self._error("decimal escape too large")
                    buf.append(chr(val))
                else:
                    self._error(f"invalid escape sequence '\\{esc}'")
            else:
                buf.append(self._advance())
        self._error("unfinished string")
        return ""  # unreachable

    def _read_number(self) -> int | float:
        start = self.pos
        is_float = False

        if self._char() == "0" and self._peek() in ("x", "X"):
            # hex
            self._advance()  # 0
            self._advance()  # x
            if not (self.pos < len(self.source) and self._char() in "0123456789abcdefABCDEF"):
                self._error("malformed number")
            while self.pos < len(self.source) and self._char() in "0123456789abcdefABCDEF_":
                self._advance()
            if self._char() == ".":
                is_float = True
                self._advance()
                while self.pos < len(self.source) and self._char() in "0123456789abcdefABCDEF_":
                    self._advance()
            if self._char() in ("p", "P"):
                is_float = True
                self._advance()
                if self._char() in ("+", "-"):
                    self._advance()
                if not (self.pos < len(self.source) and self._char().isdigit()):
                    self._error("malformed number")
                while self.pos < len(self.source) and self._char().isdigit():
                    self._advance()
        else:
            while self.pos < len(self.source) and (self._char().isdigit() or self._char() == "_"):
                self._advance()
            if self._char() == "." and self._peek() != ".":
                is_float = True
                self._advance()
                while self.pos < len(self.source) and (self._char().isdigit() or self._char() == "_"):
                    self._advance()
            if self._char() in ("e", "E"):
                is_float = True
                self._advance()
                if self._char() in ("+", "-"):
                    self._advance()
                if not (self.pos < len(self.source) and self._char().isdigit()):
                    self._error("malformed number")
                while self.pos < len(self.source) and self._char().isdigit():
                    self._advance()

        text = self.source[start : self.pos].replace("_", "")
        try:
            if is_float:
                if text.startswith(("0x", "0X")):
                    return float.fromhex(text)
                return float(text)
            if text.startswith(("0x", "0X")):
                return int(text, 16)
            return int(text)
        except ValueError:
            self._error(f"malformed number: {text}")
            return 0

    def _tokenize(self):
        while True:
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                self.tokens.append(Token(TK.EOF, None, self.line))
                return

            line = self.line
            ch = self._char()

            # Long strings
            if ch == "[":
                level = self._count_long_bracket()
                if level >= 0:
                    s = self._read_long_string(level)
                    self.tokens.append(Token(TK.STRING, s, line))
                    continue

            # Strings
            if ch in ('"', "'"):
                s = self._read_string(ch)
                self.tokens.append(Token(TK.STRING, s, line))
                continue

            # Numbers
            if ch.isdigit() or (ch == "." and self._peek().isdigit()):
                n = self._read_number()
                self.tokens.append(Token(TK.NUMBER, n, line))
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == "_":
                start = self.pos
                while self.pos < len(self.source) and (
                    self.source[self.pos].isalnum() or self.source[self.pos] == "_"
                ):
                    self.pos += 1
                word = self.source[start : self.pos]
                kind = KEYWORDS.get(word, TK.NAME)
                self.tokens.append(Token(kind, word, line))
                continue

            # Symbols
            self._advance()
            if ch == "+":
                self.tokens.append(Token(TK.PLUS, "+", line))
            elif ch == "*":
                self.tokens.append(Token(TK.STAR, "*", line))
            elif ch == "%":
                self.tokens.append(Token(TK.PERCENT, "%", line))
            elif ch == "^":
                self.tokens.append(Token(TK.CARET, "^", line))
            elif ch == "#":
                self.tokens.append(Token(TK.HASH, "#", line))
            elif ch == "&":
                self.tokens.append(Token(TK.AMP, "&", line))
            elif ch == "|":
                self.tokens.append(Token(TK.PIPE, "|", line))
            elif ch == "(":
                self.tokens.append(Token(TK.LPAREN, "(", line))
            elif ch == ")":
                self.tokens.append(Token(TK.RPAREN, ")", line))
            elif ch == "{":
                self.tokens.append(Token(TK.LBRACE, "{", line))
            elif ch == "}":
                self.tokens.append(Token(TK.RBRACE, "}", line))
            elif ch == "[":
                self.tokens.append(Token(TK.LBRACKET, "[", line))
            elif ch == "]":
                self.tokens.append(Token(TK.RBRACKET, "]", line))
            elif ch == ";":
                self.tokens.append(Token(TK.SEMICOLON, ";", line))
            elif ch == ",":
                self.tokens.append(Token(TK.COMMA, ",", line))
            elif ch == "-":
                self.tokens.append(Token(TK.MINUS, "-", line))
            elif ch == "/":
                if self._match("/"):
                    self.tokens.append(Token(TK.IDIV, "//", line))
                else:
                    self.tokens.append(Token(TK.SLASH, "/", line))
            elif ch == "<":
                if self._match("="):
                    self.tokens.append(Token(TK.LE, "<=", line))
                elif self._match("<"):
                    self.tokens.append(Token(TK.LSHIFT, "<<", line))
                else:
                    self.tokens.append(Token(TK.LT, "<", line))
            elif ch == ">":
                if self._match("="):
                    self.tokens.append(Token(TK.GE, ">=", line))
                elif self._match(">"):
                    self.tokens.append(Token(TK.RSHIFT, ">>", line))
                else:
                    self.tokens.append(Token(TK.GT, ">", line))
            elif ch == "=":
                if self._match("="):
                    self.tokens.append(Token(TK.EQ, "==", line))
                else:
                    self.tokens.append(Token(TK.ASSIGN, "=", line))
            elif ch == "~":
                if self._match("="):
                    self.tokens.append(Token(TK.NEQ, "~=", line))
                else:
                    self.tokens.append(Token(TK.TILDE, "~", line))
            elif ch == ":":
                if self._match(":"):
                    self.tokens.append(Token(TK.DCOLON, "::", line))
                else:
                    self.tokens.append(Token(TK.COLON, ":", line))
            elif ch == ".":
                if self._match("."):
                    if self._match("."):
                        self.tokens.append(Token(TK.DOTS, "...", line))
                    else:
                        self.tokens.append(Token(TK.DOTDOT, "..", line))
                else:
                    self.tokens.append(Token(TK.DOT, ".", line))
            else:
                self._error(f"unexpected character '{ch}'")
