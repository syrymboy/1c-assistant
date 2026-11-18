"""data sources catalog (demo seed) and per-user selection"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"

ALL = ["admin", "analyst", "manager"]
FIN = ["admin", "analyst"]

# (key, section, kind, title, description, fields, roles) — демо-каталог до подключения реальной 1С
SEED = [
    ("Document_РеализацияТоваровУслуг", "Продажи", "Документ", "Реализация товаров и услуг",
     "Отгрузки клиентам: что, кому и на какую сумму продано.", ["Дата", "Контрагент", "Склад", "Сумма", "Организация"], ALL),
    ("Document_ЗаказПокупателя", "Продажи", "Документ", "Заказы покупателей",
     "Заказы клиентов и их статус выполнения.", ["Дата", "Контрагент", "Сумма", "Статус"], ALL),
    ("AccumulationRegister_Продажи", "Продажи", "Регистр накопления", "Продажи",
     "Обороты по выручке и себестоимости в разрезе товаров и филиалов.", ["Период", "Номенклатура", "Количество", "Выручка", "Себестоимость", "Филиал"], ALL),
    ("AccumulationRegister_ТоварыНаСкладах", "Склад", "Регистр накопления", "Остатки товаров",
     "Сколько каких товаров лежит на каждом складе.", ["Период", "Номенклатура", "Склад", "Количество"], ALL),
    ("Document_ПоступлениеТоваровУслуг", "Склад", "Документ", "Поступление товаров",
     "Закупки у поставщиков.", ["Дата", "Контрагент", "Склад", "Сумма"], ALL),
    ("Catalog_Номенклатура", "Склад", "Справочник", "Номенклатура",
     "Товары и услуги с группами и артикулами.", ["Наименование", "Артикул", "Группа", "Единица"], ALL),
    ("AccumulationRegister_РасчетыСПокупателями", "Расчёты", "Регистр накопления", "Расчёты с покупателями",
     "Дебиторская задолженность клиентов.", ["Период", "Контрагент", "Договор", "Сумма долга"], FIN),
    ("AccumulationRegister_РасчетыСПоставщиками", "Расчёты", "Регистр накопления", "Расчёты с поставщиками",
     "Кредиторская задолженность перед поставщиками.", ["Период", "Контрагент", "Договор", "Сумма долга"], FIN),
    ("AccumulationRegister_ДвиженияДенежныхСредств", "Расчёты", "Регистр накопления", "Движение денежных средств",
     "Поступления и выплаты по счетам и кассам.", ["Период", "Счёт", "Статья", "Сумма"], FIN),
    ("Catalog_Контрагенты", "Справочники", "Справочник", "Контрагенты",
     "Клиенты и поставщики.", ["Наименование", "ИНН", "Группа"], ALL),
    ("Catalog_Склады", "Справочники", "Справочник", "Склады",
     "Склады и филиалы.", ["Наименование", "Тип"], ALL),
    ("Document_НачислениеЗарплаты", "Персонал", "Документ", "Начисление зарплаты",
     "Зарплатные ведомости. Только для администраторов.", ["Месяц", "Сотрудник", "Сумма"], ["admin"]),
]


def upgrade() -> None:
    t = op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("section", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("fields", postgresql.JSONB, nullable=False),
        sa.Column("allowed_roles", postgresql.JSONB, nullable=False),
        sa.Column("sort", sa.Integer, server_default="0", nullable=False),
    )
    op.create_table(
        "user_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id"), nullable=False),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("data_sources.id"), nullable=False),
        sa.UniqueConstraint("user_id", "source_id"),
    )
    op.bulk_insert(t, [
        dict(key=k, section=sec, kind=kind, title=title, description=d, fields=f, allowed_roles=r, sort=i)
        for i, (k, sec, kind, title, d, f, r) in enumerate(SEED)
    ])


def downgrade() -> None:
    op.drop_table("user_sources")
    op.drop_table("data_sources")
