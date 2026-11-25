"""Детерминированные тестовые данные «1С» и описание объектов (схема для $metadata).

Имена полей повторяют стандартный интерфейс OData 1С: служебные (Ref_Key, Date, Number, Posted, Period,
Recorder, LineNumber, Active) на английском, реквизиты конфигурации на русском."""
import random
import uuid
from datetime import datetime, timedelta

G, S, B, D, N, I = "Edm.Guid", "Edm.String", "Edm.Boolean", "Edm.DateTime", "Edm.Decimal", "Edm.Int32"

CATALOG_BASE = [("Ref_Key", G), ("DataVersion", S), ("DeletionMark", B), ("Code", S), ("Description", S)]
DOC_BASE = [("Ref_Key", G), ("DataVersion", S), ("DeletionMark", B), ("Number", S), ("Date", D), ("Posted", B)]
REG_BASE = [("Recorder", G), ("Recorder_Type", S), ("LineNumber", I), ("Active", B), ("Period", D)]

SCHEMA: dict[str, dict] = {
    "Catalog_Склады": {"props": CATALOG_BASE + [("Тип", S)], "key": ["Ref_Key"]},
    "Catalog_Контрагенты": {"props": CATALOG_BASE + [("ИНН", S), ("Группа", S)], "key": ["Ref_Key"]},
    "Catalog_Номенклатура": {"props": CATALOG_BASE + [("Артикул", S), ("Группа", S), ("Единица", S)], "key": ["Ref_Key"]},
    "Document_РеализацияТоваровУслуг": {
        "props": DOC_BASE + [("Контрагент_Key", G), ("Склад_Key", G), ("СуммаДокумента", N), ("Организация", S)], "key": ["Ref_Key"]},
    "Document_ЗаказПокупателя": {
        "props": DOC_BASE + [("Контрагент_Key", G), ("СуммаДокумента", N), ("Статус", S)], "key": ["Ref_Key"]},
    "Document_ПоступлениеТоваровУслуг": {
        "props": DOC_BASE + [("Контрагент_Key", G), ("Склад_Key", G), ("СуммаДокумента", N)], "key": ["Ref_Key"]},
    "Document_НачислениеЗарплаты": {
        "props": DOC_BASE + [("Месяц", D), ("Сотрудник", S), ("Сумма", N)], "key": ["Ref_Key"]},
    "AccumulationRegister_Продажи": {
        "props": REG_BASE + [("Номенклатура_Key", G), ("Контрагент_Key", G), ("Количество", N), ("Выручка", N),
                             ("Себестоимость", N), ("Филиал", S)], "key": ["Recorder", "LineNumber"]},
    "AccumulationRegister_ТоварыНаСкладах": {
        "props": REG_BASE + [("Номенклатура_Key", G), ("Склад_Key", G), ("Количество", N)], "key": ["Recorder", "LineNumber"]},
    "AccumulationRegister_РасчетыСПокупателями": {
        "props": REG_BASE + [("Контрагент_Key", G), ("Договор", S), ("СуммаДолга", N), ("СрокОплаты", D)],
        "key": ["Recorder", "LineNumber"]},
    "AccumulationRegister_РасчетыСПоставщиками": {
        "props": REG_BASE + [("Контрагент_Key", G), ("Договор", S), ("СуммаДолга", N), ("СрокОплаты", D)],
        "key": ["Recorder", "LineNumber"]},
    "AccumulationRegister_ДвиженияДенежныхСредств": {
        "props": REG_BASE + [("Счёт", S), ("Статья", S), ("Сумма", N)], "key": ["Recorder", "LineNumber"]},
}

# Реквизит-ссылка -> справочник, на который он указывает (в $metadata выражается через NavigationProperty)
REFS = {"Контрагент": "Catalog_Контрагенты", "Склад": "Catalog_Склады", "Номенклатура": "Catalog_Номенклатура"}

WAREHOUSES = [("Основной склад (Алматы)", "Оптовый", "Алматы"), ("Склад Астана", "Оптовый", "Астана"),
              ("Склад Шымкент", "Оптовый", "Шымкент"), ("Магазин Алматы", "Розничный", "Алматы")]
