# abstra-lua

A sandboxed Lua 5.5 interpreter written in pure Python. No dependencies, no C extensions.

## Install

```bash
pip install abstra-lua
```

## Usage

```python
from abstra_lua import LuaSession

session = LuaSession()

# Execute Lua code, get printed output
output = session.execute('print("hello world")')
# output == "hello world"

# Evaluate expressions, get Python values back
session.eval("1 + 2")        # 3
session.eval('"hello"')       # "hello"
session.eval("{1, 2, 3}")     # [1, 2, 3]
session.eval("{x = 1}")       # {"x": 1}

# Pass Python values into Lua
session.set("config", {"host": "localhost", "port": 8080})
session.eval("config.host")   # "localhost"

# Get Lua values back as Python
session.execute("function double(x) return x * 2 end")
fn = session.get("double")
fn(21)  # 42
```

## What's supported

**Types:** nil, boolean, number (integer + float), string, table, function

**Operators:** arithmetic (`+` `-` `*` `/` `//` `%` `^`), comparison (`==` `~=` `<` `>` `<=` `>=`), logical (`and` `or` `not`), bitwise (`&` `|` `~` `<<` `>>`), concat (`..`), length (`#`)

**Control flow:** `if`/`elseif`/`else`, `while`, `repeat`/`until`, numeric `for`, generic `for`, `do`/`end`, `break`, `return`

**Functions:** closures, multiple return values, varargs (`...`), method calls (`:` syntax), string/table call shorthand

**Tables:** constructors, dot/bracket access, metatables (`__index`, `__newindex`, `__call`, `__add`, `__sub`, `__mul`, `__div`, `__mod`, `__pow`, `__unm`, `__idiv`, `__eq`, `__lt`, `__le`, `__len`, `__concat`, `__tostring`, `__band`, `__bor`, `__bxor`, `__bnot`, `__shl`, `__shr`)

**Standard library:**
- **basic:** `print`, `type`, `tostring`, `tonumber`, `assert`, `error`, `pcall`, `xpcall`, `pairs`, `ipairs`, `next`, `select`, `rawget`, `rawset`, `rawlen`, `rawequal`, `setmetatable`, `getmetatable`, `unpack`
- **string:** `byte`, `char`, `find`, `format`, `gmatch`, `gsub`, `len`, `lower`, `match`, `rep`, `reverse`, `sub`, `upper` — plus method syntax (`s:upper()`)
- **table:** `concat`, `insert`, `move`, `pack`, `remove`, `sort`, `unpack`
- **math:** `abs`, `acos`, `asin`, `atan`, `ceil`, `cos`, `exp`, `floor`, `huge`, `log`, `max`, `maxinteger`, `min`, `mininteger`, `pi`, `random`, `randomseed`, `sin`, `sqrt`, `tan`, `tointeger`, `type`
- **os:** `clock`, `difftime`, `time`

## Sandbox

The interpreter is sandboxed by default. There is **no access** to the filesystem, network, OS commands, or the Python runtime. The following are not available: `io`, `os.execute`, `os.remove`, `debug`, `load`, `loadfile`, `dofile`, `require`, `package`.

Resource limits prevent untrusted code from hanging or exhausting memory:

```python
session = LuaSession(
    max_instructions=1_000_000,  # VM ops per execute/eval call
    max_call_depth=200,          # function call nesting
    max_output_bytes=1_000_000,  # total print output
)
```

| Threat | Protection |
|---|---|
| Infinite loops | Instruction counter (resets each call) |
| Infinite recursion | Call depth limit + Python RecursionError catch |
| Memory bomb via strings | 10 MB concat limit |
| Output flood | Output byte limit |
| File/network access | No `io`, `os.execute`, `require` |
| Code injection | No `load`, `loadstring`, `dofile` |
| Introspection | No `debug` library |

## Error handling

```python
from abstra_lua import LuaSession, LuaSyntaxError, LuaRuntimeError

session = LuaSession()

try:
    session.execute("if then end")
except LuaSyntaxError as e:
    print(e)  # syntax error

try:
    session.execute('error("boom")')
except LuaRuntimeError as e:
    print(e)  # boom
```

## Type conversion

| Python | Lua | Python |
|---|---|---|
| `None` | `nil` | `None` |
| `bool` | `boolean` | `bool` |
| `int` | `integer` | `int` |
| `float` | `float` | `float` |
| `str` | `string` | `str` |
| `dict` | `table` | `dict` |
| `list` | `table` (1-indexed) | `list` or `dict` |
| `callable` | `function` | `callable` |
