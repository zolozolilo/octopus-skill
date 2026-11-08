"""Тесты peresechenie.py. Запуск: python -I test_peresechenie.py  (все тесты, через pytest)

Оглавление:
  1. Загрузка модуля — по пути рядом (при -I папка скрипта не в sys.path)
  2. Помощник        — прогон main() на временных файлах заданий
  3. Тесты           — имя, слеши, «НЕЛЬЗЯ», «Имя.cs:123», без пересечений, stdin
  4. Сверка          — режим «sverka»: задание против изменённого в git (pytest, tmp_path)
  5. Карта           — «--graphify» и «zadeto» на маленькой карте graph.json (pytest, tmp_path)
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pytest


# ── 1. Загрузка модуля ────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "peresechenie.py"
_spec = importlib.util.spec_from_file_location("peresechenie", SCRIPT)
per = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(per)


# ── 2. Помощник ───────────────────────────────────────────────────────
def run(*extra, **tasks):
    """run("--graphify", репо, A="текст", B="текст") → (код выхода, вывод)."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, text in tasks.items():
            p = Path(tmp) / f"{name}.txt"
            p.write_text(text, encoding="utf-8")
            paths.append(str(p))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = per.main(paths + list(extra))
    return code, out.getvalue()


# ── 3. Тесты ──────────────────────────────────────────────────────────
class Peresechenie(unittest.TestCase):

    def test_po_imeni(self):
        code, out = run(A="Правь Foo.cs и Bar.py", B="ФАЙЛ: Foo.cs, ещё Baz.xaml")
        self.assertEqual(code, 1)
        self.assertIn("СТОП: Foo.cs — A, B", out)

    def test_po_puti_raznye_slesh(self):
        code, out = run(A=r"Файл src\Core\Foo.cs", B="файл SRC/core/foo.CS")
        self.assertEqual(code, 1)
        self.assertIn("СТОП:", out)

    def test_imya_i_put_odin_fail(self):
        code, _ = run(A="Foo.cs", B=r"C:\proj\src\Foo.cs")
        self.assertEqual(code, 1)

    def test_raznye_papki_ne_peresechenie(self):
        code, out = run(A="a/Foo.cs", B="b/Foo.cs")
        self.assertEqual(code, 0)
        self.assertIn("пересечений нет", out)

    def test_tolko_v_nelzya_ne_schitaetsya(self):
        code, out = run(A="Правь Foo.cs", B="Правь Bar.py\nНЕЛЬЗЯ: трогать Foo.cs")
        self.assertEqual(code, 0)
        self.assertIn("нельзя: B", out)
        code, _ = run(A="Foo.cs", B="Bar.py\nНЕ ТРОГАЙ: src/Foo.cs")
        self.assertEqual(code, 0)

    def test_nelzya_spiskom(self):
        own, forb = per.parse_task("Свой: Bar.py\nНЕЛЬЗЯ:\n- Foo.cs\n- Baz.ts\n\nещё Qux.vue")
        self.assertEqual(set(own), {("bar.py",), ("qux.vue",)})
        self.assertEqual(set(forb), {("foo.cs",), ("baz.ts",)})

    def test_stroka_s_nomerom(self):
        own, _ = per.parse_task("смотри Имя.cs:123 и Имя.cs ~123")
        self.assertEqual(set(own), {("имя.cs",)})
        code, out = run(A="Имя.cs:123", B="Имя.cs ~40")
        self.assertEqual(code, 1)
        self.assertIn("СТОП: Имя.cs — A, B", out)

    def test_rasshireniya(self):
        own, _ = per.parse_task("App.csproj, data.json, x.py.bak, run.ps1, a.csx")
        self.assertEqual(set(own), {("app.csproj",), ("data.json",), ("run.ps1",)})

    def test_net_peresecheniy(self):
        code, out = run(A="Foo.cs", B="Bar.py", C="Нет файлов вообще")
        self.assertEqual(code, 0)
        self.assertIn("пересечений нет", out)

    def test_stdin_i_kirillica(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "Ветка1.txt"
            f.write_text("Правь Модуль.py", encoding="utf-8")
            res = subprocess.run([sys.executable, "-I", str(SCRIPT), str(f), "-"],
                                 input="и Модуль.py тоже".encode("utf-8"),
                                 capture_output=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("СТОП: Модуль.py — Ветка1, stdin", res.stdout.decode("utf-8"))


# ── 4. Сверка ─────────────────────────────────────────────────────────
def git(repo, *args):
    """git в временном репо; падает громко, если команда не прошла."""
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args],
                   check=True, capture_output=True)


