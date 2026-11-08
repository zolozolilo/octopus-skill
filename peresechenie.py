#!/usr/bin/env python3
"""Пересечение файлов между заданиями агентов: не дали ли один файл двум агентам.

Запуск:  python peresechenie.py <задание1> <задание2> …    («-» — одно задание из stdin)
Выход:   0 — пересечений нет · 1 — СТОП, файл «свой» у двух и более заданий · 2 — ошибка запуска

Скрытые связи по карте кода (Graphify, https://docs.graphify.com):
Запуск:  python peresechenie.py <задание1> <задание2> … --graphify <репо с graphify-out/> [--obnovit]
         файлы разные, но один прямо вызывает или импортирует другой → СТОП-СВЯЗЬ (выход 1);
         связь через один файл — предупреждение; тесты, которые задевает каждое задание, — приёмщику.
         --obnovit — сначала graphify update (только разбор кода, без ИИ; большой репо — минуты).

Нижний конец дерева — кого задевает правка файла (как `graphify affected`, но 2 с вместо 33 с на файл):
Запуск:  python peresechenie.py zadeto <файл> … --repo <репо с graphify-out/> [--obnovit]

Сверка ПОСЛЕ работы агента: файлы из задания против реально изменённых в git.
Запуск:  python -I peresechenie.py sverka <задание.txt> --repo <путь> --ot <база> [--do HEAD]
Выход:   0 — всё в рамках задания · 1 — есть изменённое вне задания · 2 — ошибка запуска

Оглавление:
  1. Шаблоны  — какие файлы ищем, метки «НЕЛЬЗЯ:» / «НЕ ТРОГАЙ:»
  2. Пути     — нормализация и сравнение (полный путь или имя файла)
  3. Разбор   — текст задания → свои файлы и запретные
  4. Сводка   — группы «файл → задания» и пересечения
  5. Сверка   — «обещал / сделал»: git diff + status против файлов задания
  6. Карта    — graph.json Graphify: кто от кого зависит, поиск файла, свежесть, обновление
  7. Связи    — свои файлы заданий в карте: СТОП-СВЯЗЬ, через одного, документ; тесты
  8. Вывод    — таблица файлов, отчёт по карте, «кого задевает», «карта старше кода»
  9. Запуск   — аргументы, режимы, код выхода
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# ── 1. Шаблоны ────────────────────────────────────────────────────────
# Длинные расширения раньше коротких: csproj до cs, json до js.
EXTENSIONS = "csproj|cs|xaml|py|ps1|json|js|ts|vue|md|sql|sh"

FILE_RE = re.compile(
    r"(?:(?<!\w)[A-Za-z]:(?=[\\/]))?"         # диск C: — только если дальше слеш
    r"[\w./\\-]+\.(?:" + EXTENSIONS + r")"     # путь или имя с нужным расширением
    r"(?![\w-]|\.\w)",                         # не кусок длиннее: Foo.py.bak, Foo.csx
    re.IGNORECASE,                             # «Имя.cs:123», «Имя.cs ~123» → «Имя.cs» сами
)
FORBID_RE = re.compile(r"(?<!\w)(?:НЕЛЬЗЯ|НЕ\s+ТРОГАЙ)\s*:", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s")  # пункт списка под «НЕЛЬЗЯ:»


# ── 2. Пути ───────────────────────────────────────────────────────────
def norm_path(raw):
    """«src\\Core\\Foo.CS» → ('src', 'core', 'foo.cs'): слеши прямые, регистр не важен."""
    parts = [p for p in raw.replace("\\", "/").lower().split("/") if p not in ("", ".", "..")]
    return tuple(parts)


def same_file(a, b):
    """Один файл: пути равны или короткий — хвост длинного (имя без папки = имя)."""
    short, long_ = sorted((a, b), key=len)
    return long_[len(long_) - len(short):] == short


def find_files(text):
    """Все упомянутые файлы: {ключ-путь: как показать}."""
    found = {}
    for m in FILE_RE.finditer(text):
        shown = m.group().replace("\\", "/").lstrip("./")
        key = norm_path(shown)
        if key and not key[-1].startswith("."):
            found.setdefault(key, shown)
    return found


# ── 3. Разбор ─────────────────────────────────────────────────────────
def parse_task(text):
    """Текст задания → (свои, запретные). «НЕЛЬЗЯ: …» — до конца строки
    или списком пунктов ниже, если после двоеточия пусто."""
    mentioned, forbidden = {}, {}
    in_block = False
    for line in text.splitlines():
        if in_block and BULLET_RE.match(line):
            forbidden.update(find_files(line))
            continue
        in_block = False
        stop = FORBID_RE.search(line)
        if stop:
            tail = line[stop.end():]
            mentioned.update(find_files(line[:stop.start()]))
            forbidden.update(find_files(tail))
            in_block = not tail.strip()
        else:
            mentioned.update(find_files(line))
    own = {k: v for k, v in mentioned.items()
           if not any(same_file(k, f) for f in forbidden)}
    return own, forbidden


# ── 4. Сводка ─────────────────────────────────────────────────────────
def summarize(tasks):
    """tasks: [(имя, свои, запретные)] → строки [(файл, чьи, кому нельзя)].
    Упоминания одного файла склеиваем (union-find): «Foo.cs» и «src/Foo.cs» — одно."""
    entries = [(name, key, shown) for name, own, _ in tasks for key, shown in own.items()]
    parent = list(range(len(entries)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(entries)):
        for j in range(i):
            if same_file(entries[i][1], entries[j][1]):
                parent[root(i)] = root(j)

    groups = {}
    for i, entry in enumerate(entries):
        groups.setdefault(root(i), []).append(entry)

    rows = []
    for members in groups.values():
        keys = [key for _, key, _ in members]
        shown = max((s for _, _, s in members), key=len)
        owners = list(dict.fromkeys(name for name, _, _ in members))
        banned = [name for name, _, forb in tasks
                  if any(same_file(f, k) for f in forb for k in keys)]
        rows.append((shown, owners, banned))
    return sorted(rows, key=lambda r: r[0].lower())


# ── 5. Сверка ─────────────────────────────────────────────────────────
# Метки теста: «FooTests», «FooTest», «test_foo», «foo_test», «foo.spec» — регистр важен
# (иначе «Latest» сошёл бы за тест). Папки tests/test/__tests__ — тоже тест.
TEST_DIRS = {"tests", "test", "__tests__"}
TEST_MARK_RE = re.compile(r"^test_|(?:Tests?|[._]tests?|[._]spec)$")
TEST_WORD_RE = re.compile(r"тест|\btests?\b", re.IGNORECASE)   # слово «тест» в задании


def git_lines(repo, *args):
    """git в папке repo → список строк вывода (только чтение). Ошибка git → RuntimeError."""
    done = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip() or done.returncode}")
    return [line for line in done.stdout.split("\0" if "-z" in args else "\n") if line]


def changed_files(repo, base, head="HEAD"):
    """Изменённые: закоммиченное base..head + незакоммиченное (правки и новые файлы)."""
    files = dict.fromkeys(git_lines(repo, "diff", "--name-only", f"{base}..{head}"))
    entries = git_lines(repo, "--no-optional-locks", "status", "--porcelain", "-z", "-uall")
    skip_next = False                                    # после «R  новый» идёт «старый» путь
    for entry in entries:
        if skip_next:
            skip_next = False
            continue
        files[entry[3:]] = None
        skip_next = entry[0] in "RC"
    return list(files)


def file_stem(path):
    """«tests/FooTests.cs» → «FooTests»: имя без папки и расширения, регистр сохранён."""
    return path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]


def is_test_file(path):
    """Путь — тест: папка tests/… или метка в имени файла (регистр имени важен)."""
    folders = set(norm_path(path)[:-1])
    return bool(folders & TEST_DIRS) or bool(TEST_MARK_RE.search(file_stem(path)))


def test_is_near(path, named):
    """Тест рядом с названным файлом: та же папка или то же имя без метки теста
    («tests/FooTests.cs» ↔ «src/Foo.cs»). Чужой тест («OtherTests») — не рядом."""
    key = norm_path(path)
    core = TEST_MARK_RE.sub("", file_stem(path)).lower()
    for n in named:
        if core and core == n[-1].rsplit(".", 1)[0]:     # ключи уже в нижнем регистре
            return True
        if len(n) > 1 and n[:-1] == key[:-1]:
            return True
    return False


def sverka(text, changed):
    """Задание + изменённые пути → (вне задания, названы-но-не-тронуты, совпало)."""
    own, _ = parse_task(text)
    named = list(own)
    allow_tests = bool(TEST_WORD_RE.search(text))        # слово «тест» — тесты рядом разрешены
    outside, matched = [], set()
    for path in changed:
        key = norm_path(path)
        hits = [k for k in named if same_file(key, k)]
        if hits:
            matched.update(hits)
        elif not (allow_tests and is_test_file(path) and test_is_near(path, named)):
            outside.append(path)
    untouched = [own[k] for k in named if k not in matched]
    return sorted(outside, key=str.lower), sorted(untouched, key=str.lower), len(matched)


def cmd_sverka(args):
    try:
        text = Path(args.zadanie).read_text(encoding="utf-8-sig", errors="replace")
        changed = changed_files(args.repo, args.ot, args.do)
    except (OSError, RuntimeError) as e:
        print(f"ОШИБКА: {e}")
        return 2
    outside, untouched, matched = sverka(text, changed)
    if outside:
        print(f"вне задания ({len(outside)}) — изменены, но не названы:")
        for path in outside:
            print(f"  {path}")
    if untouched:
        print(f"названы, но не тронуты ({len(untouched)}) — для сведения:")
        for path in untouched:
            print(f"  {path}")
    print(f"совпало: {matched}")
    return 1 if outside else 0


# ── 6. Карта (Graphify) ───────────────────────────────────────────────
# graph.json читаем сами: `graphify affected` грузит карту заново на каждый файл
# (репо на 22 тыс. узлов: 33 с на файл), здесь одна загрузка на весь прогон (~2 с).
# Связи — те же, что обходит `graphify affected` (v0.9.97); «contains», «method»,
# «rationale_for» — устройство файла, а не зависимость. Узлы склеиваем в файлы:
# глубина 1 — файл прямо вызывает или импортирует, 2 — через один файл.
# Обход начинаем со ВСЕХ узлов файла, не только с узла-файла: вызов функции без импорта
# самого файла `graphify affected` не видит (на красном прогоне — «связей нет»).
# Документ (.md), который ссылается на код, от правки не ломается: обход через него дальше не идёт.
RELATIONS = frozenset({
    "calls", "indirect_call", "references", "imports", "imports_from", "dynamic_import",
    "re_exports", "inherits", "extends", "implements", "uses", "mixes_in", "embeds",
    "defines", "requires",
})
GRAPHIFY_ENV = {"GRAPHIFY_BACKEND": "none", "GRAPHIFY_NO_AUTO_REFRESH": "1", "GRAPHIFY_NO_TIPS": "1"}


@dataclass
class Karta:
    """Карта на уровне файлов: какие файлы вызывают или импортируют какой."""
    path: Path          # graphify-out/graph.json
    files: dict         # ключ-путь (norm_path) → путь как в карте
    users: dict         # путь → {пути файлов, которые от него зависят}
    docs: set           # пути документов: ссылаются на код, но от правки не ломаются


def load_karta(repo):
    """graphify-out/graph.json → Karta. Нет карты или чужой формат → RuntimeError."""
    path = Path(repo) / "graphify-out" / "graph.json"
    if not path.exists():
        raise RuntimeError(f"нет карты {path} — сначала graphify update . в папке репо")
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
        file_of = {n["id"]: n["source_file"] for n in graph["nodes"] if n.get("source_file")}
        docs = {n["source_file"] for n in graph["nodes"]
                if n.get("file_type") == "document" and n.get("source_file")}
        links = graph["links"] if "links" in graph else graph["edges"]
        edges = [(e["source"], e["target"]) for e in links if e.get("relation") in RELATIONS]
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise RuntimeError(f"карта {path} не в том формате ({e!r}) — graphify сменил формат?") from e
    if not file_of:                                      # пустая карта — проверки не было, не «чисто»
        raise RuntimeError(f"карта {path} пустая — graphify update . в папке репо")
    users = {}
    for src, dst in edges:
        user, used = file_of.get(src), file_of.get(dst)
        if user and used and user != used:
            users.setdefault(used, set()).add(user)
    return Karta(path, {norm_path(f): f for f in file_of.values()}, users, docs)


def fajlov(n):
    """1 файл · 2 файла · 5 файлов."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} файл"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} файла"
    return f"{n} файлов"


