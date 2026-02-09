from __future__ import annotations
from typing import Any
from .parser import Parser
from .interpreter import Interpreter, Environment, LuaFunction, BuiltinFunction, MultiRes
from .lua_table import LuaTable
from .stdlib import install_stdlib
from .errors import LuaError, LuaRuntimeError


class LuaSession:
    """A sandboxed Lua execution session.

    Args:
        max_instructions: Max VM instructions per execute/eval call (default 1M).
        max_call_depth: Max function call nesting depth (default 200).
        max_output_bytes: Max total print output in bytes (default 1MB).
    """

    def __init__(
        self,
        max_instructions: int = 1_000_000,
        max_call_depth: int = 200,
        max_output_bytes: int = 1_000_000,
    ):
        self.interpreter = Interpreter(
            max_instructions=max_instructions,
            max_call_depth=max_call_depth,
            max_output_bytes=max_output_bytes,
        )
        install_stdlib(self.interpreter)
        self._env = Environment()

    def execute(self, code: str) -> str:
        """Execute Lua code and return captured stdout as a string."""
        self.interpreter.output = []
        self.interpreter.instructions = 0
        self.interpreter._output_bytes = 0
        block = Parser(code).parse()
        self.interpreter.execute(block, self._env)
        return "\n".join(self.interpreter.output)

    def _eval_with_return(self, code: str) -> list:
        from .errors import ReturnSignal
        self.interpreter.instructions = 0
        block = Parser(code).parse()
        env = Environment(self._env)
        try:
            self.interpreter.execute(block, env)
        except ReturnSignal as ret:
            return ret.values
        return []

    def eval(self, expression: str) -> Any:
        """Evaluate a Lua expression and return the result as a Python value."""
        vals = self._eval_with_return(f"return {expression}")
        if not vals:
            return None
        return self._to_python(vals[0])

    def set(self, name: str, value: Any):
        """Set a variable in the Lua environment from a Python value."""
        lua_val = self._to_lua(value)
        # Set as local in the session env AND as global
        self._env.define(name, lua_val)
        self.interpreter.globals.rawset(name, lua_val)

    def get(self, name: str) -> Any:
        """Get a variable from the Lua environment as a Python value."""
        val, found = self._env.get_local(name)
        if not found:
            val = self.interpreter.globals.rawget(name)
        return self._to_python(val)

    def _to_lua(self, value: Any) -> Any:
        """Convert a Python value to a Lua value."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            t = LuaTable()
            for k, v in value.items():
                lk = self._to_lua(k)
                lv = self._to_lua(v)
                if lk is not None:
                    t.rawset(lk, lv)
            return t
        if isinstance(value, (list, tuple)):
            t = LuaTable()
            for i, v in enumerate(value, 1):
                t.rawset(i, self._to_lua(v))
            return t
        if callable(value):
            def wrapper(args):
                py_args = [self._to_python(a) for a in args]
                result = value(*py_args)
                return self._to_lua(result)
            return BuiltinFunction(getattr(value, '__name__', '?'), wrapper)
        raise LuaRuntimeError(f"cannot convert {type(value).__name__} to Lua value")

    def _to_python(self, value: Any) -> Any:
        """Convert a Lua value to a Python value."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, LuaTable):
            return self._table_to_python(value)
        if isinstance(value, (LuaFunction, BuiltinFunction)):
            return self._function_to_python(value)
        return value

    def _table_to_python(self, table: LuaTable) -> dict | list:
        """Convert a Lua table to a Python dict or list."""
        n = table.length()
        # Check if it's a pure sequence (list)
        has_non_int = False
        for k in table._data:
            if not isinstance(k, int) or k < 1 or k > n:
                has_non_int = True
                break

        if not has_non_int and n > 0 and len(table._data) == n:
            return [self._to_python(table.rawget(i)) for i in range(1, n + 1)]

        result = {}
        for k, v in table._data.items():
            pk = self._to_python(k) if not isinstance(k, (str, int, float)) else k
            result[pk] = self._to_python(v)
        return result

    def _function_to_python(self, func) -> callable:
        """Wrap a Lua function as a Python callable."""
        interp = self.interpreter

        def wrapper(*args):
            lua_args = [self._to_lua(a) for a in args]
            results = interp._call_function(func, lua_args)
            if not results:
                return None
            if len(results) == 1:
                return self._to_python(results[0])
            return tuple(self._to_python(r) for r in results)

        return wrapper
