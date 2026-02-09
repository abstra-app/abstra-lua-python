import pytest
import math
from abstra_lua import LuaSession, LuaRuntimeError, LuaSyntaxError


def lua(code: str) -> str:
    """Helper: execute code, return stdout."""
    s = LuaSession()
    return s.execute(code)


def lua_eval(expr: str):
    """Helper: evaluate expression, return Python value."""
    s = LuaSession()
    return s.eval(expr)


# ===================== LITERALS =====================

class TestLiterals:
    def test_nil(self):
        assert lua_eval("nil") is None

    def test_true(self):
        assert lua_eval("true") is True

    def test_false(self):
        assert lua_eval("false") is False

    def test_integer(self):
        assert lua_eval("42") == 42

    def test_float(self):
        assert lua_eval("3.14") == 3.14

    def test_string(self):
        assert lua_eval('"hello"') == "hello"

    def test_hex_number(self):
        assert lua_eval("0xFF") == 255

    def test_negative_number(self):
        assert lua_eval("-5") == -5


# ===================== ARITHMETIC =====================

class TestArithmetic:
    def test_add_int(self):
        assert lua_eval("2 + 3") == 5

    def test_add_float(self):
        assert lua_eval("2.5 + 3.5") == 6.0

    def test_sub(self):
        assert lua_eval("10 - 3") == 7

    def test_mul(self):
        assert lua_eval("4 * 5") == 20

    def test_div(self):
        # Float division always returns float
        assert lua_eval("10 / 3") == pytest.approx(3.3333333333333335)

    def test_idiv_int(self):
        assert lua_eval("10 // 3") == 3

    def test_idiv_negative(self):
        # Lua floors toward -inf
        assert lua_eval("-10 // 3") == -4

    def test_mod(self):
        assert lua_eval("10 % 3") == 1

    def test_mod_negative(self):
        assert lua_eval("-10 % 3") == 2

    def test_pow(self):
        assert lua_eval("2 ^ 10") == 1024.0

    def test_unary_minus(self):
        assert lua_eval("-(3 + 2)") == -5

    def test_precedence_mul_add(self):
        assert lua_eval("2 + 3 * 4") == 14

    def test_precedence_unary_pow(self):
        # -x^2 = -(x^2)
        assert lua_eval("-2 ^ 2") == -4.0

    def test_string_coercion_add(self):
        assert lua_eval('"10" + 5') == 15

    def test_string_coercion_float(self):
        assert lua_eval('"3.14" + 0') == 3.14

    def test_div_by_zero_float(self):
        result = lua_eval("1.0 / 0.0")
        assert result == float("inf")

    def test_div_zero_by_zero_float(self):
        result = lua_eval("0.0 / 0.0")
        assert math.isnan(result)


# ===================== COMPARISON =====================

class TestComparison:
    def test_eq_int(self):
        assert lua_eval("1 == 1") is True

    def test_eq_float_int(self):
        assert lua_eval("1 == 1.0") is True

    def test_neq(self):
        assert lua_eval("1 ~= 2") is True

    def test_lt(self):
        assert lua_eval("1 < 2") is True

    def test_le(self):
        assert lua_eval("2 <= 2") is True

    def test_gt(self):
        assert lua_eval("3 > 2") is True

    def test_ge(self):
        assert lua_eval("3 >= 3") is True

    def test_string_comparison(self):
        assert lua_eval('"abc" < "abd"') is True

    def test_nil_eq_nil(self):
        assert lua_eval("nil == nil") is True

    def test_nil_neq_false(self):
        assert lua_eval("nil == false") is False

    def test_table_identity_eq(self):
        out = lua("local t = {}; print(t == t)")
        assert out == "true"

    def test_table_different_neq(self):
        out = lua("print({} == {})")
        assert out == "false"


# ===================== LOGICAL =====================

class TestLogical:
    def test_and_true(self):
        assert lua_eval("true and 42") == 42

    def test_and_false(self):
        assert lua_eval("false and 42") is False

    def test_and_nil(self):
        assert lua_eval("nil and 42") is None

    def test_or_true(self):
        assert lua_eval("true or 42") is True

    def test_or_false(self):
        assert lua_eval("false or 42") == 42

    def test_not_true(self):
        assert lua_eval("not true") is False

    def test_not_false(self):
        assert lua_eval("not false") is True

    def test_not_nil(self):
        assert lua_eval("not nil") is True

    def test_not_number(self):
        assert lua_eval("not 0") is False

    def test_short_circuit_and(self):
        # Should not error because second operand is not evaluated
        out = lua("print(false and error('nope'))")
        assert out == "false"

    def test_short_circuit_or(self):
        out = lua("print(true or error('nope'))")
        assert out == "true"


# ===================== STRING OPS =====================

class TestStringOps:
    def test_concat(self):
        assert lua_eval('"hello" .. " " .. "world"') == "hello world"

    def test_concat_number(self):
        assert lua_eval('"value: " .. 42') == "value: 42"

    def test_length_string(self):
        assert lua_eval('#"hello"') == 5

    def test_length_empty_string(self):
        assert lua_eval('#""') == 0


# ===================== BITWISE =====================