def find_in_karta(karta, shown):
    """Файл из задания → (путь в карте, None) или (None, почему не нашли). Не угадываем:
    голое имя, которое носят несколько файлов (и config.py в корне, и sub/config.py), — «дай путь»."""
    key = norm_path(shown)
    if len(key) > 1 and key in karta.files:              # путь от корня репо — не догадка
        return karta.files[key], None
    hits = [path for k, path in karta.files.items() if same_file(key, k)]
    if len(hits) == 1:
        return hits[0], None
    if hits:
        return None, f"имя неоднозначно ({fajlov(len(hits))} в карте) — дай путь"
    return None, "нет в карте"


def zadeto(karta, paths, depth=2):
    """Кого задевает правка файлов: {путь: (глубина, через какой файл)} — обход назад."""
    seen = {p: (0, None) for p in paths}
    layer = sorted(paths)
    for d in range(1, depth + 1):
        next_layer = []
        for path in layer:
            if path in karta.docs:                       # от документа код не зависит
                continue
            for user in sorted(karta.users.get(path, ())):
                if user not in seen:
                    seen[user] = (d, path if d > 1 else None)
                    next_layer.append(user)
        layer = next_layer
    return {p: hit for p, hit in seen.items() if hit[0]}


def changed_after(karta, repo):
    """Файлы карты, правленные после её сборки, — про их связи карта отстала.
    Удалённые не считаем: задание их не возьмёт, лишняя связь к ним не мешает.
    Правку во время самой сборки не видно: graph.json пишется в конце (большой репо — минуты)."""
    built = karta.path.stat().st_mtime + 2               # запас на округление времени файлов
    late = []
    for path in sorted(karta.files.values()):
        try:
            if (Path(repo) / path).stat().st_mtime > built:
                late.append(path)
        except OSError:
            pass
    return late


