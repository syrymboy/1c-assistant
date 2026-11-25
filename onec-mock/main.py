"""Заглушка стандартного интерфейса OData 1С:Предприятие (только чтение) с тестовыми данными.

Адреса и формат ответов повторяют платформу: /odata/standard.odata/$metadata, /<Объект>?$filter=…
Подключение настоящей 1С сводится к смене ONEC_ODATA_URL и учётных данных в backend."""
import os
import secrets
from xml.sax.saxutils import quoteattr

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import data as seed
from odata_filter import FilterError, compile_filter

USER = os.environ.get("ONEC_USER", "odata")
PASSWORD = os.environ.get("ONEC_PASSWORD", "odata")
BASE = "/odata/standard.odata"

app = FastAPI(title="1C OData mock", docs_url=None, redoc_url=None, openapi_url=None)
basic = HTTPBasic(auto_error=False)
DATA = seed.build()


def auth(creds: HTTPBasicCredentials | None = Depends(basic)) -> None:
    ok = creds is not None and secrets.compare_digest(creds.username, USER) and secrets.compare_digest(creds.password, PASSWORD)
    if not ok:
        raise HTTPException(401, "Неверное имя пользователя или пароль", headers={"WWW-Authenticate": 'Basic realm="1C"'})


@app.exception_handler(HTTPException)
async def odata_error(_: Request, exc: HTTPException):
    # формат ошибок платформы: {"odata.error": {"code": "", "message": {"lang": "ru", "value": "..."}}}
    return JSONResponse(
        {"odata.error": {"code": str(exc.status_code), "message": {"lang": "ru", "value": str(exc.detail)}}},
        status_code=exc.status_code, headers=exc.headers,
    )


@app.get("/health")
def health():
    return {"status": "ok", "objects": len(DATA), "rows": sum(len(v) for v in DATA.values())}


@app.get(f"{BASE}/$metadata", dependencies=[Depends(auth)])
def metadata():
    types, sets, assoc = [], [], []
    for name, spec in seed.SCHEMA.items():
        keys = "".join(f'<PropertyRef Name="{k}"/>' for k in spec["key"])
        props = "".join(
            f'<Property Name="{p}" Type="{t}"{"" if p not in spec["key"] else " Nullable=" + quoteattr("false")}/>' for p, t in spec["props"])
        navs = ""
        for p, _ in spec["props"]:
            if p.endswith("_Key") and p[:-4] in seed.REFS:
                ref = p[:-4]
                navs += f'<NavigationProperty Name="{ref}" Relationship="StandardODATA.{name}_{ref}" FromRole="{name}" ToRole="{seed.REFS[ref]}"/>'
                assoc.append(
                    f'<Association Name="{name}_{ref}"><End Type="StandardODATA.{name}" Role="{name}" Multiplicity="*"/>'
                    f'<End Type="StandardODATA.{seed.REFS[ref]}" Role="{seed.REFS[ref]}" Multiplicity="0..1"/></Association>')
        types.append(f'<EntityType Name="{name}"><Key>{keys}</Key>{props}{navs}</EntityType>')
        sets.append(f'<EntitySet Name="{name}" EntityType="StandardODATA.{name}"/>')
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">'
        '<edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" m:DataServiceVersion="3.0">'
        '<Schema xmlns="http://schemas.microsoft.com/ado/2009/11/edm" Namespace="StandardODATA">'
        + "".join(types) + "".join(assoc) + '<EntityContainer Name="EntityContainer" m:IsDefaultEntityContainer="true">' + "".join(sets)
        + "</EntityContainer></Schema></edmx:DataServices></edmx:Edmx>"
    )
    return Response(xml, media_type="application/xml")


@app.get(f"{BASE}/", dependencies=[Depends(auth)])
def service_document(request: Request):
    return {"odata.metadata": f"{request.base_url}odata/standard.odata/$metadata", "value": [{"name": n, "url": n} for n in DATA]}


def _spec(entity: str) -> dict:
    if entity not in seed.SCHEMA:
        raise HTTPException(404, f"Объект «{entity}» не опубликован в стандартном интерфейсе OData")
    return seed.SCHEMA[entity]


@app.get(f"{BASE}/{{entity}}/$count", dependencies=[Depends(auth)])
def count(entity: str, request: Request):
    return PlainTextResponse(str(len(_select_rows(entity, request.query_params.get("$filter")))))


def _select_rows(entity: str, flt: str | None) -> list[dict]:
    spec = _spec(entity)
    rows = DATA[entity]
    if flt:
        try:
            pred = compile_filter(flt, dict(spec["props"]))
        except FilterError as e:
            raise HTTPException(400, str(e))
        rows = [r for r in rows if pred(r)]
    return rows


@app.get(f"{BASE}/{{entity}}", dependencies=[Depends(auth)])
def query(entity: str, request: Request):
    q = request.query_params
    spec = _spec(entity)
    names = [p for p, _ in spec["props"]]
    rows = _select_rows(entity, q.get("$filter"))
    total = len(rows)

    if q.get("$orderby"):
        for part in reversed([x.strip() for x in q["$orderby"].split(",") if x.strip()]):
            field, _, direction = part.partition(" ")
            if field not in names:
                raise HTTPException(400, f"Поле «{field}» не найдено в объекте")
            rows = sorted(rows, key=lambda r, f=field: (r.get(f) is None, r.get(f)), reverse=direction.strip().lower() == "desc")
    try:
        skip, top = int(q.get("$skip", 0)), q.get("$top")
        rows = rows[skip: skip + int(top)] if top is not None else rows[skip:]
    except ValueError:
        raise HTTPException(400, "$top и $skip должны быть целыми числами")

    if q.get("$select"):
        cols = [c.strip() for c in q["$select"].split(",") if c.strip()]
        bad = [c for c in cols if c not in names]
        if bad:
            raise HTTPException(400, f"Поле «{bad[0]}» не найдено в объекте")
        rows = [{c: r.get(c) for c in cols} for r in rows]

    body = {"odata.metadata": f"{request.base_url}odata/standard.odata/$metadata#{entity}", "value": rows}
    if q.get("$inlinecount") == "allpages":
        body["odata.count"] = str(total)
    return JSONResponse(body)
