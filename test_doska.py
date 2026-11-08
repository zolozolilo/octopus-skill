"""Тесты doska.py: данные и страница — во временной папке (doska.DATA_DIR → tmp_path).
Запуск:  python -m pytest test_doska.py -q
Время подменяем: doska.now возвращает значения из списка, чтобы видеть, ставится ли оно и сколько раз.
"""
import json

import pytest

import doska


@pytest.fixture
def papka(tmp_path, monkeypatch):
    monkeypatch.setattr(doska, "DATA_DIR", tmp_path)
    monkeypatch.setattr(doska, "now", lambda: "2026-10-24T10:00:00")
    return tmp_path


def run(*argv):
    return doska.main(list(argv))


def data_of(papka):
    return json.loads((papka / "derevo.json").read_text(encoding="utf-8"))


def leaf_of(papka, lid):
    for t in data_of(papka)["derevya"]:
        for x in t["listya"]:
            if x["id"] == lid:
                return x
    raise AssertionError(lid)


def test_sozdanie_dereva_i_listev(papka):
    assert run("derevo", "t1", "Первое") == 0
    assert run("list", "a", "ждёт", "--v", "t1", "--zadacha", "Сделать A", "--kto", "я") == 0
    assert run("list", "b", "ждёт", "--v", "a", "--zadacha", "Под-лист B") == 0
    d = data_of(papka)
    assert d["derevya"][0]["nazvanie"] == "Первое"
    assert [x["id"] for x in d["derevya"][0]["listya"]] == ["a", "b"]
    assert leaf_of(papka, "a")["kto"] == "я" and leaf_of(papka, "a")["v"] == ""
    assert leaf_of(papka, "b")["v"] == "a"


def test_obnovlenie_ne_trogaet_ostalnye_polya(papka):
    run("derevo", "t1", "Первое")
    run("list", "a", "ждёт", "--v", "t1", "--zadacha", "Сделать A", "--kto", "агент E", "--zametka", "n")
    run("list", "a", "идёт")
    x = leaf_of(papka, "a")
    assert (x["zadacha"], x["kto"], x["zametka"], x["status"]) == ("Сделать A", "агент E", "n", "идёт")


def test_vremya_stavitsya_odin_raz(papka, monkeypatch):
    run("derevo", "t1", "Первое")
    run("list", "a", "ждёт", "--v", "t1", "--zadacha", "A")
    assert leaf_of(papka, "a")["nachato"] == "" and leaf_of(papka, "a")["gotovo"] == ""
    run("list", "a", "идёт")
    assert leaf_of(papka, "a")["nachato"] == "2026-10-24T10:00:00"
    monkeypatch.setattr(doska, "now", lambda: "2026-10-24T11:00:00")
    run("list", "a", "идёт")                                 # тот же статус — время не двигаем
    assert leaf_of(papka, "a")["nachato"] == "2026-10-24T10:00:00"
    run("list", "a", "готово")
    assert leaf_of(papka, "a")["gotovo"] == "2026-10-24T11:00:00"
    monkeypatch.setattr(doska, "now", lambda: "2026-10-24T12:00:00")
    run("list", "a", "готово")                               # повтор — конец не меняется
    assert leaf_of(papka, "a")["gotovo"] == "2026-10-24T11:00:00"
    assert leaf_of(papka, "a")["nachato"] == "2026-10-24T10:00:00"


def test_vozvrat_v_rabotu_snimaet_konec(papka):
    run("derevo", "t1", "Первое")
    run("list", "a", "сломано", "--v", "t1", "--zadacha", "A")
    assert leaf_of(papka, "a")["gotovo"] != ""
    run("list", "a", "идёт")
    assert leaf_of(papka, "a")["gotovo"] == ""


def test_bez_vremeni_ostavlyaet_pustym(papka):
    run("derevo", "t1", "Первое")
    run("list", "a", "готово", "--v", "t1", "--zadacha", "A", "--bez-vremeni")
    x = leaf_of(papka, "a")
    assert x["status"] == "готово" and x["nachato"] == "" and x["gotovo"] == ""


def test_ubrat_derevo(papka):
    run("derevo", "t1", "Первое")
    run("derevo", "t2", "Второе")
    run("list", "a", "ждёт", "--v", "t1", "--zadacha", "A")
    assert run("ubrat", "t1") == 0
    assert [t["id"] for t in data_of(papka)["derevya"]] == ["t2"]
    assert "A" not in (papka / "doska.html").read_text(encoding="utf-8").split("<main>")[1].split("</main>")[0]
    assert run("ubrat", "net-takogo") == 1


