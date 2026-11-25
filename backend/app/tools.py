"""Инструменты агента для чтения данных 1С.

Модель не ходит в 1С сама: она просит бэкенд выполнить запрос, а бэкенд проверяет, что объект входит в
разрешённые пользователю источники (роль + его выбор), ограничивает объём и выполняет только чтение (GET).
Каждый вызов попадает в трассу, которую пользователь видит в блоке «Как получен ответ»."""
import json
from collections import defaultdict
from datetime import date

from app import onec
from app.models import DataSource

MAX_ROWS = 100  # строк в одном ответе модели
MAX_SCAN = 5000  # строк, которые можно прочитать для агрегации
PAGE = 1000

FUNCTIONS = [
    {
        "type": "function", "name": "query_1c",
        "description": "Читает строки объекта 1С (OData GET). Возвращает до 100 строк и общее число строк по фильтру. "
                       "Ссылки на справочники возвращаются названиями.",
        "parameters": {"type": "object", "properties": {
            "entity": {"type": "string", "description": "Ключ объекта из списка доступных источников"},
            "filter": {"type": "string", "description": "OData $filter: Date ge datetime'2026-01-01T00:00:00' and Posted eq true; "
                                                        "ссылки: Контрагент_Key eq guid'…'"},
            "select": {"type": "array", "items": {"type": "string"}, "description": "Нужные поля (по умолчанию все)"},
            "orderby": {"type": "string", "description": "Например: СуммаДокумента desc"},
            "top": {"type": "integer", "description": "Сколько строк вернуть, максимум 100 (по умолчанию 20)"},
        }, "required": ["entity"]},
    },
    {
        "type": "function", "name": "aggregate_1c",
        "description": "Группирует и суммирует данные объекта 1С (OData сам этого не умеет, считает бэкенд). "
                       "Для периодов используйте group_by вида «Date:month» или «Period:year».",
        "parameters": {"type": "object", "properties": {
            "entity": {"type": "string"},
            "filter": {"type": "string", "description": "OData $filter, как в query_1c"},
            "group_by": {"type": "array", "items": {"type": "string"}, "description": "Поля группировки; пусто — один итог"},
            "metrics": {"type": "array", "description": "Показатели", "items": {"type": "object", "properties": {
                "field": {"type": "string", "description": "Числовое поле или * для count"},
                "fn": {"type": "string", "enum": ["sum", "avg", "min", "max", "count"]},
            }, "required": ["field", "fn"]}},
            "order_by_metric": {"type": "integer", "description": "Номер показателя (с 1) для сортировки по убыванию"},
            "limit": {"type": "integer", "description": "Сколько групп вернуть, максимум 100 (по умолчанию 20)"},
        }, "required": ["entity", "metrics"]},
    },
    {
        "type": "function", "name": "find_reference",
        "description": "Ищет элементы справочника по части названия и возвращает Ref_Key для фильтров guid'…'.",
        "parameters": {"type": "object", "properties": {
            "entity": {"type": "string", "description": "Ключ справочника, например Catalog_Контрагенты"},
            "text": {"type": "string", "description": "Часть названия"},
        }, "required": ["entity", "text"]},
    },
]


class ToolError(Exception):
    """Ошибка, которую нужно вернуть модели, чтобы она исправила вызов."""


def describe_sources(sources: list[DataSource]) -> str:
    lines = []
    for s in sources:
        fields = []
        for p in s.odata_schema or []:
            if p["name"] in ("DataVersion", "Recorder_Type", "Active", "LineNumber"):
                continue
            ref = f" → {p['ref']}" if p.get("ref") else ""
            fields.append(f"{p['name']}:{p['type'].replace('Edm.', '')}{ref}")
        lines.append(f"- {s.key} — «{s.title}» ({s.kind}). {s.description} Поля: {', '.join(fields)}")
    return "\n".join(lines)


