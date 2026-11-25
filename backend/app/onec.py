"""Клиент стандартного интерфейса OData 1С:Предприятие (только чтение)."""
import xml.etree.ElementTree as ET

import httpx

from app.config import settings

KINDS = {
    "Catalog_": "Справочник", "Document_": "Документ",
    "AccumulationRegister_": "Регистр накопления", "InformationRegister_": "Регистр сведений",
}


class OneCError(Exception):
    """Ошибка обращения к 1С. Текст безопасен для показа пользователю и полезен модели для исправления запроса."""


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.onec_odata_url.rstrip("/"), auth=(settings.onec_user, settings.onec_password),
        timeout=httpx.Timeout(5, read=30), headers={"Accept": "application/json"},
    )


def _get(path: str, params: dict | None = None) -> httpx.Response:
    try:
        with _client() as c:
            r = c.get(path, params=params)
    except httpx.HTTPError as e:
        raise OneCError(f"Нет связи с 1С ({type(e).__name__}). Проверьте ONEC_ODATA_URL.") from e
    if r.status_code == 401:
        raise OneCError("1С отклонила учётные данные (ONEC_USER / ONEC_PASSWORD).")
    if r.status_code >= 400:
        try:
            msg = r.json()["odata.error"]["message"]["value"]
        except Exception:
            msg = r.text[:200]
        raise OneCError(msg)
    return r


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def kind_of(name: str) -> str:
    return next((v for k, v in KINDS.items() if name.startswith(k)), "Объект")


def fetch_metadata() -> list[dict]:
    """Объекты, опубликованные в OData: [{name, kind, props: [{name, type, ref?}]}]. Ссылки берём из NavigationProperty."""
    root = ET.fromstring(_get("/$metadata", {}).content)
    assoc: dict[str, dict[str, str]] = {}  # имя связи -> {роль: тип}
    for el in root.iter():
        if _local(el.tag) == "Association":
            assoc[el.get("Name")] = {e.get("Role"): e.get("Type").split(".")[-1] for e in el if _local(e.tag) == "End"}
    out = []
    for el in root.iter():
        if _local(el.tag) != "EntityType":
            continue
        name = el.get("Name")
        props = [{"name": p.get("Name"), "type": p.get("Type")} for p in el if _local(p.tag) == "Property"]
        by_name = {p["name"]: p for p in props}
        for nav in (n for n in el if _local(n.tag) == "NavigationProperty"):
            ends = assoc.get(nav.get("Relationship", "").split(".")[-1], {})
            target = ends.get(nav.get("ToRole"))
            if target and f"{nav.get('Name')}_Key" in by_name:
                by_name[f"{nav.get('Name')}_Key"]["ref"] = target
        out.append({"name": name, "kind": kind_of(name), "props": props})
    if not out:
        raise OneCError("В $metadata не найдено ни одного объекта.")
    return out


def query(entity: str, *, filter: str | None = None, select: list[str] | None = None, orderby: str | None = None,
          top: int | None = None, skip: int | None = None, count: bool = False) -> tuple[list[dict], int | None, str]:
    """Возвращает (строки, всего по фильтру, читаемый вид запроса)."""
    params: dict[str, str] = {"$format": "json"}
    if filter:
        params["$filter"] = filter
    if select:
        params["$select"] = ",".join(select)
    if orderby:
        params["$orderby"] = orderby
    if top is not None:
        params["$top"] = str(top)
    if skip:
        params["$skip"] = str(skip)
    if count:
        params["$inlinecount"] = "allpages"
    r = _get(f"/{entity}", params)
    body = r.json()
    shown = "&".join(f"{k}={v}" for k, v in params.items() if k != "$format")
    total = int(body["odata.count"]) if "odata.count" in body else None
    return body["value"], total, f"{entity}" + (f"?{shown}" if shown else "")
