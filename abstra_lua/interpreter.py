from __future__ import annotations
import math
import operator
from typing import Any, Callable
from . import ast_nodes as ast
from .errors import LuaRuntimeError, BreakSignal, ReturnSignal
from .lua_table import LuaTable


class MultiRes(list):
    """Multiple return values from a function call or varargs."""
    pass


class LuaFunction:
    __slots__ = ("params", "has_varargs", "body", "closure", "name")

    def __init__(self, params, has_varargs, body, closure, name="?"):
        self.params = params
        self.has_varargs = has_varargs
        self.body = body
        self.closure = closure
        self.name = name


class Environment:
    __slots__ = ("vars", "parent")

    def __init__(self, parent: Environment | None = None):
        self.vars: dict[str, Any] = {}
        self.parent = parent

    def get_local(self, name: str):
        if name in self.vars:
            return self.vars[name], True
        if self.parent is not None:
            return self.parent.get_local(name)
        return None, False

    def set_existing(self, name: str, value) -> bool:
        if name in self.vars:
            self.vars[name] = value
            return True
        if self.parent is not None:
            return self.parent.set_existing(name, value)
        return False

    def define(self, name: str, value):
        self.vars[name] = value


def _is_truthy(v) -> bool:
    return v is not None and v is not False


def _first(v):
    """Adjust a value to a single result."""
    if isinstance(v, (MultiRes, list)):
        return v[0] if v else None
    return v


def _tonum(v):
    """Try to convert a value to a number."""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            if "." in s or "e" in s or "E" in s:
                return float(s)
            if s.startswith(("0x", "0X")):
                return int(s, 16)
            return int(s)
        except ValueError:
            return None
    return None


def _toint(v):
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        iv = int(v)
        if float(iv) == v:
            return iv
    if isinstance(v, str):
        n = _tonum(v)
        if n is not None:
            return _toint(n)
    return None


def _arith_coerce(a, b):
    """Coerce two values to numbers for arithmetic."""
    na, nb = _tonum(a), _tonum(b)
    return na, nb


def _lua_type(v) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "number"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, LuaTable):
        return "table"
    if isinstance(v, (LuaFunction, BuiltinFunction)):
        return "function"
    return "userdata"


class BuiltinFunction:
    __slots__ = ("name", "func")

    def __init__(self, name: str, func: Callable):
        self.name = name
        self.func = func

    def __repr__(self):
        return f"function: builtin-{self.name}"


MAX_STRING_LEN = 10_000_000  # 10MB


