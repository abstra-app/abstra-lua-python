from __future__ import annotations
from .lexer import TK, Token, Lexer
from .errors import LuaSyntaxError
from . import ast_nodes as ast


# Operator precedence for binary operators (higher = tighter)
_BINARY_OPS: dict[TK, tuple[int, str]] = {
    TK.OR:      (1, "left"),
    TK.AND:     (2, "left"),
    TK.LT:      (3, "left"),
    TK.GT:      (3, "left"),
    TK.LE:      (3, "left"),
    TK.GE:      (3, "left"),
    TK.NEQ:     (3, "left"),
    TK.EQ:      (3, "left"),
    TK.PIPE:    (4, "left"),
    TK.TILDE:   (5, "left"),
    TK.AMP:     (6, "left"),
    TK.LSHIFT:  (7, "left"),
    TK.RSHIFT:  (7, "left"),
    TK.DOTDOT:  (8, "right"),
    TK.PLUS:    (9, "left"),
    TK.MINUS:   (9, "left"),
    TK.STAR:    (10, "left"),
    TK.SLASH:   (10, "left"),
    TK.IDIV:    (10, "left"),
    TK.PERCENT: (10, "left"),
    TK.CARET:   (12, "right"),
}

_BINOP_NAMES: dict[TK, str] = {
    TK.PLUS: "+", TK.MINUS: "-", TK.STAR: "*", TK.SLASH: "/",
    TK.IDIV: "//", TK.PERCENT: "%", TK.CARET: "^",
    TK.AMP: "&", TK.TILDE: "~", TK.PIPE: "|",
    TK.LSHIFT: "<<", TK.RSHIFT: ">>",
    TK.EQ: "==", TK.NEQ: "~=", TK.LT: "<", TK.LE: "<=",
    TK.GT: ">", TK.GE: ">=",
    TK.AND: "and", TK.OR: "or", TK.DOTDOT: "..",
}