class TestBitwise:
    def test_band(self):
        assert lua_eval("0xFF & 0x0F") == 0x0F

    def test_bor(self):
        assert lua_eval("0xF0 | 0x0F") == 0xFF

    def test_bxor(self):
        assert lua_eval("0xFF ~ 0x0F") == 0xF0

    def test_bnot(self):
        assert lua_eval("~0") == -1

    def test_lshift(self):
        assert lua_eval("1 << 4") == 16

    def test_rshift(self):
        assert lua_eval("16 >> 4") == 1


# ===================== VARIABLES =====================

class TestVariables:
    def test_global_assign(self):
        out = lua("x = 42; print(x)")
        assert out == "42"

    def test_local_variable(self):
        out = lua("local x = 10; print(x)")
        assert out == "10"

    def test_local_scoping(self):
        out = lua("""
            local x = 1
            do
                local x = 2
                print(x)
            end
            print(x)
        """)
        assert out == "2\n1"

    def test_multiple_assignment(self):
        out = lua("local a, b, c = 1, 2, 3; print(a, b, c)")
        assert out == "1\t2\t3"

    def test_extra_values_discarded(self):
        out = lua("local a, b = 1, 2, 3; print(a, b)")
        assert out == "1\t2"

    def test_missing_values_nil(self):
        out = lua("local a, b, c = 1, 2; print(a, b, c)")
        assert out == "1\t2\tnil"

    def test_swap(self):
        out = lua("local a, b = 1, 2; a, b = b, a; print(a, b)")
        assert out == "2\t1"


# ===================== IF / ELSEIF / ELSE =====================

class TestIf:
    def test_if_true(self):
        out = lua("if true then print('yes') end")
        assert out == "yes"

    def test_if_false(self):
        out = lua("if false then print('yes') end")
        assert out == ""

    def test_if_else(self):
        out = lua("if false then print('a') else print('b') end")
        assert out == "b"

    def test_if_elseif(self):
        out = lua("""
            local x = 2
            if x == 1 then print('one')
            elseif x == 2 then print('two')
            elseif x == 3 then print('three')
            else print('other')
            end
        """)
        assert out == "two"

    def test_if_elseif_else(self):
        out = lua("""
            local x = 99
            if x == 1 then print('one')
            elseif x == 2 then print('two')
            else print('other')
            end
        """)
        assert out == "other"


# ===================== WHILE =====================

class TestWhile:
    def test_while_basic(self):
        out = lua("""
            local i = 1
            while i <= 3 do
                print(i)
                i = i + 1
            end
        """)
        assert out == "1\n2\n3"

    def test_while_false(self):
        out = lua("while false do print('nope') end")
        assert out == ""

    def test_while_break(self):
        out = lua("""
            local i = 1
            while true do
                if i > 3 then break end
                print(i)
                i = i + 1
            end
        """)
        assert out == "1\n2\n3"


# ===================== REPEAT / UNTIL =====================

class TestRepeat:
    def test_repeat_basic(self):
        out = lua("""
            local i = 1
            repeat
                print(i)
                i = i + 1
            until i > 3
        """)
        assert out == "1\n2\n3"

    def test_repeat_runs_at_least_once(self):
        out = lua("""
            repeat
                print('once')
            until true
        """)
        assert out == "once"

    def test_repeat_condition_sees_locals(self):
        out = lua("""
            local found = false
            repeat
                local x = 42
                if x == 42 then found = true end
            until found
            print(found)
        """)
        assert out == "true"


# ===================== NUMERIC FOR =====================

class TestNumericFor:
    def test_basic(self):
        out = lua("for i = 1, 5 do print(i) end")
        assert out == "1\n2\n3\n4\n5"

    def test_with_step(self):
        out = lua("for i = 0, 10, 2 do print(i) end")
        assert out == "0\n2\n4\n6\n8\n10"

    def test_negative_step(self):
        out = lua("for i = 5, 1, -1 do print(i) end")
        assert out == "5\n4\n3\n2\n1"

    def test_empty_range(self):
        out = lua("for i = 5, 1 do print(i) end")
        assert out == ""

    def test_float_for(self):
        out = lua("for i = 0.0, 1.0, 0.5 do print(i) end")
        assert out == "0.0\n0.5\n1.0"

    def test_break_in_for(self):
        out = lua("""
            for i = 1, 10 do
                if i > 3 then break end
                print(i)
            end
        """)
        assert out == "1\n2\n3"

    def test_loop_var_is_local(self):
        out = lua("""
            local i = 99
            for i = 1, 3 do end
            print(i)
        """)
        assert out == "99"


# ===================== GENERIC FOR =====================

class TestGenericFor:
    def test_ipairs(self):
        out = lua("""
            local t = {10, 20, 30}
            for i, v in ipairs(t) do
                print(i, v)
            end
        """)
        assert out == "1\t10\n2\t20\n3\t30"

    def test_pairs(self):
        out = lua("""
            local t = {a = 1}
            for k, v in pairs(t) do
                print(k, v)
            end
        """)
        assert out == "a\t1"

    def test_custom_iterator(self):
        out = lua("""
            function range(n)
                local i = 0
                return function()
                    i = i + 1
                    if i <= n then return i end
                end
            end
            for v in range(3) do
                print(v)
            end
        """)
        assert out == "1\n2\n3"


# ===================== DO BLOCK =====================

