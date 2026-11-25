"""Разбор и вычисление $filter OData v3 в объёме, который поддерживает стандартный интерфейс 1С.

Намеренно повторяет строгость 1С: ссылки сравниваются только с guid'…', даты только с datetime'…',
строки в одинарных кавычках. Ошибка типов даёт HTTP 400, как у настоящей платформы."""
import re
from datetime import datetime

TOKEN = re.compile(
    r"""\s*(?:
    (?P<dt>datetime'(?P<dtv>[^']*)')|
    (?P<guid>guid'(?P<guidv>[^']*)')|
    (?P<str>'(?P<strv>(?:[^']|'')*)')|
    (?P<num>-?\d+(?:\.\d+)?)|
    (?P<id>[^\W\d][\w]*)|
    (?P<sym>[(),])
    )""",
    re.X | re.U,
)


class FilterError(Exception):
    pass


def _tokenize(text: str) -> list[tuple[str, object]]:
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise FilterError(f"Синтаксическая ошибка в $filter около «{text[pos:pos + 20]}»")
        pos = m.end()
        if m.group("dt"):
            out.append(("dt", _norm_dt(m.group("dtv"))))
        elif m.group("guid"):
            out.append(("guid", m.group("guidv").lower()))
        elif m.group("str") is not None:
            out.append(("str", m.group("strv").replace("''", "'")))
        elif m.group("num"):
            s = m.group("num")
            out.append(("num", float(s) if "." in s else int(s)))
        elif m.group("id"):
            out.append(("id", m.group("id")))
        else:
            out.append(("sym", m.group("sym")))
    return out


def _norm_dt(s: str) -> str:
    try:
        d = datetime.fromisoformat(s.replace("Z", ""))
    except ValueError:
        raise FilterError(f"Неверный формат даты datetime'{s}'")
    return d.strftime("%Y-%m-%dT%H:%M:%S")


CMP = {"eq", "ne", "gt", "ge", "lt", "le"}
COMPAT = {
    "Edm.Guid": "guid", "Edm.DateTime": "dt", "Edm.String": "str", "Edm.Boolean": "bool",
    "Edm.Decimal": "num", "Edm.Int32": "num", "Edm.Int64": "num", "Edm.Double": "num",
}


class Parser:
    def __init__(self, text: str, schema: dict[str, str]):
        self.t = _tokenize(text)
        self.i = 0
        self.schema = schema  # имя поля -> Edm-тип

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        node = self.or_()
        if self.i != len(self.t):
            raise FilterError("Лишние символы в конце $filter")
        return node

    def _is(self, word):
        k, v = self.peek()
        return k == "id" and str(v).lower() == word

    def or_(self):
        left = self.and_()
        while self._is("or"):
            self.take()
            right = self.and_()
            left = (lambda a, b: lambda r: bool(a(r)) or bool(b(r)))(left, right)
        return left

    def and_(self):
        left = self.not_()
        while self._is("and"):
            self.take()
            right = self.not_()
            left = (lambda a, b: lambda r: bool(a(r)) and bool(b(r)))(left, right)
        return left

    def not_(self):
        if self._is("not"):
            self.take()
            inner = self.not_()
            return lambda r: not inner(r)
        return self.cmp()

    def cmp(self):
        left, lmeta = self.value()
        k, v = self.peek()
        if k == "id" and str(v).lower() in CMP:
            op = str(self.take()[1]).lower()
            right, rmeta = self.value()
            self._check_types(lmeta, rmeta)
            return self._compare(op, left, right)
        return left

    def _check_types(self, a, b):
        # a, b: ('field', edm_type) | ('lit', kind) | ('expr', None)
        for x, y in ((a, b), (b, a)):
            if x[0] == "field" and y[0] == "lit" and y[1] != "null":
                want = COMPAT.get(x[1], "str")
                if want != y[1]:
                    hint = {"guid": "guid'…'", "dt": "datetime'…'", "str": "'…'", "num": "число"}[want]
                    raise FilterError(f"Несоответствие типов в $filter: для поля типа {x[1]} нужен литерал {hint}")

    @staticmethod
    def _compare(op, left, right):
        def f(r):
            a, b = left(r), right(r)
            if op == "eq":
                return a == b
            if op == "ne":
                return a != b
            if a is None or b is None:
                return False
            return {"gt": a > b, "ge": a >= b, "lt": a < b, "le": a <= b}[op]
        return f

    def value(self):
        k, v = self.take()
        if k is None:
            raise FilterError("Неожиданный конец $filter")
        if k == "sym" and v == "(":
            node = self.or_()
            if self.take() != ("sym", ")"):
                raise FilterError("Не закрыта скобка в $filter")
            return node, ("expr", None)
        if k in ("str", "num", "dt", "guid"):
            return (lambda val: lambda r: val)(v), ("lit", k)
        if k == "id":
            low = str(v).lower()
            if low in ("true", "false"):
                return (lambda val: lambda r: val)(low == "true"), ("lit", "bool")
            if low == "null":
                return (lambda r: None), ("lit", "null")
            if self.peek() == ("sym", "("):
                return self.func(low), ("expr", None)
            if v not in self.schema:
                raise FilterError(f"Поле «{v}» не найдено в объекте")
            return (lambda name: lambda r: r.get(name))(v), ("field", self.schema[v])
        raise FilterError(f"Неожиданный элемент «{v}» в $filter")

    def func(self, name):
        self.take()  # (
        args = []
        while True:
            node, _ = self.value()
            args.append(node)
            k, v = self.take()
            if (k, v) == ("sym", ")"):
                break
            if (k, v) != ("sym", ","):
                raise FilterError("Ошибка в списке аргументов функции")
        one = {
            "tolower": lambda s: s.lower() if s else s, "toupper": lambda s: s.upper() if s else s,
            "length": lambda s: len(s or ""), "year": lambda s: int(s[:4]), "month": lambda s: int(s[5:7]),
            "day": lambda s: int(s[8:10]),
        }
        two = {
            "substringof": lambda sub, s: sub.lower() in (s or "").lower(),  # 1С: подстрока без учёта регистра
            "startswith": lambda s, p: (s or "").lower().startswith(p.lower()),
            "endswith": lambda s, p: (s or "").lower().endswith(p.lower()),
        }
        if name in one and len(args) == 1:
            fn, a = one[name], args[0]
            return lambda r: (lambda x: None if x is None else fn(x))(a(r))
        if name in two and len(args) == 2:
            fn, a, b = two[name], args[0], args[1]
            return lambda r: fn(a(r), b(r))
        raise FilterError(f"Функция {name} не поддерживается")


def compile_filter(text: str, schema: dict[str, str]):
    return Parser(text, schema).parse()