class Parser:
    def __init__(self, source: str):
        lexer = Lexer(source)
        self.tokens = lexer.tokens
        self.pos = 0

    # ---- helpers ----

    def _cur(self) -> Token:
        return self.tokens[self.pos]

    def _peek_kind(self) -> TK:
        return self.tokens[self.pos].kind

    def _line(self) -> int:
        return self._cur().line

    def _check(self, kind: TK) -> bool:
        return self._peek_kind() == kind

    def _match(self, kind: TK) -> Token | None:
        if self._check(kind):
            tok = self._cur()
            self.pos += 1
            return tok
        return None

    def _expect(self, kind: TK, msg: str = "") -> Token:
        tok = self._match(kind)
        if tok is None:
            what = msg or f"'{kind.name}'"
            self._error(f"expected {what}, got '{self._cur().value}'")
        return tok

    def _error(self, msg: str):
        raise LuaSyntaxError(msg, self._line())

    # ---- top-level ----

    def parse(self) -> ast.Block:
        block = self._parse_block()
        self._expect(TK.EOF, "end of input")
        return block

    # ---- block ----

    def _parse_block(self) -> ast.Block:
        line = self._line()
        stmts: list = []
        while True:
            self._skip_semicolons()
            if self._is_block_end():
                break
            stmt = self._parse_statement()
            if stmt is not None:
                stmts.append(stmt)
        return ast.Block(stmts, line)

    def _is_block_end(self) -> bool:
        return self._peek_kind() in (
            TK.EOF, TK.END, TK.ELSE, TK.ELSEIF, TK.UNTIL,
        )

    def _skip_semicolons(self):
        while self._match(TK.SEMICOLON):
            pass

    # ---- statements ----

    def _parse_statement(self):
        k = self._peek_kind()
        if k == TK.IF:
            return self._parse_if()
        if k == TK.WHILE:
            return self._parse_while()
        if k == TK.DO:
            return self._parse_do()
        if k == TK.FOR:
            return self._parse_for()
        if k == TK.REPEAT:
            return self._parse_repeat()
        if k == TK.FUNCTION:
            return self._parse_function_stat()
        if k == TK.LOCAL:
            return self._parse_local()
        if k == TK.RETURN:
            return self._parse_return()
        if k == TK.BREAK:
            return self._parse_break()
        if k == TK.GOTO:
            return self._parse_goto()
        if k == TK.DCOLON:
            return self._parse_label()
        # assignment or function call
        return self._parse_expr_stat()

    def _parse_if(self):
        line = self._line()
        self._expect(TK.IF)
        clauses = []

        cond = self._parse_expression()
        self._expect(TK.THEN, "'then'")
        body = self._parse_block()
        clauses.append((cond, body))

        while self._match(TK.ELSEIF):
            cond = self._parse_expression()
            self._expect(TK.THEN, "'then'")
            body = self._parse_block()
            clauses.append((cond, body))

        if self._match(TK.ELSE):
            body = self._parse_block()
            clauses.append((None, body))

        self._expect(TK.END, "'end'")
        return ast.IfStatement(clauses, line)

    def _parse_while(self):
        line = self._line()
        self._expect(TK.WHILE)
        cond = self._parse_expression()
        self._expect(TK.DO, "'do'")
        body = self._parse_block()
        self._expect(TK.END, "'end'")
        return ast.WhileLoop(cond, body, line)

    def _parse_do(self):
        line = self._line()
        self._expect(TK.DO)
        body = self._parse_block()
        self._expect(TK.END, "'end'")
        return ast.DoBlock(body, line)

    def _parse_for(self):
        line = self._line()
        self._expect(TK.FOR)
        name_tok = self._expect(TK.NAME, "variable name")

        if self._match(TK.ASSIGN):
            # numeric for
            start = self._parse_expression()
            self._expect(TK.COMMA, "','")
            stop = self._parse_expression()
            step = None
            if self._match(TK.COMMA):
                step = self._parse_expression()
            self._expect(TK.DO, "'do'")
            body = self._parse_block()
            self._expect(TK.END, "'end'")
            return ast.NumericFor(name_tok.value, start, stop, step, body, line)
        else:
            # generic for
            names = [name_tok.value]
            while self._match(TK.COMMA):
                names.append(self._expect(TK.NAME, "variable name").value)
            self._expect(TK.IN, "'in'")
            iters = self._parse_expression_list()
            self._expect(TK.DO, "'do'")
            body = self._parse_block()
            self._expect(TK.END, "'end'")
            return ast.GenericFor(names, iters, body, line)

    def _parse_repeat(self):
        line = self._line()
        self._expect(TK.REPEAT)
        body = self._parse_block()
        self._expect(TK.UNTIL, "'until'")
        cond = self._parse_expression()
        return ast.RepeatLoop(body, cond, line)

    def _parse_function_stat(self):
        line = self._line()
        self._expect(TK.FUNCTION)
        # funcname ::= Name {'.' Name} [':' Name]
        name_tok = self._expect(TK.NAME, "function name")
        target: object = ast.NameRef(name_tok.value, line)
        is_method = False

        while self._match(TK.DOT):
            field = self._expect(TK.NAME, "field name")
            target = ast.FieldExpr(target, field.value, line)

        if self._match(TK.COLON):
            method_name = self._expect(TK.NAME, "method name")
            target = ast.FieldExpr(target, method_name.value, line)
            is_method = True

        func_body = self._parse_funcbody(is_method, line)
        # Desugar to assignment
        return ast.AssignStatement([target], [func_body], line)

    def _parse_local(self):
        line = self._line()
        self._expect(TK.LOCAL)

        if self._match(TK.FUNCTION):
            name = self._expect(TK.NAME, "function name")
            func_body = self._parse_funcbody(False, line)
            return ast.LocalStatement(
                [name.value], [None], [func_body], line
            )

        # local namelist ['=' explist]
        names = [self._expect(TK.NAME, "variable name").value]
        attribs: list[str | None] = [self._parse_attrib()]

        while self._match(TK.COMMA):
            names.append(self._expect(TK.NAME, "variable name").value)
            attribs.append(self._parse_attrib())

        values: list = []
        if self._match(TK.ASSIGN):
            values = self._parse_expression_list()

        return ast.LocalStatement(names, attribs, values, line)

    def _parse_attrib(self) -> str | None:
        if self._match(TK.LT):
            attr = self._expect(TK.NAME, "attribute name")
            self._expect(TK.GT, "'>'")
            return attr.value
        return None

    def _parse_return(self):
        line = self._line()
        self._expect(TK.RETURN)
        values: list = []
        if not self._is_block_end() and not self._check(TK.SEMICOLON):
            values = self._parse_expression_list()
        self._match(TK.SEMICOLON)
        return ast.ReturnStatement(values, line)

    def _parse_break(self):
        line = self._line()
        self._expect(TK.BREAK)
        return ast.BreakStatement(line)

    def _parse_goto(self):
        line = self._line()
        self._expect(TK.GOTO)
        name = self._expect(TK.NAME, "label name")
        return ast.GotoStatement(name.value, line)

    def _parse_label(self):
        line = self._line()
        self._expect(TK.DCOLON)
        name = self._expect(TK.NAME, "label name")
        self._expect(TK.DCOLON, "'::'")
        return ast.LabelStatement(name.value, line)

    def _parse_expr_stat(self):
        """Parse assignment or function-call statement."""
        line = self._line()
        expr = self._parse_suffixed_expr()

        # Multi-assignment: expr {',' expr} '=' explist
        if self._check(TK.COMMA) or self._check(TK.ASSIGN):
            targets = [expr]
            while self._match(TK.COMMA):
                targets.append(self._parse_suffixed_expr())
            self._expect(TK.ASSIGN, "'='")
            values = self._parse_expression_list()
            for t in targets:
                if not isinstance(t, (ast.NameRef, ast.IndexExpr, ast.FieldExpr)):
                    self._error("invalid assignment target")
            return ast.AssignStatement(targets, values, line)

        # Must be a function call
        if isinstance(expr, (ast.FunctionCallExpr, ast.MethodCallExpr)):
            return ast.FunctionCallStatement(expr, line)

        self._error("unexpected expression statement")

    # ---- expressions ----

    def _parse_expression(self, min_prec: int = 0):
        left = self._parse_unary()

        while True:
            k = self._peek_kind()
            if k not in _BINARY_OPS:
                break
            prec, assoc = _BINARY_OPS[k]
            if prec < min_prec:
                break
            op_tok = self._cur()
            self.pos += 1
            next_prec = prec + 1 if assoc == "left" else prec
            right = self._parse_expression(next_prec)
            op_name = _BINOP_NAMES[k]
            left = ast.BinOp(op_name, left, right, op_tok.line)

        return left

    def _parse_unary(self):
        k = self._peek_kind()
        if k == TK.NOT:
            line = self._line()
            self.pos += 1
            operand = self._parse_expression(11)
            return ast.UnaryOp("not", operand, line)
        if k == TK.HASH:
            line = self._line()
            self.pos += 1
            operand = self._parse_expression(11)
            return ast.UnaryOp("#", operand, line)
        if k == TK.MINUS:
            line = self._line()
            self.pos += 1
            operand = self._parse_expression(11)
            return ast.UnaryOp("-", operand, line)
        if k == TK.TILDE:
            line = self._line()
            self.pos += 1
            operand = self._parse_expression(11)
            return ast.UnaryOp("~", operand, line)
        return self._parse_suffixed_expr()

    def _parse_suffixed_expr(self):
        expr = self._parse_primary()
        while True:
            k = self._peek_kind()
            if k == TK.DOT:
                self.pos += 1
                field = self._expect(TK.NAME, "field name")
                expr = ast.FieldExpr(expr, field.value, field.line)
            elif k == TK.LBRACKET:
                line = self._line()
                self.pos += 1
                key = self._parse_expression()
                self._expect(TK.RBRACKET, "']'")
                expr = ast.IndexExpr(expr, key, line)
            elif k == TK.COLON:
                line = self._line()
                self.pos += 1
                method = self._expect(TK.NAME, "method name")
                args = self._parse_call_args()
                expr = ast.MethodCallExpr(expr, method.value, args, line)
            elif k in (TK.LPAREN, TK.LBRACE, TK.STRING):
                line = self._line()
                args = self._parse_call_args()
                expr = ast.FunctionCallExpr(expr, args, line)
            else:
                break
        return expr

    def _parse_call_args(self) -> list:
        if self._match(TK.LPAREN):
            args: list = []
            if not self._check(TK.RPAREN):
                args = self._parse_expression_list()
            self._expect(TK.RPAREN, "')'")
            return args
        if self._check(TK.LBRACE):
            return [self._parse_table_constructor()]
        if self._check(TK.STRING):
            tok = self._cur()
            self.pos += 1
            return [ast.StringLiteral(tok.value, tok.line)]
        self._error("function arguments expected")
        return []

    def _parse_primary(self):
        k = self._peek_kind()
        if k == TK.NAME:
            tok = self._cur()
            self.pos += 1
            return ast.NameRef(tok.value, tok.line)
        if k == TK.LPAREN:
            self.pos += 1
            expr = self._parse_expression()
            self._expect(TK.RPAREN, "')'")
            return expr
        return self._parse_simple_expr()

    def _parse_simple_expr(self):
        k = self._peek_kind()
        tok = self._cur()
        if k == TK.NUMBER:
            self.pos += 1
            return ast.NumberLiteral(tok.value, tok.line)
        if k == TK.STRING:
            self.pos += 1
            return ast.StringLiteral(tok.value, tok.line)
        if k == TK.NIL:
            self.pos += 1
            return ast.NilLiteral(tok.line)
        if k == TK.TRUE:
            self.pos += 1
            return ast.TrueLiteral(tok.line)
        if k == TK.FALSE:
            self.pos += 1
            return ast.FalseLiteral(tok.line)
        if k == TK.DOTS:
            self.pos += 1
            return ast.VarArg(tok.line)
        if k == TK.FUNCTION:
            return self._parse_function_expr()
        if k == TK.LBRACE:
            return self._parse_table_constructor()
        self._error(f"unexpected symbol '{tok.value}'")

    def _parse_function_expr(self):
        line = self._line()
        self._expect(TK.FUNCTION)
        return self._parse_funcbody(False, line)

    def _parse_funcbody(self, is_method: bool, line: int) -> ast.FunctionBody:
        self._expect(TK.LPAREN, "'('")
        params: list[str] = []
        has_varargs = False

        if is_method:
            params.append("self")

        if not self._check(TK.RPAREN):
            if self._check(TK.DOTS):
                has_varargs = True
                self.pos += 1
            else:
                params.append(self._expect(TK.NAME, "parameter name").value)
                while self._match(TK.COMMA):
                    if self._check(TK.DOTS):
                        has_varargs = True
                        self.pos += 1
                        break
                    params.append(self._expect(TK.NAME, "parameter name").value)

        self._expect(TK.RPAREN, "')'")
        body = self._parse_block()
        self._expect(TK.END, "'end'")
        return ast.FunctionBody(params, has_varargs, body, line)

    def _parse_table_constructor(self) -> ast.TableConstructor:
        line = self._line()
        self._expect(TK.LBRACE, "'{'")
        fields: list = []

        while not self._check(TK.RBRACE):
            if self._check(TK.LBRACKET):
                # [expr] = expr
                self.pos += 1
                key = self._parse_expression()
                self._expect(TK.RBRACKET, "']'")
                self._expect(TK.ASSIGN, "'='")
                val = self._parse_expression()
                fields.append((key, val))
            elif self._check(TK.NAME) and self._tokens_ahead_is_assign():
                # name = expr
                name_tok = self._cur()
                self.pos += 1
                self._expect(TK.ASSIGN, "'='")
                val = self._parse_expression()
                fields.append((ast.StringLiteral(name_tok.value, name_tok.line), val))
            else:
                # positional
                val = self._parse_expression()
                fields.append((None, val))

            if not self._match(TK.COMMA) and not self._match(TK.SEMICOLON):
                break

        self._expect(TK.RBRACE, "'}'")
        return ast.TableConstructor(fields, line)

    def _tokens_ahead_is_assign(self) -> bool:
        return self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].kind == TK.ASSIGN

    def _parse_expression_list(self) -> list:
        exprs = [self._parse_expression()]
        while self._match(TK.COMMA):
            exprs.append(self._parse_expression())
        return exprs