class TestDoBlock:
    def test_do_block_scoping(self):
        out = lua("""
            local x = 1
            do
                local x = 2
            end
            print(x)
        """)
        assert out == "1"


# ===================== FUNCTIONS =====================

class TestFunctions:
    def test_basic_function(self):
        out = lua("""
            function greet(name)
                print("hello " .. name)
            end
            greet("world")
        """)
        assert out == "hello world"

    def test_local_function(self):
        out = lua("""
            local function add(a, b)
                return a + b
            end
            print(add(3, 4))
        """)
        assert out == "7"

    def test_anonymous_function(self):
        out = lua("""
            local add = function(a, b)
                return a + b
            end
            print(add(3, 4))
        """)
        assert out == "7"

    def test_multiple_returns(self):
        out = lua("""
            function multi()
                return 1, 2, 3
            end
            local a, b, c = multi()
            print(a, b, c)
        """)
        assert out == "1\t2\t3"

    def test_return_adjustment(self):
        out = lua("""
            function two() return 1, 2 end
            local a, b, c = two()
            print(a, b, c)
        """)
        assert out == "1\t2\tnil"

    def test_multi_return_in_middle_adjusted(self):
        out = lua("""
            function two() return 1, 2 end
            local a, b = two(), 99
            print(a, b)
        """)
        assert out == "1\t99"

    def test_closure(self):
        out = lua("""
            function counter()
                local n = 0
                return function()
                    n = n + 1
                    return n
                end
            end
            local c = counter()
            print(c())
            print(c())
            print(c())
        """)
        assert out == "1\n2\n3"

    def test_recursive_function(self):
        out = lua("""
            function fact(n)
                if n <= 1 then return 1 end
                return n * fact(n - 1)
            end
            print(fact(10))
        """)
        assert out == "3628800"

    def test_varargs(self):
        out = lua("""
            function sum(...)
                local total = 0
                local args = {...}
                for i = 1, #args do
                    total = total + args[i]
                end
                return total
            end
            print(sum(1, 2, 3, 4, 5))
        """)
        assert out == "15"

    def test_varargs_with_named_params(self):
        out = lua("""
            function f(a, b, ...)
                print(a, b, ...)
            end
            f(1, 2, 3, 4)
        """)
        assert out == "1\t2\t3\t4"

    def test_method_call_syntax(self):
        out = lua("""
            local t = {}
            function t:greet(name)
                print("hello " .. name .. " from " .. tostring(self))
            end
            t:greet("world")
        """)
        assert "hello world from" in out

    def test_string_arg_shorthand(self):
        out = lua('print "hello"')
        assert out == "hello"

    def test_table_arg_shorthand(self):
        out = lua("""
            function f(t) print(t.x) end
            f{x = 42}
        """)
        assert out == "42"

    def test_stack_overflow(self):
        with pytest.raises(LuaRuntimeError, match="stack overflow"):
            lua("""
                function f() return f() end
                f()
            """)

    def test_nested_returns(self):
        out = lua("""
            function outer()
                function inner()
                    return 42
                end
                return inner()
            end
            print(outer())
        """)
        assert out == "42"


# ===================== TABLES =====================

class TestTables:
    def test_empty_table(self):
        out = lua("local t = {}; print(type(t))")
        assert out == "table"

    def test_array_constructor(self):
        out = lua("""
            local t = {10, 20, 30}
            print(t[1], t[2], t[3])
        """)
        assert out == "10\t20\t30"

    def test_record_constructor(self):
        out = lua("""
            local t = {x = 1, y = 2}
            print(t.x, t.y)
        """)
        assert out == "1\t2"

    def test_mixed_constructor(self):
        out = lua("""
            local t = {10, x = 1, 20, y = 2, 30}
            print(t[1], t[2], t[3], t.x, t.y)
        """)
        assert out == "10\t20\t30\t1\t2"

    def test_bracket_key_constructor(self):
        out = lua("""
            local t = {[1+1] = "two", ["hello world"] = true}
            print(t[2], t["hello world"])
        """)
        assert out == "two\ttrue"

    def test_table_length(self):
        out = lua("""
            local t = {10, 20, 30, 40}
            print(#t)
        """)
        assert out == "4"

    def test_table_nested(self):
        out = lua("""
            local t = {inner = {value = 42}}
            print(t.inner.value)
        """)
        assert out == "42"

    def test_table_dot_assign(self):
        out = lua("""
            local t = {}
            t.x = 42
            print(t.x)
        """)
        assert out == "42"

    def test_table_bracket_assign(self):
        out = lua("""
            local t = {}
            t["key"] = "value"
            print(t["key"])
        """)
        assert out == "value"

    def test_table_nil_delete(self):
        out = lua("""
            local t = {1, 2, 3}
            t[2] = nil
            print(t[2])
        """)
        assert out == "nil"

    def test_table_constructor_trailing_comma(self):
        out = lua("""
            local t = {1, 2, 3,}
            print(#t)
        """)
        assert out == "3"

    def test_table_constructor_semicolons(self):
        out = lua("""
            local t = {1; 2; 3}
            print(#t)
        """)
        assert out == "3"

    def test_multireturn_in_table_constructor(self):
        out = lua("""
            function multi() return 10, 20, 30 end
            local t = {multi()}
            print(#t, t[1], t[2], t[3])
        """)
        assert out == "3\t10\t20\t30"

    def test_multireturn_in_middle_of_constructor(self):
        out = lua("""
            function multi() return 10, 20, 30 end
            local t = {multi(), 99}
            print(#t, t[1], t[2])
        """)
        assert out == "2\t10\t99"