def put(repo, name, text="x" + chr(10)):
    path = Path(repo) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    """Репо с одним коммитом-базой; тег «base» — точка «от»."""
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    put(r, "README.md")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    git(r, "tag", "base")
    return r


def sverka(tmp_path, repo, task_text, extra=()):
    """Прогон «sverka» → (код выхода, вывод)."""
    task = tmp_path / "задание.txt"
    task.write_text(task_text, encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = per.main(["sverka", str(task), "--repo", str(repo), "--ot", "base", *extra])
    return code, out.getvalue()


def commit(repo, *names):
    for n in names:
        put(repo, n)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "work")


def test_sverka_vne_zadaniya(tmp_path, repo):
    commit(repo, "src/Foo.cs", "src/Lishnee.cs")
    code, out = sverka(tmp_path, repo, "ФАЙЛЫ: src/Foo.cs")
    assert code == 1
    assert "Lishnee.cs" in out
    assert "совпало: 1" in out


def test_sverka_vse_po_zadaniyu(tmp_path, repo):
    commit(repo, "src/Foo.cs", "Bar.py")
    code, out = sverka(tmp_path, repo, "Правь Foo.cs и Bar.py")
    assert code == 0
    assert "вне задания" not in out
    assert "совпало: 2" in out


def test_sverka_nazvan_no_ne_tronut(tmp_path, repo):
    commit(repo, "Foo.cs")
    code, out = sverka(tmp_path, repo, "Foo.cs, Bar.py")
    assert code == 0                                   # для сведения, не ошибка
    assert "названы, но не тронуты" in out and "Bar.py" in out


def test_sverka_test_ryadom_so_slovom_test(tmp_path, repo):
    commit(repo, "src/Foo.cs", "tests/FooTests.cs")
    code, out = sverka(tmp_path, repo, "Правь src/Foo.cs, добавь тест")
    assert code == 0
    assert "вне задания" not in out


def test_sverka_test_ryadom_bez_slova_test(tmp_path, repo):
    commit(repo, "src/Foo.cs", "tests/FooTests.cs")
    code, out = sverka(tmp_path, repo, "Правь src/Foo.cs")
    assert code == 1
    assert "FooTests.cs" in out


def test_sverka_test_chuzhogo_ne_proshchaem(tmp_path, repo):
    commit(repo, "src/Foo.cs", "tests/OtherTests.cs")
    code, out = sverka(tmp_path, repo, "Правь src/Foo.cs, нужен тест")
    assert code == 1
    assert "OtherTests.cs" in out


def test_sverka_nezakommichennoe(tmp_path, repo):
    put(repo, "Foo.cs")                                # новый, не добавлен в git
    put(repo, "README.md", "изменён")          # правка отслеживаемого, не закоммичена
    code, out = sverka(tmp_path, repo, "Foo.cs")
    assert code == 1
    assert "README.md" in out and "совпало: 1" in out


def test_sverka_kirillica_v_puti(tmp_path, repo):
    commit(repo, "модули/Заказы.py", "модули/Левый.py")
    code, out = sverka(tmp_path, repo, "Файл модули/Заказы.py")
    assert code == 1
    assert "Левый.py" in out and "совпало: 1" in out


