"""Импорт каталога источников из $metadata 1С.

Из 1С берутся только технические сведения: какие объекты опубликованы и какие у них поля.
Названия, описания, разделы и роли хранятся у нас (в 1С их синонимов в OData нет) и при повторном
импорте не затираются. Новый объект получает безопасные настройки: доступен только администратору."""
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import onec
from app.models import DataSource, UserSource

log = logging.getLogger(__name__)

# служебные поля не показываем в карточке источника (для запросов они остаются доступны)
HIDDEN = {"Ref_Key", "DataVersion", "DeletionMark", "Recorder", "Recorder_Type", "LineNumber", "Active", "IsFolder", "Code"}
# стандартные реквизиты для карточки источника по-русски
RU = {"Number": "Номер", "Date": "Дата", "Posted": "Проведён", "Period": "Период", "Description": "Наименование"}
SECTION_BY_KIND = {"Справочник": "Справочники"}


def _humanize(name: str) -> str:
    return name.split("_", 1)[-1].replace("_", " ")


def display_fields(props: list[dict]) -> list[str]:
    out = []
    for p in props:
        if p["name"] in HIDDEN:
            continue
        out.append(RU.get(p["name"]) or (p["name"][:-4] if p.get("ref") and p["name"].endswith("_Key") else p["name"]))
    return out


def sync_catalog(db: Session) -> dict:
    """Приводит таблицу data_sources в соответствие с метаданными 1С. Возвращает отчёт."""
    objects = {o["name"]: o for o in onec.fetch_metadata()}
    rows = {s.key: s for s in db.scalars(select(DataSource)).all()}
    added, updated = [], []
    for name, o in objects.items():
        fields = display_fields(o["props"])
        if name in rows:
            s = rows[name]
            if s.odata_schema != o["props"] or s.fields != fields:
                updated.append(name)
            s.odata_schema, s.fields, s.kind = o["props"], fields, o["kind"]
        else:
            db.add(DataSource(
                key=name, section=SECTION_BY_KIND.get(o["kind"], "Прочее"), kind=o["kind"], title=_humanize(name),
                description="Объект из 1С. Описание и роли ещё не заданы администратором.",
                fields=fields, allowed_roles=["admin"], odata_schema=o["props"], sort=1000 + len(added),
            ))
            added.append(name)
    removed = [k for k in rows if k not in objects]  # снят с публикации в 1С
    if removed:
        ids = [rows[k].id for k in removed]
        db.execute(delete(UserSource).where(UserSource.source_id.in_(ids)))
        db.execute(delete(DataSource).where(DataSource.id.in_(ids)))
    db.commit()
    log.info("Каталог 1С: добавлено %d, обновлено %d, удалено %d", len(added), len(updated), len(removed))
    return {"total": len(objects), "added": added, "updated": updated, "removed": removed}