# ===================== METATABLES =====================

class TestMetatables:
    def test_add_metamethod(self):
        out = lua("""
            local mt = {__add = function(a, b) return a.val + b.val end}
            local a = setmetatable({val = 10}, mt)
            local b = setmetatable({val = 20}, mt)
            print(a + b)
        """)
        assert out == "30"

    def test_index_metamethod_table(self):
        out = lua("""
            local defaults = {color = "red", size = 10}
            local mt = {__index = defaults}
            local t = setmetatable({}, mt)
            print(t.color, t.size)
        """)
        assert out == "red\t10"

    def test_index_metamethod_function(self):
        out = lua("""
            local mt = {__index = function(t, k)
                return k .. "!"
            end}
            local t = setmetatable({}, mt)
            print(t.hello)
        """)
        assert out == "hello!"

    def test_newindex_metamethod(self):
        out = lua("""
            local log = {}
            local mt = {__newindex = function(t, k, v)
                table.insert(log, k .. "=" .. tostring(v))
                rawset(t, k, v)
            end}
            local t = setmetatable({}, mt)
            t.x = 42
            print(log[1], t.x)
        """)
        assert out == "x=42\t42"

    def test_call_metamethod(self):
        out = lua("""
            local mt = {__call = function(t, x) return x * 2 end}
            local t = setmetatable({}, mt)
            print(t(21))
        """)
        assert out == "42"

    def test_tostring_metamethod(self):
        out = lua("""
            local mt = {__tostring = function(t) return "MyObj(" .. t.val .. ")" end}
            local t = setmetatable({val = 42}, mt)
            print(tostring(t))
        """)
        assert out == "MyObj(42)"

    def test_len_metamethod(self):
        out = lua("""
            local mt = {__len = function(t) return 99 end}
            local t = setmetatable({}, mt)
            print(#t)
        """)
        assert out == "99"

    def test_eq_metamethod(self):
        out = lua("""
            local mt = {__eq = function(a, b) return a.id == b.id end}
            local a = setmetatable({id = 1}, mt)
            local b = setmetatable({id = 1}, mt)
            print(a == b)
        """)
        assert out == "true"

    def test_lt_metamethod(self):
        out = lua("""
            local mt = {__lt = function(a, b) return a.val < b.val end}
            local a = setmetatable({val = 1}, mt)
            local b = setmetatable({val = 2}, mt)
            print(a < b, b < a)
        """)
        assert out == "true\tfalse"

    def test_concat_metamethod(self):
        out = lua("""
            local mt = {__concat = function(a, b) return tostring(a) .. tostring(b) end}
            local t = setmetatable({}, mt)
            print(t .. "hello")
        """)
        assert "hello" in out

    def test_getmetatable_setmetatable(self):
        out = lua("""
            local mt = {}
            local t = setmetatable({}, mt)
            print(getmetatable(t) == mt)
        """)
        assert out == "true"

    def test_protected_metatable(self):
        with pytest.raises(LuaRuntimeError, match="protected"):
            lua("""
                local mt = {__metatable = "no touchy"}
                local t = setmetatable({}, mt)
                setmetatable(t, {})
            """)

    def test_chained_index(self):
        out = lua("""
            local base = {method = function() return "base" end}
            local derived_mt = {__index = base}
            local derived = setmetatable({}, derived_mt)
            print(derived.method())
        """)
        assert out == "base"

    def test_arithmetic_metamethods(self):
        code_template = """
            local mt = {{__{mm} = function(a, b) return a.v {op} b.v end}}
            local a = setmetatable({{v = 10}}, mt)
            local b = setmetatable({{v = 3}}, mt)
            print(a {op} b)
        """
        cases = [
            ("add", "+", "13"),
            ("sub", "-", "7"),
            ("mul", "*", "30"),
        ]
        for mm, op, expected in cases:
            out = lua(code_template.format(mm=mm, op=op))
            assert out == expected, f"Failed for __{mm}"


# ===================== STRING METHODS =====================

