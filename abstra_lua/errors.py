class LuaError(Exception):
    pass


class LuaSyntaxError(LuaError):
    def __init__(self, message, line=None):
        self.line = line
        prefix = f":{line}" if line else ""
        super().__init__(f"[string]{prefix}: {message}")


class LuaRuntimeError(LuaError):
    def __init__(self, message, level=0):
        self.level = level
        super().__init__(message)


class LuaInternalError(LuaError):
    pass


class BreakSignal(BaseException):
    pass


class ReturnSignal(BaseException):
    __slots__ = ("values",)

    def __init__(self, values):
        self.values = values


class ContinueSignal(BaseException):
    pass