ITEMS = [  # наименование, группа, единица, себестоимость (тенге)
    ("Кофе в зернах Arabica 1 кг", "Напитки", "кг", 6200), ("Кофе молотый Classic 250 г", "Напитки", "уп", 1800),
    ("Чай чёрный Ассам 100 пак.", "Напитки", "уп", 1100), ("Чай зелёный Сенча 100 пак.", "Напитки", "уп", 1250),
    ("Молоко ультрапастеризованное 3.2%", "Напитки", "шт", 520), ("Сок яблочный 1 л", "Напитки", "шт", 640),
    ("Вода минеральная 0.5 л", "Напитки", "шт", 180), ("Сироп «Ваниль» 1 л", "Бакалея", "шт", 3400),
    ("Сироп «Карамель» 1 л", "Бакалея", "шт", 3400), ("Сахар-песок 1 кг", "Бакалея", "кг", 450),
    ("Мука пшеничная 2 кг", "Бакалея", "шт", 780), ("Рис длиннозёрный 1 кг", "Бакалея", "кг", 620),
    ("Печенье овсяное 400 г", "Кондитерские изделия", "уп", 710), ("Шоколад молочный 90 г", "Кондитерские изделия", "шт", 420),
    ("Конфеты ассорти 1 кг", "Кондитерские изделия", "кг", 2900), ("Вафли ореховые 300 г", "Кондитерские изделия", "уп", 560),
    ("Стакан бумажный 250 мл (уп. 50 шт.)", "Расходные материалы", "уп", 950),
    ("Крышка для стакана (уп. 100 шт.)", "Расходные материалы", "уп", 700),
    ("Салфетки бумажные (уп. 200 шт.)", "Расходные материалы", "уп", 380), ("Пакет бумажный 20×10 (уп. 100 шт.)", "Расходные материалы", "уп", 1300),
    ("Кофемашина Delonghi ECAM", "Оборудование", "шт", 185000), ("Кофемолка Bosch TCA", "Оборудование", "шт", 42000),
    ("Чайник электрический 1.7 л", "Оборудование", "шт", 14500), ("Термопот 4 л", "Оборудование", "шт", 36000),
]
CUSTOMERS = ["Альфа Трейд", "Берёзка Маркет", "Каспий Фуд", "Нур Ритейл", "Сарыарка Опт", "Алатау Кофе", "Шанырак", "Тулпар Групп",
             "Жетысу Торг", "Семей Продукт", "Атамекен Плюс", "Байтерек Сервис", "Мерей Холдинг", "Арман Фуд", "Достык Трейд",
             "Кайрат Логистик", "Тау Маркет", "Ертіс Снаб", "Астана Дистрибьюшн", "Шымкент Опт", "Юг Продукт", "Север Трейд",
             "Орда Кейтеринг", "Самал Кафе", "Сункар Групп", "Нұр Кофе", "Азия Бизнес", "Оазис Ритейл", "Горный Ручей", "Дала Фуд"]
SUPPLIERS = ["Бразил Кофе Импорт", "Чайная Компания «Ассам»", "ТД «Молочный путь»", "Сахарный Завод Казахстана",
             "Упаковка Плюс", "Техносервис Оборудование", "Кондитерская фабрика «Рахат»", "Мукомол Сервис"]