class TestStringMethods:
    def test_string_upper(self):
        assert lua_eval('string.upper("hello")') == "HELLO"

    def test_string_lower(self):
        assert lua_eval('string.lower("HELLO")') == "hello"

    def test_string_len(self):
        assert lua_eval('string.len("hello")') == 5

    def test_string_rep(self):
        assert lua_eval('string.rep("ab", 3)') == "ababab"

    def test_string_rep_with_sep(self):
        assert lua_eval('string.rep("ab", 3, ",")') == "ab,ab,ab"

    def test_string_reverse(self):
        assert lua_eval('string.reverse("hello")') == "olleh"

    def test_string_sub(self):
        assert lua_eval('string.sub("hello", 2, 4)') == "ell"

    def test_string_sub_negative(self):
        assert lua_eval('string.sub("hello", -3)') == "llo"

    def test_string_byte(self):
        assert lua_eval('string.byte("A")') == 65

    def test_string_char(self):
        assert lua_eval('string.char(65, 66, 67)') == "ABC"

    def test_string_find_plain(self):
        out = lua('local a, b = string.find("hello world", "world", 1, true); print(a, b)')
        assert out == "7\t11"

    def test_string_find_pattern(self):
        out = lua('local a, b = string.find("hello123", "%d+"); print(a, b)')
        assert out == "6\t8"

    def test_string_find_not_found(self):
        out = lua('print(string.find("hello", "xyz"))')
        assert out == "nil"

    def test_string_match(self):
        out = lua('print(string.match("hello123", "%d+"))')
        assert out == "123"

    def test_string_match_captures(self):
        out = lua('local a, b = string.match("2024-01-15", "(%d+)-(%d+)"); print(a, b)')
        assert out == "2024\t01"

    def test_string_gmatch(self):
        out = lua("""
            local result = {}
            for w in string.gmatch("hello world foo", "%a+") do
                table.insert(result, w)
            end
            print(table.concat(result, ","))
        """)
        assert out == "hello,world,foo"

    def test_string_gsub(self):
        out = lua('print(string.gsub("hello world", "(%w+)", "%1-%1"))')
        assert out == "hello-hello world-world\t2"

    def test_string_gsub_function(self):
        out = lua("""
            local result = string.gsub("hello", "(%w+)", function(w) return w:upper() end)
            print(result)
        """)
        assert out == "HELLO"

    def test_string_gsub_table(self):
        out = lua("""
            local t = {hello = "HI", world = "EARTH"}
            local result = string.gsub("hello world", "(%w+)", t)
            print(result)
        """)
        assert out == "HI EARTH"

    def test_string_gsub_limit(self):
        out = lua('print(string.gsub("aaa", "a", "b", 2))')
        assert out == "bba\t2"

    def test_string_format_d(self):
        assert lua_eval('string.format("%d", 42)') == "42"

    def test_string_format_f(self):
        out = lua_eval('string.format("%.2f", 3.14159)')
        assert out == "3.14"

    def test_string_format_s(self):
        assert lua_eval('string.format("%s=%s", "x", 42)') == "x=42"

    def test_string_format_x(self):
        assert lua_eval('string.format("%x", 255)') == "ff"

    def test_string_format_q(self):
        out = lua_eval('string.format("%q", "hello\\nworld")')
        assert out == '"hello\\nworld"'

    def test_string_format_percent(self):
        assert lua_eval('string.format("100%%")') == "100%"

    def test_string_method_syntax(self):
        out = lua('print(("hello"):upper())')
        assert out == "HELLO"


# ===================== TABLE LIBRARY =====================

class TestTableLib:
    def test_table_insert_append(self):
        out = lua("""
            local t = {1, 2, 3}
            table.insert(t, 4)
            print(#t, t[4])
        """)
        assert out == "4\t4"

    def test_table_insert_at_pos(self):
        out = lua("""
            local t = {1, 2, 3}
            table.insert(t, 2, 99)
            print(t[1], t[2], t[3], t[4])
        """)
        assert out == "1\t99\t2\t3"

    def test_table_remove(self):
        out = lua("""
            local t = {1, 2, 3, 4}
            local v = table.remove(t, 2)
            print(v, #t, t[1], t[2], t[3])
        """)
        assert out == "2\t3\t1\t3\t4"

    def test_table_remove_last(self):
        out = lua("""
            local t = {1, 2, 3}
            local v = table.remove(t)
            print(v, #t)
        """)
        assert out == "3\t2"

    def test_table_sort(self):
        out = lua("""
            local t = {3, 1, 4, 1, 5}
            table.sort(t)
            print(table.concat(t, ","))
        """)
        assert out == "1,1,3,4,5"

    def test_table_sort_custom(self):
        out = lua("""
            local t = {3, 1, 4, 1, 5}
            table.sort(t, function(a, b) return a > b end)
            print(table.concat(t, ","))
        """)
        assert out == "5,4,3,1,1"

    def test_table_concat(self):
        out = lua("""
            local t = {"a", "b", "c"}
            print(table.concat(t, ", "))
        """)
        assert out == "a, b, c"

    def test_table_concat_range(self):
        out = lua("""
            local t = {"a", "b", "c", "d"}
            print(table.concat(t, "-", 2, 3))
        """)
        assert out == "b-c"

    def test_table_pack(self):
        out = lua("""
            local t = table.pack(10, 20, 30)
            print(t.n, t[1], t[2], t[3])
        """)
        assert out == "3\t10\t20\t30"

    def test_table_unpack(self):
        out = lua("""
            local a, b, c = table.unpack({10, 20, 30})
            print(a, b, c)
        """)
        assert out == "10\t20\t30"

    def test_table_move(self):
        out = lua("""
            local t = {1, 2, 3, 4, 5}
            table.move(t, 3, 5, 1)
            print(t[1], t[2], t[3])
        """)
        assert out == "3\t4\t5"

    def test_unpack_global(self):
        out = lua("""
            local a, b, c = unpack({10, 20, 30})
            print(a, b, c)
        """)
        assert out == "10\t20\t30"


# ===================== MATH LIBRARY =====================