class Interpreter:
    def __init__(
        self,
        globals_table: LuaTable | None = None,
        max_instructions: int = 1_000_000,
        max_call_depth: int = 200,
        max_output_bytes: int = 1_000_000,
    ):
        self.globals: LuaTable = globals_table or LuaTable()
        self.call_depth = 0
        self.max_call_depth = max_call_depth
        self.max_instructions = max_instructions
        self.max_output_bytes = max_output_bytes
        self.instructions = 0
        self.output: list[str] = []
        self._output_bytes = 0

    # ---- public interface ----

    def execute(self, block: ast.Block, env: Environment | None = None):
        env = env or Environment()
        self._exec_block(block, env)

    def eval_expr(self, node, env: Environment) -> Any:
        return _first(self._eval(node, env))

    def _tick(self):
        self.instructions += 1
        if self.instructions > self.max_instructions:
            raise LuaRuntimeError("execution quota exceeded")

    # ---- block / statement execution ----

    def _exec_block(self, block: ast.Block, env: Environment):
        for stmt in block.stmts:
            self._exec_stmt(stmt, env)

    def _exec_stmt(self, stmt, env: Environment):
        self._tick()
        if isinstance(stmt, ast.AssignStatement):
            self._exec_assign(stmt, env)
        elif isinstance(stmt, ast.LocalStatement):
            self._exec_local(stmt, env)
        elif isinstance(stmt, ast.DoBlock):
            self._exec_block(stmt.body, Environment(env))
        elif isinstance(stmt, ast.WhileLoop):
            self._exec_while(stmt, env)
        elif isinstance(stmt, ast.RepeatLoop):
            self._exec_repeat(stmt, env)
        elif isinstance(stmt, ast.IfStatement):
            self._exec_if(stmt, env)
        elif isinstance(stmt, ast.NumericFor):
            self._exec_numeric_for(stmt, env)
        elif isinstance(stmt, ast.GenericFor):
            self._exec_generic_for(stmt, env)
        elif isinstance(stmt, ast.ReturnStatement):
            vals = self._eval_explist(stmt.values, env)
            raise ReturnSignal(vals)
        elif isinstance(stmt, ast.BreakStatement):
            raise BreakSignal()
        elif isinstance(stmt, ast.FunctionCallStatement):
            self._eval(stmt.call, env)
        elif isinstance(stmt, ast.GotoStatement):
            pass  # not implemented
        elif isinstance(stmt, ast.LabelStatement):
            pass  # not implemented

    def _exec_assign(self, stmt: ast.AssignStatement, env: Environment):
        vals = self._eval_explist(stmt.values, env)
        for i, target in enumerate(stmt.targets):
            val = vals[i] if i < len(vals) else None
            self._assign_target(target, val, env)

    def _assign_target(self, target, value, env: Environment):
        if isinstance(target, ast.NameRef):
            if not env.set_existing(target.name, value):
                self._set_global(target.name, value, env)
        elif isinstance(target, ast.FieldExpr):
            obj = self.eval_expr(target.table, env)
            key = target.field
            self._table_set(obj, key, value, env)
        elif isinstance(target, ast.IndexExpr):
            obj = self.eval_expr(target.table, env)
            key = self.eval_expr(target.key, env)
            self._table_set(obj, key, value, env)

    def _exec_local(self, stmt: ast.LocalStatement, env: Environment):
        vals = self._eval_explist(stmt.values, env) if stmt.values else []
        for i, name in enumerate(stmt.names):
            val = vals[i] if i < len(vals) else None
            env.define(name, val)

    def _exec_while(self, stmt: ast.WhileLoop, env: Environment):
        while _is_truthy(self.eval_expr(stmt.condition, env)):
            self._tick()
            inner = Environment(env)
            try:
                self._exec_block(stmt.body, inner)
            except BreakSignal:
                break

    def _exec_repeat(self, stmt: ast.RepeatLoop, env: Environment):
        while True:
            self._tick()
            inner = Environment(env)
            try:
                self._exec_block(stmt.body, inner)
            except BreakSignal:
                break
            # condition is evaluated in the inner scope (can see locals)
            if _is_truthy(self.eval_expr(stmt.condition, inner)):
                break

    def _exec_if(self, stmt: ast.IfStatement, env: Environment):
        for cond, body in stmt.clauses:
            if cond is None or _is_truthy(self.eval_expr(cond, env)):
                self._exec_block(body, Environment(env))
                return

    def _exec_numeric_for(self, stmt: ast.NumericFor, env: Environment):
        start = self.eval_expr(stmt.start, env)
        stop = self.eval_expr(stmt.stop, env)
        step = self.eval_expr(stmt.step, env) if stmt.step else None

        start_n = _tonum(start)
        stop_n = _tonum(stop)
        step_n = _tonum(step) if step is not None else None

        if start_n is None or stop_n is None:
            raise LuaRuntimeError("'for' initial value must be a number")
        if step is not None and step_n is None:
            raise LuaRuntimeError("'for' step must be a number")

        # Determine if we use integer or float for
        if (
            isinstance(start_n, int)
            and isinstance(stop_n, int)
            and (step_n is None or isinstance(step_n, int))
        ):
            if step_n is None:
                step_n = 1
        else:
            start_n = float(start_n)
            stop_n = float(stop_n)
            step_n = float(step_n) if step_n is not None else 1.0

        if step_n == 0:
            raise LuaRuntimeError("'for' step is zero")

        val = start_n
        while True:
            self._tick()
            if step_n > 0 and val > stop_n:
                break
            if step_n < 0 and val < stop_n:
                break
            inner = Environment(env)
            inner.define(stmt.name, val)
            try:
                self._exec_block(stmt.body, inner)
            except BreakSignal:
                break
            val = val + step_n

    def _exec_generic_for(self, stmt: ast.GenericFor, env: Environment):
        iters = self._eval_explist(stmt.iterators, env)
        iter_func = iters[0] if len(iters) > 0 else None
        state = iters[1] if len(iters) > 1 else None
        control = iters[2] if len(iters) > 2 else None

        while True:
            self._tick()
            results = self._call_function(iter_func, [state, control])
            if not results or results[0] is None:
                break
            control = results[0]
            inner = Environment(env)
            for i, name in enumerate(stmt.names):
                inner.define(name, results[i] if i < len(results) else None)
            try:
                self._exec_block(stmt.body, inner)
            except BreakSignal:
                break

    # ---- expression evaluation ----

    def _eval(self, node, env: Environment) -> Any:
        if isinstance(node, ast.NilLiteral):
            return None
        if isinstance(node, ast.TrueLiteral):
            return True
        if isinstance(node, ast.FalseLiteral):
            return False
        if isinstance(node, ast.NumberLiteral):
            return node.value
        if isinstance(node, ast.StringLiteral):
            return node.value
        if isinstance(node, ast.NameRef):
            return self._get_var(node.name, env)
        if isinstance(node, ast.VarArg):
            varargs = env.get_local("...")[0]
            if varargs is None:
                return MultiRes([])
            return MultiRes(varargs)
        if isinstance(node, ast.BinOp):
            return self._eval_binop(node, env)
        if isinstance(node, ast.UnaryOp):
            return self._eval_unaryop(node, env)
        if isinstance(node, ast.FunctionBody):
            return self._eval_funcbody(node, env)
        if isinstance(node, ast.TableConstructor):
            return self._eval_table_ctor(node, env)
        if isinstance(node, ast.FunctionCallExpr):
            return self._eval_call(node, env)
        if isinstance(node, ast.MethodCallExpr):
            return self._eval_method_call(node, env)
        if isinstance(node, ast.FieldExpr):
            obj = self.eval_expr(node.table, env)
            return self._table_get(obj, node.field, env)
        if isinstance(node, ast.IndexExpr):
            obj = self.eval_expr(node.table, env)
            key = self.eval_expr(node.key, env)
            return self._table_get(obj, key, env)
        raise LuaRuntimeError(f"cannot evaluate node: {type(node).__name__}")

    def _eval_binop(self, node: ast.BinOp, env: Environment):
        op = node.op
        # Short-circuit operators
        if op == "and":
            left = self.eval_expr(node.left, env)
            return left if not _is_truthy(left) else self.eval_expr(node.right, env)
        if op == "or":
            left = self.eval_expr(node.left, env)
            return left if _is_truthy(left) else self.eval_expr(node.right, env)

        left = self.eval_expr(node.left, env)
        right = self.eval_expr(node.right, env)

        if op == "..":
            return self._concat(left, right)
        if op in ("==", "~="):
            return self._eval_equality(op, left, right)
        if op in ("<", ">", "<=", ">="):
            return self._eval_comparison(op, left, right)

        # Arithmetic
        if op == "+":
            return self._arith(left, right, operator.add, "__add")
        if op == "-":
            return self._arith(left, right, operator.sub, "__sub")
        if op == "*":
            return self._arith(left, right, operator.mul, "__mul")
        if op == "/":
            return self._float_arith(left, right, operator.truediv, "__div")
        if op == "//":
            return self._arith(left, right, lambda a, b: self._idiv(a, b), "__idiv")
        if op == "%":
            return self._arith(left, right, lambda a, b: self._mod(a, b), "__mod")
        if op == "^":
            return self._float_arith(left, right, operator.pow, "__pow")

        # Bitwise
        if op == "&":
            return self._bitwise(left, right, operator.and_, "__band")
        if op == "|":
            return self._bitwise(left, right, operator.or_, "__bor")
        if op == "~":
            return self._bitwise(left, right, operator.xor, "__bxor")
        if op == "<<":
            return self._bitwise(left, right, operator.lshift, "__shl")
        if op == ">>":
            return self._bitwise(left, right, lambda a, b: a >> b, "__shr")

        raise LuaRuntimeError(f"unknown binary operator: {op}")

    def _eval_unaryop(self, node: ast.UnaryOp, env: Environment):
        op = node.op
        val = self.eval_expr(node.operand, env)

        if op == "-":
            n = _tonum(val)
            if n is not None:
                return -n
            mm = self._get_metamethod(val, "__unm")
            if mm is not None:
                return _first(self._call_function(mm, [val]))
            raise LuaRuntimeError(f"attempt to perform arithmetic on a {_lua_type(val)} value")

        if op == "#":
            if isinstance(val, str):
                return len(val)
            if isinstance(val, LuaTable):
                mm = self._get_metamethod(val, "__len")
                if mm is not None:
                    return _first(self._call_function(mm, [val]))
                return val.length()
            raise LuaRuntimeError(f"attempt to get length of a {_lua_type(val)} value")

        if op == "not":
            return not _is_truthy(val)

        if op == "~":
            iv = _toint(val)
            if iv is not None:
                return ~iv
            mm = self._get_metamethod(val, "__bnot")
            if mm is not None:
                return _first(self._call_function(mm, [val]))
            raise LuaRuntimeError(f"attempt to perform bitwise operation on a {_lua_type(val)} value")

        raise LuaRuntimeError(f"unknown unary operator: {op}")

    def _eval_funcbody(self, node: ast.FunctionBody, env: Environment):
        return LuaFunction(node.params, node.has_varargs, node.body, env)

    def _eval_table_ctor(self, node: ast.TableConstructor, env: Environment):
        t = LuaTable()
        array_idx = 1
        for i, (key_node, val_node) in enumerate(node.fields):
            is_last = i == len(node.fields) - 1
            if key_node is None:
                # Positional field
                if is_last:
                    val = self._eval(val_node, env)
                    if isinstance(val, MultiRes):
                        for v in val:
                            t.rawset(array_idx, v)
                            array_idx += 1
                    else:
                        t.rawset(array_idx, val)
                        array_idx += 1
                else:
                    val = self.eval_expr(val_node, env)
                    t.rawset(array_idx, val)
                    array_idx += 1
            else:
                key = self.eval_expr(key_node, env)
                val = self.eval_expr(val_node, env)
                t.rawset(key, val)
        return t

    def _eval_call(self, node: ast.FunctionCallExpr, env: Environment) -> MultiRes:
        func = self.eval_expr(node.func, env)
        args = self._eval_call_args(node.args, env)
        return MultiRes(self._call_function(func, args))

    def _eval_method_call(self, node: ast.MethodCallExpr, env: Environment) -> MultiRes:
        obj = self.eval_expr(node.obj, env)
        func = self._table_get(obj, node.method, env)
        args = self._eval_call_args(node.args, env)
        return MultiRes(self._call_function(func, [obj] + args))

    def _eval_call_args(self, arg_nodes: list, env: Environment) -> list:
        return self._eval_explist(arg_nodes, env)

    def _eval_explist(self, nodes: list, env: Environment) -> list:
        """Evaluate a list of expressions, expanding the last one if multi-valued."""
        if not nodes:
            return []
        results = []
        for i, node in enumerate(nodes):
            if i < len(nodes) - 1:
                results.append(self.eval_expr(node, env))
            else:
                val = self._eval(node, env)
                if isinstance(val, MultiRes):
                    results.extend(val)
                else:
                    results.append(val)
        return results

    # ---- function calls ----

    def _call_function(self, func, args: list) -> list:
        if func is None:
            raise LuaRuntimeError("attempt to call a nil value")

        if isinstance(func, BuiltinFunction):
            result = func.func(args)
            if result is None:
                return []
            if isinstance(result, list):
                return result
            return [result]

        if isinstance(func, LuaFunction):
            self.call_depth += 1
            if self.call_depth > self.max_call_depth:
                self.call_depth -= 1
                raise LuaRuntimeError("stack overflow")
            try:
                return self._call_lua_function(func, args)
            except RecursionError:
                raise LuaRuntimeError("stack overflow")
            finally:
                self.call_depth -= 1

        # Try __call metamethod
        mm = self._get_metamethod(func, "__call")
        if mm is not None:
            return self._call_function(mm, [func] + args)

        raise LuaRuntimeError(f"attempt to call a {_lua_type(func)} value")

    def _call_lua_function(self, func: LuaFunction, args: list) -> list:
        env = Environment(func.closure)
        # Bind parameters
        for i, param in enumerate(func.params):
            env.define(param, args[i] if i < len(args) else None)
        if func.has_varargs:
            env.define("...", args[len(func.params):])
        try:
            self._exec_block(func.body, env)
        except ReturnSignal as ret:
            return ret.values
        return []

    # ---- variable access ----

    def _get_var(self, name: str, env: Environment):
        val, found = env.get_local(name)
        if found:
            return val
        gval = self.globals.rawget(name)
        if gval is not None:
            return gval
        # Check _ENV if different from globals
        return None

    def _set_global(self, name: str, value, env: Environment):
        self.globals.rawset(name, value)

    # ---- table access with metamethods ----

    def _table_get(self, obj, key, env: Environment | None = None):
        if isinstance(obj, LuaTable):
            val = obj.rawget(key)
            if val is not None:
                return val
            mm = self._get_metamethod(obj, "__index")
            if mm is None:
                return None
            if isinstance(mm, LuaTable):
                return self._table_get(mm, key, env)
            return _first(self._call_function(mm, [obj, key]))
        if isinstance(obj, str):
            # String methods
            string_lib = self.globals.rawget("string")
            if isinstance(string_lib, LuaTable):
                return string_lib.rawget(key)
            return None
        raise LuaRuntimeError(
            f"attempt to index a {_lua_type(obj)} value"
        )

    def _table_set(self, obj, key, value, env: Environment | None = None):
        if isinstance(obj, LuaTable):
            existing = obj.rawget(key)
            if existing is not None:
                obj.rawset(key, value)
                return
            mm = self._get_metamethod(obj, "__newindex")
            if mm is None:
                obj.rawset(key, value)
                return
            if isinstance(mm, LuaTable):
                self._table_set(mm, key, value, env)
                return
            self._call_function(mm, [obj, key, value])
            return
        raise LuaRuntimeError(
            f"attempt to index a {_lua_type(obj)} value"
        )

    # ---- metamethods ----

    def _get_metamethod(self, obj, name: str):
        mt = None
        if isinstance(obj, LuaTable):
            mt = obj._metatable
        elif isinstance(obj, str):
            string_mt = self.globals.rawget("__string_mt")
            if isinstance(string_mt, LuaTable):
                mt = string_mt
        if mt is None:
            return None
        mm = mt.rawget(name)
        return mm

    # ---- arithmetic helpers ----

    def _arith(self, left, right, op_func, mm_name: str):
        na, nb = _arith_coerce(left, right)
        if na is not None and nb is not None:
            try:
                result = op_func(na, nb)
                if isinstance(result, float):
                    ires = int(result)
                    if float(ires) == result and not (isinstance(na, float) or isinstance(nb, float)):
                        return ires
                return result
            except ZeroDivisionError:
                if isinstance(na, int) and isinstance(nb, int):
                    raise LuaRuntimeError("attempt to perform 'n%0'")
                return math.copysign(math.inf, na) if na != 0 else float("nan")
        # Try metamethods
        mm = self._get_metamethod(left, mm_name) or self._get_metamethod(right, mm_name)
        if mm is not None:
            return _first(self._call_function(mm, [left, right]))
        raise LuaRuntimeError(
            f"attempt to perform arithmetic on a {_lua_type(left if na is None else right)} value"
        )

    def _float_arith(self, left, right, op_func, mm_name: str):
        na, nb = _arith_coerce(left, right)
        if na is not None and nb is not None:
            try:
                return op_func(float(na), float(nb))
            except ZeroDivisionError:
                if op_func is operator.truediv:
                    if na == 0:
                        return float("nan")
                    return math.copysign(math.inf, na) * math.copysign(1, nb)
                return float("nan")
        mm = self._get_metamethod(left, mm_name) or self._get_metamethod(right, mm_name)
        if mm is not None:
            return _first(self._call_function(mm, [left, right]))
        raise LuaRuntimeError(
            f"attempt to perform arithmetic on a {_lua_type(left if na is None else right)} value"
        )

    def _idiv(self, a, b):
        if b == 0:
            if isinstance(a, int) and isinstance(b, int):
                raise ZeroDivisionError
            if a == 0:
                return float("nan")
            return math.copysign(math.inf, a) * math.copysign(1, b)
        if isinstance(a, int) and isinstance(b, int):
            # Lua integer division floors
            return a // b
        return float(math.floor(float(a) / float(b)))

    def _mod(self, a, b):
        if b == 0:
            if isinstance(a, int) and isinstance(b, int):
                raise ZeroDivisionError
            return float("nan")
        if isinstance(a, int) and isinstance(b, int):
            return a % b
        return float(a) - math.floor(float(a) / float(b)) * float(b)

    def _bitwise(self, left, right, op_func, mm_name: str):
        ia, ib = _toint(left), _toint(right)
        if ia is not None and ib is not None:
            return op_func(ia, ib)
        mm = self._get_metamethod(left, mm_name) or self._get_metamethod(right, mm_name)
        if mm is not None:
            return _first(self._call_function(mm, [left, right]))
        raise LuaRuntimeError(
            f"attempt to perform bitwise operation on a {_lua_type(left if ia is None else right)} value"
        )

    def _concat(self, left, right):
        if isinstance(left, (str, int, float)) and isinstance(right, (str, int, float)):
            sl = self._tostring_concat(left)
            sr = self._tostring_concat(right)
            if len(sl) + len(sr) > MAX_STRING_LEN:
                raise LuaRuntimeError("string length overflow")
            return sl + sr
        mm = self._get_metamethod(left, "__concat") or self._get_metamethod(right, "__concat")
        if mm is not None:
            return _first(self._call_function(mm, [left, right]))
        raise LuaRuntimeError(
            f"attempt to concatenate a {_lua_type(left if not isinstance(left, (str, int, float)) else right)} value"
        )

    def _tostring_concat(self, v) -> str:
        if isinstance(v, str):
            return v
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return _format_float(v)
        return str(v)

    def _eval_equality(self, op: str, left, right):
        result = self._raw_equal(left, right)
        if not result:
            # Check __eq metamethod only for tables/userdata of same type
            if type(left) is type(right) and isinstance(left, LuaTable):
                mm = self._get_metamethod(left, "__eq") or self._get_metamethod(right, "__eq")
                if mm is not None:
                    result = _is_truthy(_first(self._call_function(mm, [left, right])))
        return result if op == "==" else not result

    def _raw_equal(self, a, b) -> bool:
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        # Normalize numeric comparison
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return float(a) == float(b)
        return a is b if isinstance(a, LuaTable) else a == b

    def _eval_comparison(self, op: str, left, right):
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if op == "<":  return left < right
            if op == ">":  return left > right
            if op == "<=": return left <= right
            if op == ">=": return left >= right
        elif isinstance(left, str) and isinstance(right, str):
            if op == "<":  return left < right
            if op == ">":  return left > right
            if op == "<=": return left <= right
            if op == ">=": return left >= right
        else:
            mm_name = {"<": "__lt", ">": "__lt", "<=": "__le", ">=": "__le"}[op]
            mm = self._get_metamethod(left, mm_name) or self._get_metamethod(right, mm_name)
            if mm is not None:
                if op in (">", ">="):
                    result = _is_truthy(_first(self._call_function(mm, [right, left])))
                else:
                    result = _is_truthy(_first(self._call_function(mm, [left, right])))
                return result
            raise LuaRuntimeError(
                f"attempt to compare two {_lua_type(left)} values"
            )
        return False  # unreachable

    # ---- string formatting ----

    def lua_tostring(self, v) -> str:
        if v is None:
            return "nil"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return _format_float(v)
        if isinstance(v, str):
            return v
        if isinstance(v, LuaTable):
            mm = self._get_metamethod(v, "__tostring")
            if mm is not None:
                return str(_first(self._call_function(mm, [v])))
            return repr(v)
        if isinstance(v, (LuaFunction, BuiltinFunction)):
            return f"function: 0x{id(v):016x}"
        return str(v)


def _format_float(v: float) -> str:
    if math.isinf(v):
        return "-inf" if v < 0 else "inf"
    if math.isnan(v):
        return "-nan" if math.copysign(1, v) < 0 else "nan"
    # Lua uses %.14g format
    s = f"{v:.14g}"
    # Ensure float representation has decimal point
    if "." not in s and "e" not in s and "E" not in s and "inf" not in s and "nan" not in s:
        s += ".0"
    return s
