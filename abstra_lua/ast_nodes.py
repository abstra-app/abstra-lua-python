from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# --------------- Expressions ---------------

@dataclass
class NilLiteral:
    line: int = 0

@dataclass
class TrueLiteral:
    line: int = 0

@dataclass
class FalseLiteral:
    line: int = 0

@dataclass
class NumberLiteral:
    value: int | float
    line: int = 0

@dataclass
class StringLiteral:
    value: str
    line: int = 0

@dataclass
class VarArg:
    line: int = 0

@dataclass
class NameRef:
    name: str
    line: int = 0

@dataclass
class IndexExpr:
    table: object
    key: object
    line: int = 0

@dataclass
class FieldExpr:
    table: object
    field: str
    line: int = 0

@dataclass
class BinOp:
    op: str
    left: object
    right: object
    line: int = 0

@dataclass
class UnaryOp:
    op: str
    operand: object
    line: int = 0

@dataclass
class FunctionCallExpr:
    func: object
    args: list
    line: int = 0

@dataclass
class MethodCallExpr:
    obj: object
    method: str
    args: list
    line: int = 0

@dataclass
class FunctionBody:
    params: list[str]
    has_varargs: bool
    body: Block
    line: int = 0

@dataclass
class TableConstructor:
    fields: list  # list of (key_expr | None, value_expr)
    line: int = 0


# --------------- Statements ---------------

@dataclass
class Block:
    stmts: list
    line: int = 0

@dataclass
class AssignStatement:
    targets: list
    values: list
    line: int = 0

@dataclass
class LocalStatement:
    names: list[str]
    attribs: list[Optional[str]]
    values: list
    line: int = 0

@dataclass
class DoBlock:
    body: Block
    line: int = 0

@dataclass
class WhileLoop:
    condition: object
    body: Block
    line: int = 0

@dataclass
class RepeatLoop:
    body: Block
    condition: object
    line: int = 0

@dataclass
class IfStatement:
    clauses: list  # list of (condition, Block), last may have condition=None for else
    line: int = 0

@dataclass
class NumericFor:
    name: str
    start: object
    stop: object
    step: object  # may be None
    body: Block
    line: int = 0

@dataclass
class GenericFor:
    names: list[str]
    iterators: list
    body: Block
    line: int = 0

@dataclass
class ReturnStatement:
    values: list
    line: int = 0

@dataclass
class BreakStatement:
    line: int = 0

@dataclass
class FunctionCallStatement:
    call: FunctionCallExpr | MethodCallExpr
    line: int = 0

@dataclass
class GotoStatement:
    label: str
    line: int = 0

@dataclass
class LabelStatement:
    name: str
    line: int = 0