class Toolbox:
    def __init__(self, sources: list[DataSource]):
        self.sources = {s.key: s for s in sources if s.odata_schema}
        self.trace: list[dict] = []
        self._names: dict[str, dict[str, str]] = {}  # справочник -> {Ref_Key: Description}

    @property
    def empty(self) -> bool:
        return not self.sources

    def system_part(self) -> str:
        return (
            f"Сегодня {date.today().isoformat()}. Суммы в тенге (KZT). Доступные пользователю объекты 1С "
            f"(только они, других нет):\n{describe_sources(list(self.sources.values()))}"
        )

    # ---- вызов ----
    def call(self, name: str, args: dict) -> dict:
        entry = {"tool": name, "entity": args.get("entity"), "args": args}
        try:
            fn = {"query_1c": self._query, "aggregate_1c": self._aggregate, "find_reference": self._find}.get(name)
            if fn is None:
                raise ToolError(f"Неизвестный инструмент {name}")
            result, entry["request"] = fn(args)
            entry["rows"] = result.get("returned", result.get("count"))
            return result
        except (ToolError, onec.OneCError) as e:
            entry["error"] = str(e)
            return {"error": str(e)}
        finally:
            self.trace.append(entry)

    def _source(self, entity) -> DataSource:
        if entity not in self.sources:
            raise ToolError(f"Объект «{entity}» недоступен. Доступны: {', '.join(self.sources)}")
        return self.sources[entity]

    @staticmethod
    def _fields(s: DataSource) -> dict[str, dict]:
        return {p["name"]: p for p in s.odata_schema}

    def _check_fields(self, s: DataSource, names: list[str]) -> None:
        bad = [n for n in names if n not in self._fields(s)]
        if bad:
            raise ToolError(f"Поля {bad} нет в «{s.key}». Есть: {', '.join(self._fields(s))}")

    def _resolve(self, s: DataSource, rows: list[dict]) -> list[dict]:
        """Ссылки (Контрагент_Key = guid) заменяем названиями из справочника: модель и пользователь работают с именами."""
        refs = {n: p["ref"] for n, p in self._fields(s).items() if p.get("ref")}
        if not refs or not rows:
            return rows
        out = []
        for r in rows:
            row = dict(r)
            for field, catalog in refs.items():
                if field in row:
                    row[field[:-4]] = self._name(catalog, row.pop(field))
            out.append(row)
        return out

    def _name(self, catalog: str, key) -> str | None:
        if key is None:
            return None
        if catalog not in self._names:
            rows, _, _ = onec.query(catalog, select=["Ref_Key", "Description"], top=PAGE)
            self._names[catalog] = {r["Ref_Key"]: r["Description"] for r in rows}
        return self._names[catalog].get(key, key)

    # ---- инструменты ----
    def _query(self, a: dict):
        s = self._source(a.get("entity"))
        select = a.get("select") or None
        if select:
            self._check_fields(s, select)
        top = max(1, min(int(a.get("top") or 20), MAX_ROWS))
        rows, total, shown = onec.query(s.key, filter=a.get("filter"), select=select, orderby=a.get("orderby"), top=top, count=True)
        return {"count": total, "returned": len(rows), "rows": self._resolve(s, rows)}, shown

    def _find(self, a: dict):
        s = self._source(a.get("entity"))
        text = str(a.get("text", "")).replace("'", "''")
        rows, total, shown = onec.query(s.key, filter=f"substringof('{text}', Description)", select=["Ref_Key", "Description"], top=10, count=True)
        return {"count": total, "returned": len(rows), "items": [{"Ref_Key": r["Ref_Key"], "Название": r["Description"]} for r in rows]}, shown

    def _aggregate(self, a: dict):
        s = self._source(a.get("entity"))
        group_by = a.get("group_by") or []
        metrics = a.get("metrics") or []
        if not metrics:
            raise ToolError("Укажите хотя бы один показатель в metrics")
        fields = self._fields(s)
        parts = [g.partition(":") for g in group_by]
        self._check_fields(s, [p[0] for p in parts] + [m["field"] for m in metrics if m.get("field") != "*"])
        for _, _, part in parts:
            if part not in ("", "year", "month", "day"):
                raise ToolError("После «:» допустимо year, month или day")

        needed = {p[0] for p in parts} | {m["field"] for m in metrics if m["field"] != "*"}
        rows, shown, skip = [], "", 0
        while True:
            page, total, req = onec.query(s.key, filter=a.get("filter"), select=sorted(needed) or None, top=PAGE, skip=skip, count=True)
            shown = shown or req  # в трассе показываем первый запрос; остальные страницы — тот же запрос со смещением
            rows += page
            skip += PAGE
            if len(page) < PAGE or len(rows) >= MAX_SCAN:
                break
        truncated = total is not None and len(rows) < total
        if len(rows) > PAGE:
            shown += f"  (прочитано {len(rows)} строк постранично)"

        def key_of(r):
            out = []
            for name, _, part in parts:
                v = r.get(name)
                if part and v:
                    v = v[: {"year": 4, "month": 7, "day": 10}[part]]
                if fields[name].get("ref"):
                    v = self._name(fields[name]["ref"], v)
                out.append(v)
            return tuple(out)

        groups: dict[tuple, list[dict]] = defaultdict(list)
        for r in rows:
            groups[key_of(r)].append(r)
        result = []
        for k, items in groups.items():
            line = {(p[0][:-4] if fields[p[0]].get("ref") and p[0].endswith("_Key") else p[0] + (f":{p[2]}" if p[2] else "")): v for p, v in zip(parts, k)}
            for i, m in enumerate(metrics, 1):
                vals = [x.get(m["field"]) for x in items if m["field"] == "*" or x.get(m["field"]) is not None]
                fn = m["fn"]
                label = f"{fn}({m['field']})"
                if fn == "count":
                    line[label] = len(vals)
                elif not vals:
                    line[label] = None
                else:
                    line[label] = round({"sum": sum(vals), "avg": sum(vals) / len(vals), "min": min(vals), "max": max(vals)}[fn], 2)
            result.append(line)
        metric_keys = [f"{m['fn']}({m['field']})" for m in metrics]
        if parts:
            by_time = any(p[2] for p in parts) and not a.get("order_by_metric")
            if by_time:  # периоды — по возрастанию
                result.sort(key=lambda r: tuple(str(v) for v in list(r.values())[: len(parts)]))
            else:
                order = metric_keys[int(a.get("order_by_metric") or 1) - 1]
                result.sort(key=lambda r: (r.get(order) is None, -(r.get(order) or 0)))
        limit = max(1, min(int(a.get("limit") or 20), MAX_ROWS))
        out = {"count": len(result), "returned": min(len(result), limit), "scanned_rows": len(rows), "groups": result[:limit]}
        if truncated:
            out["warning"] = f"Прочитано {len(rows)} из {total} строк: итоги неполные. Сузьте период фильтром."
        return out, shown


def to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