class TestMathLib:
    def test_math_abs(self):
        assert lua_eval("math.abs(-5)") == 5

    def test_math_floor(self):
        assert lua_eval("math.floor(3.7)") == 3

    def test_math_ceil(self):
        assert lua_eval("math.ceil(3.2)") == 4

    def test_math_sqrt(self):
        assert lua_eval("math.sqrt(16)") == 4.0

    def test_math_sin(self):
        assert lua_eval("math.sin(0)") == pytest.approx(0.0)

    def test_math_cos(self):
        assert lua_eval("math.cos(0)") == pytest.approx(1.0)

    def test_math_pi(self):
        assert lua_eval("math.pi") == pytest.approx(math.pi)

    def test_math_huge(self):
        assert lua_eval("math.huge") == float("inf")

    def test_math_max(self):
        assert lua_eval("math.max(1, 5, 3)") == 5

    def test_math_min(self):
        assert lua_eval("math.min(1, 5, 3)") == 1

    def test_math_maxinteger(self):
        assert lua_eval("math.maxinteger") == 2**63 - 1

    def test_math_type_integer(self):
        assert lua_eval("math.type(42)") == "integer"

    def test_math_type_float(self):
        assert lua_eval("math.type(3.14)") == "float"

    def test_math_type_string(self):
        assert lua_eval("math.type('hello')") is False

    def test_math_tointeger(self):
        assert lua_eval("math.tointeger(5.0)") == 5

    def test_math_tointeger_fails(self):
        assert lua_eval("math.tointeger(5.5)") is None

    def test_math_random_range(self):
        s = LuaSession()
        s.execute("math.randomseed(42)")
        val = s.eval("math.random(1, 10)")
        assert 1 <= val <= 10

    def test_math_atan(self):
        assert lua_eval("math.atan(1)") == pytest.approx(math.atan(1))

    def test_math_atan2(self):
        assert lua_eval("math.atan(1, 1)") == pytest.approx(math.atan2(1, 1))


# ===================== BASIC FUNCTIONS =====================

class TestBasicFunctions:
    def test_type(self):
        cases = [
            ("nil", "nil"), ("true", "boolean"), ("42", "number"),
            ("3.14", "number"), ('"hi"', "string"), ("{}", "table"),
            ("print", "function"),
        ]
        for expr, expected in cases:
            assert lua_eval(f'type({expr})') == expected

    def test_tostring(self):
        assert lua_eval('tostring(42)') == "42"
        assert lua_eval('tostring(nil)') == "nil"
        assert lua_eval('tostring(true)') == "true"

    def test_tonumber(self):
        assert lua_eval('tonumber("42")') == 42
        assert lua_eval('tonumber("3.14")') == 3.14
        assert lua_eval('tonumber("0xFF")') == 255
        assert lua_eval('tonumber("hello")') is None

    def test_tonumber_base(self):
        assert lua_eval('tonumber("ff", 16)') == 255
        assert lua_eval('tonumber("77", 8)') == 63
        assert lua_eval('tonumber("11", 2)') == 3

    def test_assert_pass(self):
        out = lua("assert(true, 'ok')")
        assert out == ""

    def test_assert_fail(self):
        with pytest.raises(LuaRuntimeError, match="oh no"):
            lua("assert(false, 'oh no')")

    def test_assert_default_message(self):
        with pytest.raises(LuaRuntimeError, match="assertion failed"):
            lua("assert(false)")

    def test_error(self):
        with pytest.raises(LuaRuntimeError, match="boom"):
            lua('error("boom")')

    def test_pcall_success(self):
        out = lua("""
            local ok, val = pcall(function() return 42 end)
            print(ok, val)
        """)
        assert out == "true\t42"

    def test_pcall_error(self):
        out = lua("""
            local ok, err = pcall(function() error("fail") end)
            print(ok, err)
        """)
        assert out.startswith("false")
        assert "fail" in out

    def test_xpcall(self):
        out = lua("""
            local ok, val = xpcall(
                function() error("fail") end,
                function(err) return "handled: " .. err end
            )
            print(ok, val)
        """)
        assert "handled:" in out

    def test_select_index(self):
        out = lua('print(select(2, "a", "b", "c"))')
        assert out == "b\tc"

    def test_select_count(self):
        out = lua('print(select("#", "a", "b", "c"))')
        assert out == "3"

    def test_rawget_rawset(self):
        out = lua("""
            local mt = {__index = function() return "meta" end}
            local t = setmetatable({}, mt)
            rawset(t, "x", 42)
            print(rawget(t, "x"), rawget(t, "y"))
        """)
        assert out == "42\tnil"

    def test_rawlen(self):
        out = lua("""
            local mt = {__len = function() return 99 end}
            local t = setmetatable({1, 2, 3}, mt)
            print(#t, rawlen(t))
        """)
        assert out == "99\t3"

    def test_rawequal(self):
        out = lua("""
            local mt = {__eq = function() return true end}
            local a = setmetatable({}, mt)
            local b = setmetatable({}, mt)
            print(a == b, rawequal(a, b))
        """)
        assert out == "true\tfalse"

    def test_next(self):
        out = lua("""
            local t = {a = 1}
            local k, v = next(t)
            print(k, v)
            print(next(t, k))
        """)
        lines = out.split("\n")
        assert lines[0] == "a\t1"
        assert lines[1] == "nil"

    def test_version(self):
        assert lua_eval("_VERSION") == "Lua 5.5"