def test_otkazy(papka):
    run("derevo", "t1", "Первое")
    assert run("derevo", "t1", "Дубль") == 1                 # id занят
    assert run("list", "a", "ждёт") == 1                     # новому листу нужен родитель и задача
    assert run("list", "a", "ждёт", "--v", "net", "--zadacha", "A") == 1
    assert run("list", "t1", "ждёт", "--zadacha", "A", "--v", "t1") == 1   # id дерева — не лист
    run("list", "a", "ждёт", "--v", "t1", "--zadacha", "A")
    run("list", "b", "ждёт", "--v", "a", "--zadacha", "B")
    assert run("list", "a", "ждёт", "--v", "b") == 1         # цикл: родитель — потомок


def test_ekranirovanie(papka):
    evil = "<script>alert(1)</script>"
    run("derevo", "t1", evil)
    run("list", "a", "готово", "--v", "t1", "--zadacha", evil, "--kto", evil, "--zametka", "</script><b>x")
    page = (papka / "doska.html").read_text(encoding="utf-8")
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count("</script>") == 2                       # только наши два тега: данные и код
    # данные в JSON-блоке читаются обратно без потерь
    blob = page.split('id="dannye">')[1].split("</script>")[0]
    assert json.loads(blob)["derevya"][0]["nazvanie"] == evil


def test_atomarnost_oshibka_kodirovaniya(papka):
    run("derevo", "t1", "Первое")
    before_json = (papka / "derevo.json").read_bytes()
    before_html = (papka / "doska.html").read_bytes()
    # одинокий суррогат не кодируется в UTF-8: UnicodeEncodeError — это ValueError, main отвечает отказом
    assert run("list", "a", "ждёт", "--v", "t1", "--zadacha", "плохо \ud800") == 1
    assert (papka / "derevo.json").read_bytes() == before_json != b""
    assert (papka / "doska.html").read_bytes() == before_html != b""
    assert [p.name for p in papka.iterdir() if p.suffix == ".tmp"] == []


def test_atomarnost_sboy_zapisi_ne_pustit_fayl(papka, monkeypatch):
    run("derevo", "t1", "Первое")
    before = (papka / "doska.html").read_bytes()
    monkeypatch.setattr(doska.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("диск")))
    assert run("list", "a", "ждёт", "--v", "t1", "--zadacha", "A") == 2
    assert (papka / "doska.html").read_bytes() == before
    assert [p.name for p in papka.iterdir() if p.suffix == ".tmp"] == []


def test_html_refresh_i_vse_listya(papka):
    run("derevo", "t1", "Первое")
    run("derevo", "t2", "Второе")
    names = []
    for i, (tree, st) in enumerate([("t1", "ждёт"), ("t1", "идёт"), ("t2", "готово"), ("t2", "сломано")]):
        run("list", f"l{i}", st, "--v", tree, "--zadacha", f"задача номер {i}", "--kto", "агент X")
        names.append(f"задача номер {i}")
    page = (papka / "doska.html").read_text(encoding="utf-8")
    assert '<meta http-equiv="refresh" content="10">' in page
    for n in names:
        assert n in page
    assert "Доска осьминога" in page and "prefers-color-scheme: dark" in page
    assert "щупалец занято 1 из 8" in page
    assert "http://" not in page and "https://" not in page   # без внешних ссылок


def test_stroka_svodki(papka):
    run("derevo", "t1", "Первое")
    for lid, st, kto in [("a", "идёт", "агент A"), ("b", "идёт", "я"), ("c", "готово", "агент C"),
                         ("d", "сломано", "скрипт"), ("e", "ждёт", "")]:
        run("list", lid, st, "--v", "t1", "--zadacha", lid, "--kto", kto)
    s = doska.totals(data_of(papka))
    assert s == {"busy": 1, "done": 1, "go": 2, "broken": 1, "wait": 1}
    page = (papka / "doska.html").read_text(encoding="utf-8")
    assert "щупалец занято 1 из 8 (агенты со статусом идёт) · ✔ 1 · ⏳ 2 · ✘ 1 · ждут 1 · обновлено 10:00" in page


def test_pokaz(papka, capsys):
    run("derevo", "t1", "Первое")
    run("list", "a", "готово", "--v", "t1", "--zadacha", "Один", "--kto", "агент")
    run("list", "b", "идёт", "--v", "t1", "--zadacha", "Два")
    run("list", "c", "сломано", "--v", "b", "--zadacha", "Вложенный")
    run("list", "d", "ждёт", "--v", "t1", "--zadacha", "Три")
    capsys.readouterr()
    assert run("pokaz") == 0
    out = capsys.readouterr().out
    assert out.splitlines() == [
        "Первое  [t1]",
        "├─ ✔ a  Один (агент)",
        "├─ ⏳ b  Два",
        "│  └─ ✘ c  Вложенный",
        "└─ · d  Три",
    ]