def graphify_exe():
    """Где graphify: PATH или ~/.local/bin (uv tool install)."""
    found = shutil.which("graphify")
    local = Path.home() / ".local" / "bin" / ("graphify.exe" if os.name == "nt" else "graphify")
    return found or (str(local) if local.exists() else None)


def obnovit_kartu(repo):
    """graphify update: только разбор кода, без ИИ (большой репо — минуты). Сбой → RuntimeError."""
    exe = graphify_exe()
    if not exe:
        raise RuntimeError("graphify не найден (uv tool install graphifyy)")
    done = subprocess.run([exe, "update", "."], cwd=repo, env={**os.environ, **GRAPHIFY_ENV},
                          capture_output=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        tail = (done.stderr or done.stdout).strip().splitlines()[-1:]
        raise RuntimeError(f"graphify update: {tail[0] if tail else done.returncode}")


def open_karta(repo, obnovit):
    """Карта репо; с obnovit — сначала graphify update (сбой — сказать и взять старую)."""
    if obnovit:
        try:
            obnovit_kartu(repo)
        except (RuntimeError, OSError, subprocess.SubprocessError) as e:
            print(f"карта: обновить не вышло — {e}; проверяю по старой")
    return load_karta(repo)


# ── 7. Связи заданий ──────────────────────────────────────────────────
# Документ (.md), который ссылается на код, — «сверить текст», не СТОП: в большом репо
# описания разделов ссылаются на функции, и без этого шумели бы в СТОП на каждой правке.
LINK_TEXT = {                                            # порядок — порядок вывода
    "stop":   "СТОП-СВЯЗЬ: правка «{name}» задевает {path} из «{other}» — один агент или по очереди",
    "cherez": "  через одного: правка «{name}» задевает {path} из «{other}» (через {via}) — сказать обоим",
    "doc":    "  документ: {path} из «{other}» ссылается на код «{name}» — сверить текст после правки",
}
NE_GARANTIYA = ("  не гарантия: общие ключи JSON, поля данных и маршруты-строки карта не видит"
                " — для них grep по точному имени")


def place_tasks(tasks, karta):
    """Свои файлы заданий → места в карте: ({задание: {пути}}, пометки о ненайденных,
    {расширение вне карты: сколько файлов})."""
    known_ext = {Path(p).suffix.lower() for p in karta.files.values()}
    owned, notes, unseen = {}, [], {}
    for name, own, _ in tasks:
        owned[name] = set()
        for shown in own.values():
            ext = Path(shown).suffix.lower()
            if ext not in known_ext:                     # такие файлы карта не разбирает вовсе
                unseen[ext] = unseen.get(ext, 0) + 1
                continue
            path, why = find_in_karta(karta, shown)
            if path:
                owned[name].add(path)
            else:
                notes.append(f"  {name}: {shown} — {why}")
    return owned, notes, unseen


def link_kind(karta, path, depth):
    """Какая связь: документ — «doc», прямой вызов/импорт — «stop», через файл — «cherez»."""
    if path in karta.docs:
        return "doc"
    return "stop" if depth == 1 else "cherez"


def links_between(owned, karta):
    """Связи заданий [{kind, name, path, other, via}] в порядке LINK_TEXT;
    тесты {задание: [пути]}, которые задевает его правка."""
    links, tests = [], {}
    for name, paths in owned.items():
        reach = zadeto(karta, paths)
        tests[name] = sorted(p for p in reach if is_test_file(p) and p not in karta.docs)
        for other, theirs in owned.items():
            for path in sorted(theirs & reach.keys()) if other != name else ():
                depth, via = reach[path]
                links.append({"kind": link_kind(karta, path, depth), "name": name,
                              "path": path, "other": other, "via": via})
    order = list(LINK_TEXT)
    return sorted(links, key=lambda link: order.index(link["kind"])), tests


# ── 8. Вывод ──────────────────────────────────────────────────────────
def short_list(items, limit=8):
    """«a, b» · «a, b, … ещё 5» · пусто — «—»."""
    if not items:
        return "—"
    head = ", ".join(items[:limit])
    return head if len(items) <= limit else f"{head}, … ещё {len(items) - limit}"


def print_files(rows):
    """Таблица «файл → задания» и СТОП на общих файлах → есть ли общие."""
    width = max((len(shown) for shown, _, _ in rows), default=0)
    print("файл → задания")
    if not rows:
        print("  (файлов в заданиях не найдено)")
    for shown, owners, banned in rows:
        note = f"   (нельзя: {', '.join(banned)})" if banned else ""
        print(f"  {shown.ljust(width)} → {', '.join(owners)}{note}")
    clashes = [(shown, owners) for shown, owners, _ in rows if len(owners) > 1]
    for shown, owners in clashes:
        print(f"СТОП: {shown} — {', '.join(owners)}")
    if not clashes:
        print("пересечений нет")
    return bool(clashes)


def print_staleness(karta, repo):
    late = changed_after(karta, repo)
    if late:
        print(f"  карта старше кода: после неё правили {fajlov(len(late))} ({short_list(late, 3)})"
              f" — обнови: graphify update . в папке репо (большой репо — минуты) или флаг --obnovit")


def report_karta(tasks, repo, obnovit):
    """Скрытые связи заданий по карте → печать; True — есть прямая (СТОП-СВЯЗЬ)."""
    karta = open_karta(repo, obnovit)
    owned, notes, unseen = place_tasks(tasks, karta)
    links, tests = links_between(owned, karta)
    print(f"карта кода ({fajlov(len(karta.files))}):")
    for link in links:
        print(LINK_TEXT[link["kind"]].format(**link))
    for line in notes:
        print(line)
    if unseen:
        print(f"  карта не видит: {', '.join(sorted(unseen))} — для них только сверка имён выше")
    direct = any(link["kind"] == "stop" for link in links)
    unchecked = len(notes) + sum(unseen.values())       # «связей нет» — только про проверенное
    if not direct and unchecked:
        print(f"  прямых связей среди найденных в карте нет; не проверено файлов: {unchecked} (выше)")
    elif not direct:
        print("  прямых связей между заданиями нет")
    for name, files in tests.items():
        if files:
            print(f"  тесты для «{name}» ({len(files)}): {short_list(files)}")
    print_staleness(karta, repo)
    print(NE_GARANTIYA)
    return direct


def print_reach(karta, path):
    """Кого задевает правка одного файла: код напрямую и через одного, тесты, документы."""
    reach = zadeto(karta, {path})
    code = {p: depth for p, (depth, _) in reach.items() if p not in karta.docs}
    groups = [
        ("напрямую", sorted(p for p, depth in code.items() if depth == 1)),
        ("через одного", sorted(p for p, depth in code.items() if depth == 2)),
        ("тесты", sorted(p for p in code if is_test_file(p))),
        ("документы", sorted(p for p in reach if p in karta.docs)),
    ]
    print(f"{path} — правка задевает:")
    for title, files in groups:
        print(f"  {title} ({len(files)}): {short_list(files, 30)}")


# ── 9. Запуск ─────────────────────────────────────────────────────────
USAGE = """запуск: python peresechenie.py <задание1> <задание2> …  («-» — из stdin) [--graphify <репо> [--obnovit]]
        python peresechenie.py zadeto <файл> … --repo <репо> [--obnovit]
        python peresechenie.py sverka <задание> --repo <путь> --ot <база> [--do HEAD]"""


def read_task(arg):
    """Аргумент → (имя, текст). «-» — stdin, иначе файл; имя — без расширения."""
    if arg == "-":
        return "stdin", sys.stdin.buffer.read().decode("utf-8-sig", "replace")
    path = Path(arg)
    return path.stem, path.read_text(encoding="utf-8-sig", errors="replace")


def load_tasks(args):
    """Аргументы → [(имя, свои, запретные)]; одинаковые имена из разных папок — «имя#2»."""
    tasks, used = [], set()
    for arg in args:
        name, text = read_task(arg)
        base, n = name, 1
        while name in used:
            n += 1
            name = f"{base}#{n}"
        used.add(name)
        tasks.append((name, *parse_task(text)))
    return tasks


def cmd_zadeto(args):
    """Нижний конец дерева: кого задевает правка файлов — напрямую, через одного, тесты."""
    try:
        karta = open_karta(args.repo, args.obnovit)
    except (RuntimeError, OSError) as e:
        print(f"карта: НЕ ЗНАЮ — {e}")
        return 2
    code, shown_paths = 0, set()
    for shown in args.faily:
        path, why = find_in_karta(karta, shown)
        if not path:
            print(f"{shown} — {why}")
            code = 2
        elif path not in shown_paths:                    # «sklad.py» и «app/sklad.py» — один раз
            shown_paths.add(path)
            print_reach(karta, path)
    print_staleness(karta, args.repo)
    print(NE_GARANTIYA)
    return code


def build_sverka_parser():
    p = argparse.ArgumentParser(prog="peresechenie.py sverka",
                                description="файлы из задания против изменённых в git")
    p.add_argument("zadanie", help="файл с текстом задания")
    p.add_argument("--repo", required=True, help="путь к репозиторию")
    p.add_argument("--ot", required=True, help="база: коммит/ветка, от которой считать")
    p.add_argument("--do", default="HEAD", help="до чего считать (по умолчанию HEAD)")
    p.set_defaults(run=cmd_sverka)
    return p


def build_zadeto_parser():
    p = argparse.ArgumentParser(prog="peresechenie.py zadeto",
                                description="кого задевает правка файлов — по карте graphify")
    p.add_argument("faily", nargs="+", help="файлы: путь от корня репо или имя")
    p.add_argument("--repo", required=True, help="репо с graphify-out/")
    p.add_argument("--obnovit", action="store_true", help="сначала graphify update (большой репо — минуты)")
    p.set_defaults(run=cmd_zadeto)
    return p


def build_main_parser():
    p = argparse.ArgumentParser(prog="peresechenie.py", usage=USAGE,
                                description="пересечение файлов между заданиями агентов")
    p.add_argument("zadaniya", nargs="*", help="файлы заданий («-» — одно из stdin)")
    p.add_argument("--graphify", metavar="РЕПО", help="репо с graphify-out/: скрытые связи по карте")
    p.add_argument("--obnovit", action="store_true", help="сначала graphify update (большой репо — минуты)")
    return p


SUBCOMMANDS = {"sverka": build_sverka_parser, "zadeto": build_zadeto_parser}


def main(argv):
    if argv and argv[0] in SUBCOMMANDS:                  # «после работы агента» · «кого задевает»
        args = SUBCOMMANDS[argv[0]]().parse_args(argv[1:])
        return args.run(args)
    args = build_main_parser().parse_intermixed_args(argv)
    if not args.zadaniya or (args.obnovit and not args.graphify):
        print(USAGE)
        return 2
    try:
        tasks = load_tasks(args.zadaniya)
    except OSError as e:
        print(f"не прочитать задание: {e}")
        return 2

    clashes = print_files(summarize(tasks))
    direct = False
    if args.graphify:
        try:
            direct = report_karta(tasks, args.graphify, args.obnovit)
        except (RuntimeError, OSError) as e:
            print(f"карта: НЕ ЗНАЮ — {e}")
            return 2
    return 1 if clashes or direct else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