EMPLOYEES = ["Иванов Андрей", "Петрова Мария", "Сейтказин Ержан", "Ахметова Айгерим", "Ким Олег", "Нурпеисова Дана", "Волков Сергей", "Омарова Асель"]
ACCOUNTS = ["Расчётный счёт KZ12…4567", "Касса"]
CASH_ARTICLES = [("Поступление от покупателя", 1), ("Оплата поставщику", -1), ("Зарплата", -1), ("Аренда", -1), ("Налоги", -1)]


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def build(now: datetime | None = None) -> dict[str, list[dict]]:
    rnd = random.Random(20240601)
    now = (now or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)

    def guid() -> str:
        return str(uuid.UUID(int=rnd.getrandbits(128), version=4))

    def day(back_max: int) -> datetime:
        return now - timedelta(days=rnd.randint(0, back_max), hours=-rnd.randint(8, 19), minutes=-rnd.randint(0, 59))

    def cat(name: str, code: int, **extra) -> dict:
        return {"Ref_Key": guid(), "DataVersion": "AAAAAA==", "DeletionMark": False, "Code": f"{code:09d}", "Description": name, **extra}

    def doc(prefix: str, n: int, when: datetime, posted: bool = True, **extra) -> dict:
        return {"Ref_Key": guid(), "DataVersion": "AAAAAA==", "DeletionMark": False, "Number": f"{prefix}-{n:06d}",
                "Date": _iso(when), "Posted": posted, **extra}

    data: dict[str, list[dict]] = {k: [] for k in SCHEMA}
    wh = [cat(n, i + 1, Тип=t) for i, (n, t, _) in enumerate(WAREHOUSES)]
    city = {w["Ref_Key"]: WAREHOUSES[i][2] for i, w in enumerate(wh)}
    items = [cat(n, i + 1, Артикул=f"ART-{1000 + i}", Группа=g, Единица=u) for i, (n, g, u, _) in enumerate(ITEMS)]
    cost = {it["Ref_Key"]: ITEMS[i][3] for i, it in enumerate(items)}
    buyers = [cat(f"ТОО «{n}»", i + 1, ИНН=f"{rnd.randint(10**11, 10**12 - 1)}", Группа="Покупатели") for i, n in enumerate(CUSTOMERS)]
    sellers = [cat(n if "«" in n else f"ТОО «{n}»", 100 + i, ИНН=f"{rnd.randint(10**11, 10**12 - 1)}", Группа="Поставщики") for i, n in enumerate(SUPPLIERS)]
    data["Catalog_Склады"], data["Catalog_Номенклатура"], data["Catalog_Контрагенты"] = wh, items, buyers + sellers

    def reg(rec: dict, rec_type: str, line: int, period: str, **extra) -> dict:
        return {"Recorder": rec["Ref_Key"], "Recorder_Type": f"StandardODATA.{rec_type}", "LineNumber": line,
                "Active": True, "Period": period, **extra}

    # Реализации + движения регистра «Продажи»
    big = buyers[:8]  # крупные клиенты покупают чаще
    for n in range(1, 561):
        when = day(364)
        buyer = rnd.choice(big) if rnd.random() < 0.45 else rnd.choice(buyers)
        w = rnd.choices(wh, weights=[4, 3, 2, 3])[0]
        d = doc("РТ", n, when, posted=rnd.random() > 0.04, Контрагент_Key=buyer["Ref_Key"], Склад_Key=w["Ref_Key"],
                СуммаДокумента=0, Организация="ТОО «Кофейный дом»")
        total = 0.0
        for line in range(1, rnd.randint(1, 4) + 1):
            it = rnd.choice(items)
            qty = rnd.randint(1, 6) if cost[it["Ref_Key"]] > 30000 else rnd.randint(5, 80)
            revenue = round(qty * cost[it["Ref_Key"]] * rnd.uniform(1.18, 1.45), 2)
            total += revenue
            if d["Posted"]:
                data["AccumulationRegister_Продажи"].append(reg(
                    d, "Document_РеализацияТоваровУслуг", line, d["Date"], Номенклатура_Key=it["Ref_Key"], Контрагент_Key=buyer["Ref_Key"],
                    Количество=qty, Выручка=revenue, Себестоимость=round(qty * cost[it["Ref_Key"]], 2), Филиал=city[w["Ref_Key"]]))
        d["СуммаДокумента"] = round(total, 2)
        data["Document_РеализацияТоваровУслуг"].append(d)

    for n in range(1, 261):
        when = day(364)
        status = "Выполнен" if (now - datetime.fromisoformat(_iso(when))).days > 20 else rnd.choice(["Новый", "В работе", "Выполнен"])
        if rnd.random() < 0.06:
            status = "Отменён"
        data["Document_ЗаказПокупателя"].append(doc(
            "ЗП", n, when, Контрагент_Key=rnd.choice(buyers)["Ref_Key"], СуммаДокумента=round(rnd.uniform(40_000, 2_400_000), 2), Статус=status))

    for n in range(1, 161):
        data["Document_ПоступлениеТоваровУслуг"].append(doc(
            "ПТ", n, day(364), Контрагент_Key=rnd.choice(sellers)["Ref_Key"], Склад_Key=rnd.choice(wh)["Ref_Key"],
            СуммаДокумента=round(rnd.uniform(150_000, 6_000_000), 2)))

    n = 0
    for m in range(12):
        first = (now.replace(day=1) - timedelta(days=31 * m)).replace(day=1)
        for emp in EMPLOYEES:
            n += 1
            data["Document_НачислениеЗарплаты"].append(doc(
                "НЗ", n, first + timedelta(days=27, hours=10), Месяц=_iso(first), Сотрудник=emp, Сумма=round(rnd.uniform(280_000, 720_000), -2)))

    # Остатки: часть позиций специально на исходе
    line = 0
    stock_doc = {"Ref_Key": guid()}
    for it in items:
        for w in wh:
            line += 1
            low = rnd.random() < 0.18
            qty = rnd.randint(0, 6) if low else rnd.randint(25, 400)
            if cost[it["Ref_Key"]] > 30000:
                qty = rnd.randint(0, 4)
            data["AccumulationRegister_ТоварыНаСкладах"].append(reg(
                stock_doc, "Document_ПоступлениеТоваровУслуг", line, _iso(now), Номенклатура_Key=it["Ref_Key"], Склад_Key=w["Ref_Key"], Количество=qty))

    for kind, parties, label in (("РасчетыСПокупателями", buyers, "покупателем"), ("РасчетыСПоставщиками", sellers, "поставщиком")):
        for i, p in enumerate(parties):
            owe = rnd.random() < 0.7
            due = now - timedelta(days=rnd.randint(-20, 95))
            data[f"AccumulationRegister_{kind}"].append(reg(
                {"Ref_Key": guid()}, "Document_РеализацияТоваровУслуг", 1, _iso(now), Контрагент_Key=p["Ref_Key"],
                Договор=f"Договор № {100 + i} с {label}", СуммаДолга=round(rnd.uniform(60_000, 3_200_000), 2) if owe else 0, СрокОплаты=_iso(due)))

    for i in range(1, 321):
        art, sign = rnd.choice(CASH_ARTICLES[:1] * 4 + CASH_ARTICLES[1:])
        data["AccumulationRegister_ДвиженияДенежныхСредств"].append(reg(
            {"Ref_Key": guid()}, "Document_ПриходныйКассовыйОрдер", i, _iso(day(364)), Счёт=rnd.choice(ACCOUNTS), Статья=art,
            Сумма=sign * round(rnd.uniform(30_000, 2_500_000), 2)))
    return data