def test_sverka_do_ogranichivaet(tmp_path, repo):
    commit(repo, "Foo.cs")
    git(repo, "tag", "mid")
    commit(repo, "Lishnee.cs")
    out = io.StringIO()
    task = tmp_path / "t.txt"
    task.write_text("Foo.cs", encoding="utf-8")
    with contextlib.redirect_stdout(out):
        code = per.main(["sverka", str(task), "--repo", str(repo), "--ot", "base", "--do", "mid"])
    assert code == 0


# ── 5. Карта ──────────────────────────────────────────────────────────
# Заказы ← счета (вызов функции заказов) ← отчёт (импорт счетов); тест заказов импортирует заказы.
# Описание заказов (документ) ссылается на функцию заказов. Два router.py — неоднозначное имя;
# config.py в корне и в sub/ (sub/user.py импортирует sub/config.py) — голое имя не угадываем.
# «contains» и «rationale_for» — устройство, не зависимость.
MAP_FILES = ["app/orders.py", "app/invoices.py", "app/otchet.py", "tests/test_orders.py",
             "app/router.py", "lib/router.py", "docs/orders.md",
             "config.py", "sub/config.py", "sub/user.py"]


def uzel(uid, path, label=None, kind="code"):
    return {"id": uid, "label": label or Path(path).name, "source_file": path, "file_type": kind}


MAP = {
    "directed": True, "multigraph": False, "graph": {},
    "nodes": [uzel("orders", "app/orders.py"), uzel("orders.vydat", "app/orders.py", "vydat()"),
              uzel("invoices", "app/invoices.py"), uzel("invoices.sozdat", "app/invoices.py", "sozdat()"),
              uzel("otchet", "app/otchet.py"), uzel("t_orders", "tests/test_orders.py"),
              uzel("router_a", "app/router.py"), uzel("router_b", "lib/router.py"),
              uzel("opisanie", "docs/orders.md", "Заказы", kind="document"),
              uzel("cfg_root", "config.py"), uzel("cfg_sub", "sub/config.py", "sub/config.py"),
              uzel("user", "sub/user.py"),
              {"id": "logging", "label": "logging"}],
    "links": [
        {"source": "invoices.sozdat", "target": "orders.vydat", "relation": "calls"},
        {"source": "otchet", "target": "invoices", "relation": "imports_from"},
        {"source": "t_orders", "target": "orders", "relation": "imports"},
        {"source": "opisanie", "target": "orders.vydat", "relation": "references"},
        {"source": "user", "target": "cfg_sub", "relation": "imports_from"},
        {"source": "orders", "target": "orders.vydat", "relation": "defines"},
        {"source": "orders", "target": "logging", "relation": "calls"},
        {"source": "router_a", "target": "orders", "relation": "contains"},
        {"source": "router_b", "target": "orders", "relation": "rationale_for"},
    ],
}


@pytest.fixture
def karta(tmp_path):
    """Репо с файлами и картой graphify-out/graph.json; карта новее файлов."""
    r = tmp_path / "repo"
    old = time.time() - 3600
    for f in MAP_FILES:
        put(r, f)
        os.utime(r / f, (old, old))
    (r / "graphify-out").mkdir()
    (r / "graphify-out" / "graph.json").write_text(json.dumps(MAP), encoding="utf-8")
    return r


