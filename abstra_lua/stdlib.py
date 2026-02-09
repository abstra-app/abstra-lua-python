from __future__ import annotations
import math
import random
import re
import time
from typing import TYPE_CHECKING
from .errors import LuaRuntimeError
from .lua_table import LuaTable
from .interpreter import (
    Interpreter, BuiltinFunction, LuaFunction, _lua_type,
    _tonum, _toint, _is_truthy, _first, MultiRes, _format_float,
)

if TYPE_CHECKING:
    pass


def install_stdlib(interp: Interpreter):
    """Install standard library functions into the interpreter's globals."""
    g = interp.globals

    def _bf(name, fn):
        g.rawset(name, BuiltinFunction(name, fn))

    # ---------- basic functions ----------

    def _print(args):
        parts = [interp.lua_tostring(a) for a in args]
        line = "\t".join(parts)
        interp._output_bytes += len(line) + 1
        if interp._output_bytes > interp.max_output_bytes:
            raise LuaRuntimeError("output limit exceeded")
        interp.output.append(line)

    def _type(args):
        return _lua_type(args[0] if args else None)

    def _tostring(args):
        return interp.lua_tostring(args[0] if args else None)

    def _tonumber(args):
        v = args[0] if args else None
        base = args[1] if len(args) > 1 else None
        if base is not None:
            b = _toint(base)
            if b is None:
                raise LuaRuntimeError("bad argument #2 to 'tonumber' (number expected)")
            if not isinstance(v, str):
                raise LuaRuntimeError("bad argument #1 to 'tonumber' (string expected)")
            try:
                return int(v.strip(), b)
            except ValueError:
                return [None]
        result = _tonum(v)
        return result if result is not None else [None]

    def _assert(args):
        v = args[0] if args else None
        if not _is_truthy(v):
            msg = args[1] if len(args) > 1 else "assertion failed!"
            raise LuaRuntimeError(str(msg))
        return list(args)

    def _error(args):
        msg = args[0] if args else None
        raise LuaRuntimeError(interp.lua_tostring(msg) if msg is not None else "nil")

    def _pcall(args):
        func = args[0] if args else None
        call_args = list(args[1:])
        try:
            results = interp._call_function(func, call_args)
            return [True] + results
        except (LuaRuntimeError, LuaError) as e:
            return [False, str(e)]
        except Exception as e:
            return [False, str(e)]

    def _xpcall(args):
        func = args[0] if args else None
        handler = args[1] if len(args) > 1 else None
        call_args = list(args[2:])
        try:
            results = interp._call_function(func, call_args)
            return [True] + results
        except Exception as e:
            try:
                hresults = interp._call_function(handler, [str(e)])
                return [False] + hresults
            except Exception:
                return [False, str(e)]

    def _ipairs(args):
        t = args[0] if args else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'ipairs' (table expected)")
        i = [0]  # mutable counter in closure

        def _iter(iter_args):
            i[0] += 1
            val = t.rawget(i[0])
            if val is None:
                return [None]
            return [i[0], val]

        return [BuiltinFunction("ipairs_iterator", _iter), t, 0]

    def _pairs(args):
        t = args[0] if args else None
        if not isinstance(t, LuaTable):
            # Check __pairs metamethod
            mm = interp._get_metamethod(t, "__pairs")
            if mm is not None:
                return interp._call_function(mm, [t])
            raise LuaRuntimeError("bad argument #1 to 'pairs' (table expected)")

        def _next_fn(nargs):
            key = nargs[1] if len(nargs) > 1 else None
            k, v = t.next(key)
            if k is None:
                return [None]
            return [k, v]

        return [BuiltinFunction("next", _next_fn), t, None]

    def _next(args):
        t = args[0] if args else None
        key = args[1] if len(args) > 1 else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'next' (table expected)")
        k, v = t.next(key)
        if k is None:
            return [None]
        return [k, v]

    def _select(args):
        idx = args[0] if args else None
        rest = list(args[1:])
        if idx == "#":
            return len(rest)
        n = _toint(idx)
        if n is None:
            raise LuaRuntimeError("bad argument #1 to 'select' (number or string expected)")
        if n < 0:
            n = len(rest) + 1 + n
        if n < 1:
            raise LuaRuntimeError("bad argument #1 to 'select' (index out of range)")
        return rest[n - 1:]

    def _rawget(args):
        t = args[0] if args else None
        k = args[1] if len(args) > 1 else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'rawget' (table expected)")
        return [t.rawget(k)]

    def _rawset(args):
        t = args[0] if args else None
        k = args[1] if len(args) > 1 else None
        v = args[2] if len(args) > 2 else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'rawset' (table expected)")
        t.rawset(k, v)
        return t

    def _rawlen(args):
        v = args[0] if args else None
        if isinstance(v, LuaTable):
            return v.length()
        if isinstance(v, str):
            return len(v)
        raise LuaRuntimeError("bad argument #1 to 'rawlen' (table or string expected)")

    def _rawequal(args):
        a = args[0] if args else None
        b = args[1] if len(args) > 1 else None
        return interp._raw_equal(a, b)

    def _setmetatable(args):
        t = args[0] if args else None
        mt = args[1] if len(args) > 1 else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'setmetatable' (table expected)")
        if mt is not None and not isinstance(mt, LuaTable):
            raise LuaRuntimeError("bad argument #2 to 'setmetatable' (nil or table expected)")
        # Check __metatable
        if t._metatable is not None:
            prot = t._metatable.rawget("__metatable")
            if prot is not None:
                raise LuaRuntimeError("cannot change a protected metatable")
        t._metatable = mt
        return t

    def _getmetatable(args):
        v = args[0] if args else None
        if isinstance(v, LuaTable) and v._metatable is not None:
            prot = v._metatable.rawget("__metatable")
            if prot is not None:
                return prot
            return v._metatable
        return [None]

    def _unpack(args):
        t = args[0] if args else None
        i = _toint(args[1]) if len(args) > 1 else 1
        j = _toint(args[2]) if len(args) > 2 else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'unpack' (table expected)")
        if i is None:
            i = 1
        if j is None:
            j = t.length()
        result = []
        for idx in range(i, j + 1):
            result.append(t.rawget(idx))
        return result

    # ---------- register basic functions ----------

    _bf("print", _print)
    _bf("type", _type)
    _bf("tostring", _tostring)
    _bf("tonumber", _tonumber)
    _bf("assert", _assert)
    _bf("error", _error)
    _bf("pcall", _pcall)
    _bf("xpcall", _xpcall)
    _bf("ipairs", _ipairs)
    _bf("pairs", _pairs)
    _bf("next", _next)
    _bf("select", _select)
    _bf("rawget", _rawget)
    _bf("rawset", _rawset)
    _bf("rawlen", _rawlen)
    _bf("rawequal", _rawequal)
    _bf("setmetatable", _setmetatable)
    _bf("getmetatable", _getmetatable)
    _bf("unpack", _unpack)

    # ---------- table library ----------

    table_lib = LuaTable()

    def _tbl_insert(args):
        t = args[0] if args else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'insert' (table expected)")
        if len(args) == 2:
            # append
            pos = t.length() + 1
            val = args[1]
        elif len(args) >= 3:
            pos = _toint(args[1])
            val = args[2]
            if pos is None:
                raise LuaRuntimeError("bad argument #2 to 'insert' (number expected)")
            # shift elements
            n = t.length()
            for i in range(n, pos - 1, -1):
                t.rawset(i + 1, t.rawget(i))
        else:
            raise LuaRuntimeError("wrong number of arguments to 'insert'")
        t.rawset(pos, val)

    def _tbl_remove(args):
        t = args[0] if args else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'remove' (table expected)")
        n = t.length()
        pos = _toint(args[1]) if len(args) > 1 else n
        if pos is None:
            raise LuaRuntimeError("bad argument #2 to 'remove' (number expected)")
        val = t.rawget(pos)
        for i in range(pos, n):
            t.rawset(i, t.rawget(i + 1))
        t.rawset(n, None)
        return val

    def _tbl_sort(args):
        t = args[0] if args else None
        comp = args[1] if len(args) > 1 else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'sort' (table expected)")
        n = t.length()
        items = [t.rawget(i) for i in range(1, n + 1)]

        import functools

        if comp is not None:
            def cmp_func(a, b):
                result = interp._call_function(comp, [a, b])
                if _is_truthy(_first(result)):
                    return -1
                result2 = interp._call_function(comp, [b, a])
                if _is_truthy(_first(result2)):
                    return 1
                return 0
            items.sort(key=functools.cmp_to_key(cmp_func))
        else:
            def default_cmp(a, b):
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    return -1 if a < b else (1 if a > b else 0)
                if isinstance(a, str) and isinstance(b, str):
                    return -1 if a < b else (1 if a > b else 0)
                raise LuaRuntimeError("attempt to compare mixed types")
            items.sort(key=functools.cmp_to_key(default_cmp))

        for i, v in enumerate(items, 1):
            t.rawset(i, v)

    def _tbl_concat(args):
        t = args[0] if args else None
        sep = args[1] if len(args) > 1 else ""
        i = _toint(args[2]) if len(args) > 2 else 1
        j = _toint(args[3]) if len(args) > 3 else None
        if not isinstance(t, LuaTable):
            raise LuaRuntimeError("bad argument #1 to 'concat' (table expected)")
        if not isinstance(sep, str):
            sep = interp.lua_tostring(sep)
        if i is None:
            i = 1
        if j is None:
            j = t.length()
        parts = []
        for idx in range(i, j + 1):
            v = t.rawget(idx)
            if not isinstance(v, (str, int, float)):
                raise LuaRuntimeError(f"invalid value (table) at index {idx} in table for 'concat'")
            parts.append(interp.lua_tostring(v))
        return sep.join(parts)

    def _tbl_move(args):
        a1 = args[0] if args else None
        f = _toint(args[1]) if len(args) > 1 else None
        e = _toint(args[2]) if len(args) > 2 else None
        t_pos = _toint(args[3]) if len(args) > 3 else None
        a2 = args[4] if len(args) > 4 else a1
        if not isinstance(a1, LuaTable) or not isinstance(a2, LuaTable):
            raise LuaRuntimeError("bad argument to 'move'")
        if f is None or e is None or t_pos is None:
            raise LuaRuntimeError("bad argument to 'move'")
        if e >= f:
            n = e - f
            if t_pos > f:
                for i in range(n, -1, -1):
                    a2.rawset(t_pos + i, a1.rawget(f + i))
            else:
                for i in range(0, n + 1):
                    a2.rawset(t_pos + i, a1.rawget(f + i))
        return a2

    def _tbl_unpack(args):
        return _unpack(args)

    def _tbl_pack(args):
        t = LuaTable()
        for i, v in enumerate(args, 1):
            t.rawset(i, v)
        t.rawset("n", len(args))
        return t

    table_lib.rawset("insert", BuiltinFunction("table.insert", _tbl_insert))
    table_lib.rawset("remove", BuiltinFunction("table.remove", _tbl_remove))
    table_lib.rawset("sort", BuiltinFunction("table.sort", _tbl_sort))
    table_lib.rawset("concat", BuiltinFunction("table.concat", _tbl_concat))
    table_lib.rawset("move", BuiltinFunction("table.move", _tbl_move))
    table_lib.rawset("unpack", BuiltinFunction("table.unpack", _tbl_unpack))
    table_lib.rawset("pack", BuiltinFunction("table.pack", _tbl_pack))
    g.rawset("table", table_lib)

    # ---------- string library ----------

    string_lib = LuaTable()

    def _str_byte(args):
        s = args[0] if args else None
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'byte' (string expected)")
        i = _toint(args[1]) if len(args) > 1 else 1
        j = _toint(args[2]) if len(args) > 2 else i
        if i is None:
            i = 1
        if j is None:
            j = i
        if i < 0:
            i = len(s) + 1 + i
        if j < 0:
            j = len(s) + 1 + j
        result = []
        for idx in range(i, j + 1):
            if 1 <= idx <= len(s):
                result.append(ord(s[idx - 1]))
        return result

    def _str_char(args):
        chars = []
        for a in args:
            n = _toint(a)
            if n is None:
                raise LuaRuntimeError("bad argument to 'char' (number expected)")
            chars.append(chr(n))
        return "".join(chars)

    def _str_len(args):
        s = args[0] if args else None
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'len' (string expected)")
        return len(s)

    def _str_sub(args):
        s = args[0] if args else None
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'sub' (string expected)")
        i = _toint(args[1]) if len(args) > 1 else 1
        j = _toint(args[2]) if len(args) > 2 else -1
        if i is None:
            i = 1
        if j is None:
            j = -1
        if i < 0:
            i = max(len(s) + 1 + i, 1)
        if j < 0:
            j = len(s) + 1 + j
        if i < 1:
            i = 1
        return s[i - 1 : j]

    def _str_rep(args):
        s = args[0] if args else ""
        n = _toint(args[1]) if len(args) > 1 else 0
        sep = args[2] if len(args) > 2 else ""
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'rep' (string expected)")
        if n is None or n <= 0:
            return ""
        if not isinstance(sep, str):
            sep = interp.lua_tostring(sep)
        return sep.join([s] * n)

    def _str_reverse(args):
        s = args[0] if args else None
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'reverse' (string expected)")
        return s[::-1]

    def _str_upper(args):
        s = args[0] if args else None
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'upper' (string expected)")
        return s.upper()

    def _str_lower(args):
        s = args[0] if args else None
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'lower' (string expected)")
        return s.lower()

    _CHAR_CLASSES = {
        'a': '[a-zA-Z]', 'A': '[^a-zA-Z]',
        'd': '[0-9]', 'D': '[^0-9]',
        'l': '[a-z]', 'L': '[^a-z]',
        'u': '[A-Z]', 'U': '[^A-Z]',
        'w': '[a-zA-Z0-9_]', 'W': '[^a-zA-Z0-9_]',
        's': '[ \\t\\n\\r\\f\\v]', 'S': '[^ \\t\\n\\r\\f\\v]',
        'p': '[^\\w\\s]', 'P': '[\\w\\s]',
        'c': '[\\x00-\\x1f\\x7f]', 'C': '[^\\x00-\\x1f\\x7f]',
    }

    _CHAR_CLASSES_INNER = {
        'a': 'a-zA-Z', 'd': '0-9', 'l': 'a-z', 'u': 'A-Z',
        'w': 'a-zA-Z0-9_', 's': ' \\t\\n\\r\\f\\v',
        'A': '^a-zA-Z', 'D': '^0-9', 'L': '^a-z', 'U': '^A-Z',
        'W': '^a-zA-Z0-9_', 'S': '^ \\t\\n\\r\\f\\v',
    }

    def _lua_pattern_to_regex(pattern: str) -> str:
        """Convert a Lua pattern to a Python regex.

        Parses pattern as a sequence of pattern items, where each item is a
        character class optionally followed by a quantifier (*, +, -, ?).
        '-' is only a quantifier when it follows a class; otherwise literal.
        """
        result = []
        i = 0
        plen = len(pattern)

        def _maybe_quantifier():
            nonlocal i
            if i < plen and pattern[i] in '*+?':
                result.append(pattern[i])
                i += 1
            elif i < plen and pattern[i] == '-':
                result.append('*?')
                i += 1

        def _parse_class():
            nonlocal i
            if pattern[i] == '%':
                i += 1
                if i >= plen:
                    raise LuaRuntimeError("malformed pattern")
                nc = pattern[i]
                i += 1
                if nc in _CHAR_CLASSES:
                    result.append(_CHAR_CLASSES[nc])
                elif nc in '.+*?()-[]%^${}|\\':
                    result.append('\\' + nc)
                else:
                    result.append(re.escape(nc))
                return True
            if pattern[i] == '[':
                _parse_set()
                return True
            if pattern[i] == '.':
                result.append('(?s:.)')
                i += 1
                return True
            return False

        def _parse_set():
            nonlocal i
            result.append('[')
            i += 1  # skip '['
            if i < plen and pattern[i] == '^':
                result.append('^')
                i += 1
            # First char in set can be ']' literally
            if i < plen and pattern[i] == ']':
                result.append('\\]')
                i += 1
            while i < plen and pattern[i] != ']':
                if pattern[i] == '%':
                    i += 1
                    if i < plen:
                        nc = pattern[i]
                        if nc in _CHAR_CLASSES_INNER:
                            result.append(_CHAR_CLASSES_INNER[nc])
                        else:
                            result.append(re.escape(nc))
                        i += 1
                else:
                    ch = pattern[i]
                    # Handle ranges like a-z
                    if (i + 2 < plen and pattern[i + 1] == '-'
                            and pattern[i + 2] != ']'):
                        result.append(re.escape(ch))
                        result.append('-')
                        result.append(re.escape(pattern[i + 2]))
                        i += 3
                    else:
                        if ch in '\\':
                            result.append('\\' + ch)
                        else:
                            result.append(ch if ch not in '^$.|+*?{}()' or ch == '-' or ch == '^' else '\\' + ch)
                        i += 1
            if i < plen:
                i += 1  # skip ']'
            result.append(']')

        while i < plen:
            c = pattern[i]
            if c == '^' and i == 0:
                result.append('^')
                i += 1
            elif c == '$' and i == plen - 1:
                result.append('$')
                i += 1
            elif c == '(':
                result.append('(')
                i += 1
            elif c == ')':
                result.append(')')
                i += 1
            elif _parse_class():
                _maybe_quantifier()
            else:
                # Literal character — can also have a quantifier
                result.append(re.escape(c))
                i += 1
                _maybe_quantifier()

        return ''.join(result)

    def _str_find(args):
        s = args[0] if args else None
        pattern = args[1] if len(args) > 1 else None
        init = _toint(args[2]) if len(args) > 2 else 1
        plain = args[3] if len(args) > 3 else None
        if not isinstance(s, str) or not isinstance(pattern, str):
            raise LuaRuntimeError("bad argument to 'find' (string expected)")
        if init is None:
            init = 1
        if init < 0:
            init = max(len(s) + 1 + init, 1)
        search_str = s[init - 1:]
        if _is_truthy(plain):
            idx = search_str.find(pattern)
            if idx == -1:
                return [None]
            return [init + idx, init + idx + len(pattern) - 1]
        try:
            regex = _lua_pattern_to_regex(pattern)
            m = re.search(regex, search_str)
        except re.error:
            raise LuaRuntimeError(f"malformed pattern")
        if m is None:
            return [None]
        result = [init + m.start(), init + m.end() - 1]
        for g in m.groups():
            result.append(g)
        return result

    def _str_match(args):
        s = args[0] if args else None
        pattern = args[1] if len(args) > 1 else None
        init = _toint(args[2]) if len(args) > 2 else 1
        if not isinstance(s, str) or not isinstance(pattern, str):
            raise LuaRuntimeError("bad argument to 'match' (string expected)")
        if init is None:
            init = 1
        if init < 0:
            init = max(len(s) + 1 + init, 1)
        try:
            regex = _lua_pattern_to_regex(pattern)
            m = re.search(regex, s[init - 1:])
        except re.error:
            raise LuaRuntimeError("malformed pattern")
        if m is None:
            return [None]
        groups = m.groups()
        if groups:
            return list(groups)
        return [m.group(0)]

    def _str_gmatch(args):
        s = args[0] if args else None
        pattern = args[1] if len(args) > 1 else None
        if not isinstance(s, str) or not isinstance(pattern, str):
            raise LuaRuntimeError("bad argument to 'gmatch' (string expected)")
        try:
            regex = _lua_pattern_to_regex(pattern)
            matches = list(re.finditer(regex, s))
        except re.error:
            raise LuaRuntimeError("malformed pattern")
        idx = [0]

        def _iter(iter_args):
            if idx[0] >= len(matches):
                return [None]
            m = matches[idx[0]]
            idx[0] += 1
            groups = m.groups()
            if groups:
                return list(groups)
            return [m.group(0)]

        return [BuiltinFunction("gmatch_iterator", _iter)]

    def _str_gsub(args):
        s = args[0] if args else None
        pattern = args[1] if len(args) > 1 else None
        repl = args[2] if len(args) > 2 else None
        n = _toint(args[3]) if len(args) > 3 else None
        if not isinstance(s, str) or not isinstance(pattern, str):
            raise LuaRuntimeError("bad argument to 'gsub' (string expected)")
        try:
            regex = _lua_pattern_to_regex(pattern)
        except re.error:
            raise LuaRuntimeError("malformed pattern")

        count = [0]
        max_count = n if n is not None else len(s) + 1

        if isinstance(repl, str):
            def _repl_func(m):
                if count[0] >= max_count:
                    return m.group(0)
                count[0] += 1
                result = []
                i = 0
                while i < len(repl):
                    if repl[i] == '%' and i + 1 < len(repl):
                        i += 1
                        if repl[i].isdigit():
                            gn = int(repl[i])
                            if gn == 0:
                                result.append(m.group(0))
                            else:
                                g = m.group(gn) if gn <= len(m.groups()) else ""
                                result.append(g or "")
                        elif repl[i] == '%':
                            result.append('%')
                        else:
                            result.append(repl[i])
                    else:
                        result.append(repl[i])
                    i += 1
                return ''.join(result)
            result = re.sub(regex, _repl_func, s)
        elif isinstance(repl, LuaTable):
            def _repl_func(m):
                if count[0] >= max_count:
                    return m.group(0)
                count[0] += 1
                key = m.group(1) if m.groups() else m.group(0)
                val = interp._table_get(repl, key)
                if val is None or val is False:
                    return m.group(0)
                return interp.lua_tostring(val)
            result = re.sub(regex, _repl_func, s)
        elif isinstance(repl, (LuaFunction, BuiltinFunction)):
            def _repl_func(m):
                if count[0] >= max_count:
                    return m.group(0)
                count[0] += 1
                groups = m.groups()
                if groups:
                    call_args = list(groups)
                else:
                    call_args = [m.group(0)]
                res = interp._call_function(repl, call_args)
                val = _first(res) if res else None
                if val is None or val is False:
                    return m.group(0)
                return interp.lua_tostring(val)
            result = re.sub(regex, _repl_func, s)
        else:
            raise LuaRuntimeError("bad argument #3 to 'gsub'")
        return [result, count[0]]

    def _str_format(args):
        s = args[0] if args else None
        if not isinstance(s, str):
            raise LuaRuntimeError("bad argument #1 to 'format' (string expected)")
        fmt_args = list(args[1:])
        result = []
        arg_idx = 0
        i = 0
        while i < len(s):
            if s[i] == '%':
                i += 1
                if i >= len(s):
                    raise LuaRuntimeError("invalid format string")
                if s[i] == '%':
                    result.append('%')
                    i += 1
                    continue
                # Parse format specifier
                fmt = '%'
                # flags
                while i < len(s) and s[i] in '-+ #0':
                    fmt += s[i]
                    i += 1
                # width
                while i < len(s) and s[i].isdigit():
                    fmt += s[i]
                    i += 1
                # precision
                if i < len(s) and s[i] == '.':
                    fmt += s[i]
                    i += 1
                    while i < len(s) and s[i].isdigit():
                        fmt += s[i]
                        i += 1
                if i >= len(s):
                    raise LuaRuntimeError("invalid format string")
                spec = s[i]
                i += 1
                if arg_idx >= len(fmt_args):
                    raise LuaRuntimeError("bad argument to 'format' (no value)")
                val = fmt_args[arg_idx]
                arg_idx += 1
                if spec in ('d', 'i', 'u', 'o', 'x', 'X'):
                    n = _toint(val)
                    if n is None:
                        raise LuaRuntimeError(f"bad argument to 'format' (number expected)")
                    if spec == 'u':
                        fmt += 'd'
                        n = n & 0xFFFFFFFFFFFFFFFF
                    else:
                        fmt += spec
                    result.append(fmt % n)
                elif spec in ('f', 'e', 'E', 'g', 'G'):
                    n = _tonum(val)
                    if n is None:
                        raise LuaRuntimeError("bad argument to 'format' (number expected)")
                    fmt += spec
                    result.append(fmt % float(n))
                elif spec == 's':
                    sv = interp.lua_tostring(val)
                    fmt += 's'
                    result.append(fmt % sv)
                elif spec == 'q':
                    sv = interp.lua_tostring(val)
                    result.append(_quote_string(sv))
                elif spec == 'c':
                    n = _toint(val)
                    if n is None:
                        raise LuaRuntimeError("bad argument to 'format' (number expected)")
                    result.append(chr(n))
                else:
                    raise LuaRuntimeError(f"invalid format specifier '{spec}'")
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    def _quote_string(s: str) -> str:
        result = ['"']
        for ch in s:
            if ch == '\\':
                result.append('\\\\')
            elif ch == '"':
                result.append('\\"')
            elif ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                result.append('\\r')
            elif ch == '\0':
                result.append('\\0')
            elif ch == '\x1a':
                result.append('\\26')
            else:
                result.append(ch)
        result.append('"')
        return ''.join(result)

    string_lib.rawset("byte", BuiltinFunction("string.byte", _str_byte))
    string_lib.rawset("char", BuiltinFunction("string.char", _str_char))
    string_lib.rawset("len", BuiltinFunction("string.len", _str_len))
    string_lib.rawset("sub", BuiltinFunction("string.sub", _str_sub))
    string_lib.rawset("rep", BuiltinFunction("string.rep", _str_rep))
    string_lib.rawset("reverse", BuiltinFunction("string.reverse", _str_reverse))
    string_lib.rawset("upper", BuiltinFunction("string.upper", _str_upper))
    string_lib.rawset("lower", BuiltinFunction("string.lower", _str_lower))
    string_lib.rawset("find", BuiltinFunction("string.find", _str_find))
    string_lib.rawset("match", BuiltinFunction("string.match", _str_match))
    string_lib.rawset("gmatch", BuiltinFunction("string.gmatch", _str_gmatch))
    string_lib.rawset("gsub", BuiltinFunction("string.gsub", _str_gsub))
    string_lib.rawset("format", BuiltinFunction("string.format", _str_format))
    g.rawset("string", string_lib)

    # Set up string metatable so "hello":upper() works
    string_mt = LuaTable()
    string_mt.rawset("__index", string_lib)
    g.rawset("__string_mt", string_mt)

    # ---------- math library ----------

    math_lib = LuaTable()

    def _m1(name, fn):
        def wrapper(args):
            n = _tonum(args[0] if args else None)
            if n is None:
                raise LuaRuntimeError(f"bad argument #1 to '{name}' (number expected)")
            return fn(n)
        math_lib.rawset(name, BuiltinFunction(f"math.{name}", wrapper))

    def _m2(name, fn):
        def wrapper(args):
            a = _tonum(args[0] if args else None)
            b = _tonum(args[1] if len(args) > 1 else None)
            if a is None:
                raise LuaRuntimeError(f"bad argument #1 to '{name}' (number expected)")
            if b is None:
                raise LuaRuntimeError(f"bad argument #2 to '{name}' (number expected)")
            return fn(a, b)
        math_lib.rawset(name, BuiltinFunction(f"math.{name}", wrapper))

    _m1("abs", abs)
    _m1("ceil", lambda x: math.ceil(x))
    _m1("floor", lambda x: math.floor(x))
    _m1("sqrt", math.sqrt)
    _m1("sin", math.sin)
    _m1("cos", math.cos)
    _m1("tan", math.tan)
    _m1("asin", math.asin)
    _m1("acos", math.acos)
    _m1("exp", math.exp)
    _m1("log", lambda x: math.log(x))

    def _math_atan(args):
        y = _tonum(args[0] if args else None)
        x = _tonum(args[1] if len(args) > 1 else None)
        if y is None:
            raise LuaRuntimeError("bad argument #1 to 'atan' (number expected)")
        if x is not None:
            return math.atan2(y, x)
        return math.atan(y)
    math_lib.rawset("atan", BuiltinFunction("math.atan", _math_atan))

    _rng = random.Random()

    def _math_random(args):
        if len(args) == 0:
            return _rng.random()
        m = _toint(args[0])
        if m is None:
            raise LuaRuntimeError("bad argument #1 to 'random' (number expected)")
        if len(args) == 1:
            return _rng.randint(1, m)
        n = _toint(args[1])
        if n is None:
            raise LuaRuntimeError("bad argument #2 to 'random' (number expected)")
        return _rng.randint(m, n)

    def _math_randomseed(args):
        seed = _toint(args[0]) if args else None
        if seed is None:
            _rng.seed()
        else:
            _rng.seed(seed)

    math_lib.rawset("random", BuiltinFunction("math.random", _math_random))
    math_lib.rawset("randomseed", BuiltinFunction("math.randomseed", _math_randomseed))

    def _math_max(args):
        if not args:
            raise LuaRuntimeError("bad argument #1 to 'max' (value expected)")
        best = args[0]
        for v in args[1:]:
            if isinstance(v, (int, float)) and isinstance(best, (int, float)):
                if v > best:
                    best = v
            else:
                raise LuaRuntimeError("attempt to compare non-numeric values")
        return best

    def _math_min(args):
        if not args:
            raise LuaRuntimeError("bad argument #1 to 'min' (value expected)")
        best = args[0]
        for v in args[1:]:
            if isinstance(v, (int, float)) and isinstance(best, (int, float)):
                if v < best:
                    best = v
            else:
                raise LuaRuntimeError("attempt to compare non-numeric values")
        return best

    math_lib.rawset("max", BuiltinFunction("math.max", _math_max))
    math_lib.rawset("min", BuiltinFunction("math.min", _math_min))

    def _math_tointeger(args):
        v = args[0] if args else None
        result = _toint(v)
        return result if result is not None else [None]

    def _math_type(args):
        v = args[0] if args else None
        if isinstance(v, int):
            return "integer"
        if isinstance(v, float):
            return "float"
        return False  # Lua returns false for non-number

    math_lib.rawset("tointeger", BuiltinFunction("math.tointeger", _math_tointeger))
    math_lib.rawset("type", BuiltinFunction("math.type", _math_type))

    math_lib.rawset("pi", math.pi)
    math_lib.rawset("huge", math.inf)
    math_lib.rawset("maxinteger", 2**63 - 1)
    math_lib.rawset("mininteger", -(2**63))

    g.rawset("math", math_lib)

    # ---------- os library (sandboxed) ----------

    os_lib = LuaTable()

    def _os_clock(args):
        return time.process_time()

    def _os_time(args):
        return int(time.time())

    def _os_difftime(args):
        t2 = _tonum(args[0] if args else None)
        t1 = _tonum(args[1] if len(args) > 1 else None)
        if t2 is None or t1 is None:
            raise LuaRuntimeError("bad argument to 'difftime'")
        return t2 - t1

    os_lib.rawset("clock", BuiltinFunction("os.clock", _os_clock))
    os_lib.rawset("time", BuiltinFunction("os.time", _os_time))
    os_lib.rawset("difftime", BuiltinFunction("os.difftime", _os_difftime))

    g.rawset("os", os_lib)

    # _VERSION
    g.rawset("_VERSION", "Lua 5.5")


# Import here to avoid circular import issues
from .errors import LuaError