# ===================== PRINT =====================

class TestPrint:
    def test_print_multiple_values(self):
        out = lua("print(1, 2, 3)")
        assert out == "1\t2\t3"

    def test_print_no_args(self):
        out = lua("print()")
        assert out == ""

    def test_print_nil(self):
        out = lua("print(nil)")
        assert out == "nil"

    def test_print_boolean(self):
        out = lua("print(true, false)")
        assert out == "true\tfalse"

    def test_print_float(self):
        out = lua("print(3.14)")
        assert out == "3.14"

    def test_multiple_print_calls(self):
        out = lua("print('a'); print('b'); print('c')")
        assert out == "a\nb\nc"


# ===================== SESSION API =====================

class TestSession:
    def test_execute_returns_stdout(self):
        s = LuaSession()
        out = s.execute("print('hello')")
        assert out == "hello"

    def test_eval_number(self):
        s = LuaSession()
        assert s.eval("1 + 2") == 3

    def test_eval_string(self):
        s = LuaSession()
        assert s.eval('"hello"') == "hello"

    def test_eval_boolean(self):
        s = LuaSession()
        assert s.eval("true") is True

    def test_eval_nil(self):
        s = LuaSession()
        assert s.eval("nil") is None

    def test_eval_table_as_list(self):
        s = LuaSession()
        result = s.eval("{10, 20, 30}")
        assert result == [10, 20, 30]

    def test_eval_table_as_dict(self):
        s = LuaSession()
        result = s.eval('{x = 1, y = 2}')
        assert result == {"x": 1, "y": 2}

    def test_set_and_get(self):
        s = LuaSession()
        s.set("x", 42)
        assert s.get("x") == 42

    def test_set_string(self):
        s = LuaSession()
        s.set("name", "world")
        out = s.execute('print("hello " .. name)')
        assert out == "hello world"

    def test_set_dict(self):
        s = LuaSession()
        s.set("config", {"host": "localhost", "port": 8080})
        assert s.eval("config.host") == "localhost"
        assert s.eval("config.port") == 8080

    def test_set_list(self):
        s = LuaSession()
        s.set("items", [10, 20, 30])
        assert s.eval("items[2]") == 20

    def test_set_none(self):
        s = LuaSession()
        s.set("x", None)
        assert s.get("x") is None

    def test_set_bool(self):
        s = LuaSession()
        s.set("flag", True)
        assert s.get("flag") is True

    def test_set_callable(self):
        s = LuaSession()
        s.set("add", lambda a, b: a + b)
        assert s.eval("add(3, 4)") == 7

    def test_get_function(self):
        s = LuaSession()
        s.execute("function double(x) return x * 2 end")
        fn = s.get("double")
        assert callable(fn)
        assert fn(21) == 42

    def test_persistent_state(self):
        s = LuaSession()
        s.execute("x = 10")
        s.execute("x = x + 5")
        assert s.eval("x") == 15

    def test_separate_sessions(self):
        s1 = LuaSession()
        s2 = LuaSession()
        s1.execute("x = 1")
        s2.execute("x = 2")
        assert s1.eval("x") == 1
        assert s2.eval("x") == 2

    def test_set_nested_dict(self):
        s = LuaSession()
        s.set("data", {"user": {"name": "Alice", "age": 30}})
        assert s.eval("data.user.name") == "Alice"
        assert s.eval("data.user.age") == 30


# ===================== ERROR HANDLING =====================

class TestErrorHandling:
    def test_syntax_error(self):
        with pytest.raises(LuaSyntaxError):
            lua("if then end")

    def test_runtime_error_nil_call(self):
        with pytest.raises(LuaRuntimeError, match="attempt to call"):
            lua("local x = nil; x()")

    def test_runtime_error_nil_index(self):
        with pytest.raises(LuaRuntimeError, match="attempt to index"):
            lua("local x = nil; return x.foo")

    def test_runtime_error_arithmetic_on_string(self):
        with pytest.raises(LuaRuntimeError, match="attempt to perform arithmetic"):
            lua('local x = "hello" + 1')

    def test_runtime_error_compare_mixed(self):
        with pytest.raises(LuaRuntimeError, match="attempt to compare"):
            lua('local x = 1 < "hello"')

    def test_runtime_error_concat_table(self):
        with pytest.raises(LuaRuntimeError, match="attempt to concatenate"):
            lua('local x = {} .. "hello"')


# ===================== COMPLEX PROGRAMS =====================