def zadeto(*args):
    """Прогон «zadeto» → (код выхода, вывод)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = per.main(["zadeto", *map(str, args)])
    return code, out.getvalue()


def test_karta_pryamaya_svyaz_stop(karta):
    """Заявки вызывают функцию заказов: правка заказов задевает счета напрямую — СТОП."""
    code, out = run("--graphify", str(karta), A="Правь app/orders.py", B="Правь app/invoices.py")
    assert code == 1
    assert "СТОП-СВЯЗЬ: правка «A» задевает app/invoices.py из «B»" in out


def test_karta_cherez_odnogo_preduprezhdenie(karta):
    """Отчёт зависит от заказов только через счета — предупреждение, не СТОП."""
    code, out = run("--graphify", str(karta), A="app/orders.py", C="app/otchet.py")
    assert code == 0
    assert "СТОП-СВЯЗЬ" not in out
    assert "через одного: правка «A» задевает app/otchet.py из «C» (через app/invoices.py)" in out


def test_karta_testy_priyomshchiku(karta):
    """Тесты, которые задевает правка задания, — списком приёмщику."""
    _, out = run("--graphify", str(karta), A="app/orders.py")
    assert "тесты для «A» (1): tests/test_orders.py" in out


def test_karta_ustrojstvo_ne_svyaz(karta):
    """«contains» и «rationale_for» — не вызов и не импорт: router.py заказы не задевает."""
    code, out = run("--graphify", str(karta), A="app/orders.py", R="app/router.py", L="lib/router.py")
    assert code == 0
    assert "СТОП-СВЯЗЬ" not in out and "через одного" not in out


def test_karta_neodnoznachnoe_imya(karta):
    """Голое имя, а в карте два таких файла, — не угадываем, просим путь."""
    code, out = run("--graphify", str(karta), A="Правь router.py")
    assert code == 0
    assert "A: router.py — имя неоднозначно (2 файла в карте) — дай путь" in out


def test_karta_goloe_imya_koren_i_podpapka(karta):
    """«config.py» есть в корне и в sub/: точное совпадение с корнем — тоже догадка, просим путь."""
    code, out = run("--graphify", str(karta), A="Правь config.py", U="Правь sub/user.py")
    assert "A: config.py — имя неоднозначно (2 файла в карте) — дай путь" in out
    assert "прямых связей между заданиями нет" not in out
    assert code == 0


def test_karta_put_iz_neskolkih_chastej_tochno(karta):
    """Путь от корня репо — не догадка: sub/config.py берём сразу и видим импорт из sub/user.py."""
    code, out = run("--graphify", str(karta), A="sub/config.py", U="sub/user.py")
    assert code == 1
    assert "СТОП-СВЯЗЬ: правка «A» задевает sub/user.py из «U»" in out


def test_karta_net_v_karte(karta):
    _, out = run("--graphify", str(karta), A="app/novyj.py")
    assert "A: app/novyj.py — нет в карте" in out


def test_karta_ne_provereno_ne_chisto(karta):
    """Файл задания не нашёлся в карте — «связей нет» без оговорки не говорим."""
    code, out = run("--graphify", str(karta), A="app/novyj.py", B="app/invoices.py")
    assert code == 0
    assert "прямых связей между заданиями нет" not in out
    assert "не проверено файлов: 1" in out


def test_karta_pustaya(karta):
    """Пустая карта — проверки не было: «НЕ ЗНАЮ», а не «связей нет»."""
    (karta / "graphify-out" / "graph.json").write_text('{"nodes": [], "links": []}', encoding="utf-8")
    code, out = run("--graphify", str(karta), A="app/orders.py", B="app/invoices.py")
    assert code == 2
    assert "карта: НЕ ЗНАЮ" in out
    assert "связей между заданиями нет" not in out


def test_karta_klyuch_edges(karta):
    """networkx новее пишет рёбра под ключом «edges» — читаем и его."""
    graph = {**MAP, "edges": MAP["links"]}
    del graph["links"]
    (karta / "graphify-out" / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    code, out = run("--graphify", str(karta), A="app/orders.py", B="app/invoices.py")
    assert code == 1
    assert "СТОП-СВЯЗЬ" in out


def test_karta_ne_kod_ne_shumit(karta):
    """Карта знает .py и .md: .json в задании — одна строка «карта не видит», без «нет в карте»."""
    _, out = run("--graphify", str(karta), A="app/orders.py, config/nastrojki.json")
    assert "нет в карте" not in out
    assert "карта не видит: .json" in out


def test_karta_dokument_ne_stop(karta):
    """Описание ссылается на функцию заказов: правка кода документ не ломает — сверить текст, не СТОП."""
    code, out = run("--graphify", str(karta), A="app/orders.py", P="docs/orders.md")
    assert code == 0
    assert "СТОП-СВЯЗЬ" not in out
    assert "документ: docs/orders.md из «P» ссылается на код «A» — сверить текст после правки" in out


def test_karta_absolyutnyj_put_i_obratnye_slesh(karta):
    code, out = run("--graphify", str(karta), A=str(karta / "app" / "orders.py"), B=r"app\invoices.py")
    assert code == 1
    assert "СТОП-СВЯЗЬ" in out


def test_karta_ne_garantiya(karta):
    """Карта не видит общих ключей JSON и полей данных — вывод говорит это прямо."""
    _, out = run("--graphify", str(karta), A="app/orders.py")
    assert "не гарантия" in out and "grep" in out


def test_karta_ustarela(karta):
    """Файл правлен после карты: предупреждение с командой обновления, код выхода тот же."""
    future = time.time() + 60
    os.utime(karta / "app" / "invoices.py", (future, future))
    code, out = run("--graphify", str(karta), A="app/orders.py")
    assert code == 0
    assert "карта старше кода: после неё правили 1 файл (app/invoices.py)" in out
    assert "graphify update" in out


def test_karta_svezhaya_molchit(karta):
    _, out = run("--graphify", str(karta), A="app/orders.py")
    assert "карта старше кода" not in out


def test_karta_net_karty(tmp_path):
    code, out = run("--graphify", str(tmp_path), A="app/orders.py")
    assert code == 2
    assert "карта: НЕ ЗНАЮ" in out


def test_karta_chuzhoj_format(karta):
    (karta / "graphify-out" / "graph.json").write_text('{"nodes": 1}', encoding="utf-8")
    code, out = run("--graphify", str(karta), A="app/orders.py")
    assert code == 2
    assert "карта: НЕ ЗНАЮ" in out


def test_karta_obnovit_snachala(karta, monkeypatch):
    """--obnovit: сначала одно обновление карты, потом проверка."""
    calls = []
    monkeypatch.setattr(per, "obnovit_kartu", calls.append)
    code, _ = run("--graphify", str(karta), "--obnovit", A="app/orders.py")
    assert calls == [str(karta)]
    assert code == 0


def test_karta_obnovit_ne_vyshlo(karta, monkeypatch):
    """Обновить не вышло — говорим и проверяем по старой карте."""
    def fail(repo):
        raise RuntimeError("graphify не найден")
    monkeypatch.setattr(per, "obnovit_kartu", fail)
    code, out = run("--graphify", str(karta), "--obnovit", A="app/orders.py")
    assert "обновить не вышло — graphify не найден" in out
    assert "тесты для «A» (1)" in out
    assert code == 0


def test_zadeto_nizhnij_konec(karta):
    """Нижний конец дерева: кого задевает правка файла — напрямую, через одного, тесты."""
    code, out = zadeto("app/orders.py", "--repo", karta)
    assert code == 0
    assert "напрямую (2): app/invoices.py, tests/test_orders.py" in out
    assert "через одного (1): app/otchet.py" in out
    assert "тесты (1): tests/test_orders.py" in out
    assert "документы (1): docs/orders.md" in out


def test_zadeto_odin_fajl_dvazhdy(karta):
    _, out = zadeto("app/orders.py", "app/orders.py", "--repo", karta)
    assert out.count("— правка задевает:") == 1


def test_zadeto_net_v_karte(karta):
    code, out = zadeto("app/novyj.py", "--repo", karta)
    assert code == 2
    assert "app/novyj.py — нет в карте" in out


if __name__ == "__main__":
    # Все тесты разом: unittest-классы и pytest-функции; кэш pytest в папку скилла не пишем.
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