class TestComplexPrograms:
    def test_fibonacci(self):
        out = lua("""
            function fib(n)
                if n <= 1 then return n end
                return fib(n - 1) + fib(n - 2)
            end
            for i = 0, 10 do
                print(fib(i))
            end
        """)
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
        lines = out.strip().split("\n")
        assert [int(x) for x in lines] == expected

    def test_bubble_sort(self):
        out = lua("""
            local arr = {5, 3, 8, 1, 9, 2, 7, 4, 6}
            for i = 1, #arr do
                for j = 1, #arr - i do
                    if arr[j] > arr[j + 1] then
                        arr[j], arr[j + 1] = arr[j + 1], arr[j]
                    end
                end
            end
            print(table.concat(arr, ","))
        """)
        assert out == "1,2,3,4,5,6,7,8,9"

    def test_class_like_pattern(self):
        out = lua("""
            local Animal = {}
            Animal.__index = Animal

            function Animal.new(name, sound)
                local self = setmetatable({}, Animal)
                self.name = name
                self.sound = sound
                return self
            end

            function Animal:speak()
                return self.name .. " says " .. self.sound
            end

            local dog = Animal.new("Dog", "Woof")
            local cat = Animal.new("Cat", "Meow")
            print(dog:speak())
            print(cat:speak())
        """)
        assert out == "Dog says Woof\nCat says Meow"

    def test_higher_order_functions(self):
        out = lua("""
            function map(t, f)
                local result = {}
                for i, v in ipairs(t) do
                    result[i] = f(v)
                end
                return result
            end

            function filter(t, f)
                local result = {}
                for i, v in ipairs(t) do
                    if f(v) then
                        table.insert(result, v)
                    end
                end
                return result
            end

            local nums = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
            local evens = filter(nums, function(x) return x % 2 == 0 end)
            local doubled = map(evens, function(x) return x * 2 end)
            print(table.concat(doubled, ","))
        """)
        assert out == "4,8,12,16,20"

    def test_string_processing(self):
        out = lua("""
            local text = "the quick brown fox jumps over the lazy dog"
            local words = {}
            for w in string.gmatch(text, "%a+") do
                table.insert(words, w)
            end
            table.sort(words)
            print(table.concat(words, " "))
        """)
        assert out == "brown dog fox jumps lazy over quick the the"

    def test_accumulator_closure(self):
        out = lua("""
            function accumulator(init)
                local sum = init or 0
                return {
                    add = function(n) sum = sum + n end,
                    get = function() return sum end,
                }
            end
            local acc = accumulator(10)
            acc.add(5)
            acc.add(3)
            print(acc.get())
        """)
        assert out == "18"

    def test_linked_list(self):
        out = lua("""
            function cons(head, tail) return {head = head, tail = tail} end
            function list_tostring(node)
                if node == nil then return "" end
                if node.tail == nil then return tostring(node.head) end
                return tostring(node.head) .. ", " .. list_tostring(node.tail)
            end

            local lst = cons(1, cons(2, cons(3, nil)))
            print(list_tostring(lst))
        """)
        assert out == "1, 2, 3"

    def test_memoization(self):
        out = lua("""
            function memoize(f)
                local cache = {}
                return function(n)
                    if cache[n] == nil then
                        cache[n] = f(n)
                    end
                    return cache[n]
                end
            end

            local fib
            fib = memoize(function(n)
                if n <= 1 then return n end
                return fib(n - 1) + fib(n - 2)
            end)

            print(fib(30))
        """)
        assert out == "832040"


# ===================== SANDBOX / SECURITY =====================

class TestSandbox:
    def test_infinite_while_loop(self):
        s = LuaSession(max_instructions=1000)
        with pytest.raises(LuaRuntimeError, match="execution quota exceeded"):
            s.execute("while true do end")

    def test_infinite_repeat_loop(self):
        s = LuaSession(max_instructions=1000)
        with pytest.raises(LuaRuntimeError, match="execution quota exceeded"):
            s.execute("repeat until false")

    def test_infinite_for_loop(self):
        s = LuaSession(max_instructions=1000)
        with pytest.raises(LuaRuntimeError, match="execution quota exceeded"):
            s.execute("for i = 1, math.huge do end")

    def test_infinite_recursion(self):
        s = LuaSession(max_call_depth=50)
        with pytest.raises(LuaRuntimeError, match="stack overflow"):
            s.execute("function f() return f() end; f()")

    def test_output_limit(self):
        s = LuaSession(max_output_bytes=100)
        with pytest.raises(LuaRuntimeError, match="output limit exceeded"):
            s.execute("""
                for i = 1, 10000 do
                    print(string.rep("x", 100))
                end
            """)

    def test_string_bomb(self):
        s = LuaSession(max_instructions=100_000)
        with pytest.raises(LuaRuntimeError, match="(string length overflow|execution quota exceeded)"):
            s.execute("""
                local s = "a"
                for i = 1, 100 do
                    s = s .. s
                end
            """)

    def test_no_os_execute(self):
        s = LuaSession()
        out = s.execute("print(type(os.execute))")
        assert out == "nil"

    def test_no_io_library(self):
        s = LuaSession()
        out = s.execute("print(type(io))")
        assert out == "nil"

    def test_no_load(self):
        s = LuaSession()
        out = s.execute("print(type(load))")
        assert out == "nil"

    def test_no_dofile(self):
        s = LuaSession()
        out = s.execute("print(type(dofile))")
        assert out == "nil"

    def test_no_require(self):
        s = LuaSession()
        out = s.execute("print(type(require))")
        assert out == "nil"

    def test_quota_resets_between_calls(self):
        s = LuaSession(max_instructions=10000)
        s.execute("for i = 1, 100 do end")
        # Should work again - quota resets
        s.execute("for i = 1, 100 do end")

    def test_custom_limits(self):
        s = LuaSession(max_instructions=500, max_call_depth=10)
        with pytest.raises(LuaRuntimeError):
            s.execute("""
                function f(n)
                    if n > 0 then return f(n-1) end
                end
                f(100)
            """)
