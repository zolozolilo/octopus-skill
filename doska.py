#!/usr/bin/env python3
"""Доска осьминога: дерево задач в derevo.json и страница doska.html (локально, без сети).

Запуск (из этой папки):
  python -I doska.py derevo <id> "<название>"
  python -I doska.py ubrat <id>
  python -I doska.py list <id> <ждёт|идёт|готово|сломано> [--v <родитель>] [--zadacha "…"]
                          [--kto "агент E|я|скрипт"] [--zametka "…"] [--bez-vremeni]
  python -I doska.py pokaz
Выход:   0 — готово · 1 — отказ (нет такого дерева/листа, занятый id…) · 2 — ошибка записи
После КАЖДОЙ команды страница doska.html пересобирается; в браузере она обновляется сама (раз в 10 с).

Данные лежат в doska/derevo.json: {"derevya": [{"id", "nazvanie", "listya": [лист, …]}]}.
Лист: id, v (родитель: id другого листа, у корневого пусто), status, zadacha, kto, nachato, gotovo, zametka.
Время — локальное, «ГГГГ-ММ-ДДTЧЧ:ММ:СС»; неизвестное — пустая строка, не выдумываем.
id листа и id дерева — в одном пространстве: двух одинаковых быть не может.

Оглавление:
  1. Данные   — путь, чтение, атомарная запись
  2. Время    — «сейчас» и правила проставления времени
  3. Дерево   — создать/убрать дерево, создать/обновить лист
  4. Страница — HTML: шапка с осьминогом, карточки деревьев
  5. Консоль  — сводка «pokaz»
  6. Команды  — derevo, ubrat, list, pokaz
  7. Запуск   — аргументы, код выхода
"""
import argparse
import html
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


# ── 1. Данные ─────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent / "doska"        # тесты подменяют на tmp_path
JSON_NAME, HTML_NAME = "derevo.json", "doska.html"

WAIT, GO, DONE, BROKEN = "ждёт", "идёт", "готово", "сломано"
STATUSES = (WAIT, GO, DONE, BROKEN)
ICONS = {WAIT: "·", GO: "⏳", DONE: "✔", BROKEN: "✘"}       # значки для консоли
TENTACLES = 8                                               # сколько агентов тянет осьминог


def load():
    """derevo.json → словарь; нет файла — пустая доска."""
    path = DATA_DIR / JSON_NAME
    if not path.exists():
        return {"derevya": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic(path, payload):
    """Записать bytes в path через временный файл рядом + os.replace.
    Живой файл никогда не открываем на запись: упали посередине — старый цел."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(5):                            # Windows: браузер мог читать файл в эту секунду
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.2)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save(data):
    """Сначала кодируем ОБА файла (ошибка кодирования — ничего не тронуто), потом пишем."""
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    html_bytes = render_html(data).encode("utf-8")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_atomic(DATA_DIR / JSON_NAME, json_bytes)
    write_atomic(DATA_DIR / HTML_NAME, html_bytes)


# ── 2. Время ──────────────────────────────────────────────────────────
def now():
    """Сейчас, локально, до секунды (тесты подменяют)."""
    return datetime.now().replace(microsecond=0).isoformat()


def stamp_times(leaf, old_status, new_status):
    """Время ставится само и один раз: «идёт» → nachato (если пусто), «готово/сломано» → gotovo (если пусто).
    Возврат в «ждёт/идёт» снимает gotovo — иначе новый заход показывал бы старый конец."""
    if new_status == old_status:
        return
    if new_status in (WAIT, GO):
        leaf["gotovo"] = ""
    if new_status == GO and not leaf["nachato"]:
        leaf["nachato"] = now()
    if new_status in (DONE, BROKEN) and not leaf["gotovo"]:
        leaf["gotovo"] = now()


# ── 3. Дерево ─────────────────────────────────────────────────────────
def find_tree(data, tid):
    return next((t for t in data["derevya"] if t["id"] == tid), None)


def find_leaf(data, lid):
    """(дерево, лист) по id листа или (None, None)."""
    for t in data["derevya"]:
        for leaf in t["listya"]:
            if leaf["id"] == lid:
                return t, leaf
    return None, None


def id_taken(data, some_id):
    return find_tree(data, some_id) is not None or find_leaf(data, some_id)[0] is not None


def add_tree(data, tid, name):
    if id_taken(data, tid):
        raise ValueError(f"id «{tid}» уже занят")
    data["derevya"].append({"id": tid, "nazvanie": name, "listya": []})


def remove_tree(data, tid):
    tree = find_tree(data, tid)
    if tree is None:
        raise ValueError(f"нет дерева «{tid}»")
    data["derevya"].remove(tree)


def resolve_parent(data, parent):
    """Родитель — id дерева или листа → (дерево, id родителя-листа или '' для корня)."""
    tree = find_tree(data, parent)
    if tree is not None:
        return tree, ""
    tree, leaf = find_leaf(data, parent)
    if tree is None:
        raise ValueError(f"нет такого родителя «{parent}» (ни дерева, ни листа)")
    return tree, leaf["id"]


def is_descendant(tree, leaf_id, maybe_child_id):
    """maybe_child_id — это leaf_id или его потомок? (защита от цикла при смене родителя)"""
    cur = maybe_child_id
    while cur:
        if cur == leaf_id:
            return True
        cur = next((x["v"] for x in tree["listya"] if x["id"] == cur), "")
    return False


def set_leaf(data, lid, status, v=None, zadacha=None, kto=None, zametka=None, bez_vremeni=False):
    """Создать лист (нужны v и zadacha) или обновить; поля, которых не дали, не трогаем."""
    if status not in STATUSES:
        raise ValueError(f"статус «{status}»: бывает {' | '.join(STATUSES)}")
    tree, leaf = find_leaf(data, lid)
    if leaf is None:
        if find_tree(data, lid) is not None:
            raise ValueError(f"id «{lid}» — это дерево, а не лист")
        if not v or not zadacha:
            raise ValueError('новому листу нужны --v <родитель> и --zadacha "…"')
        tree, parent_leaf = resolve_parent(data, v)
        leaf = {"id": lid, "v": parent_leaf, "status": WAIT, "zadacha": zadacha, "kto": "",
                "nachato": "", "gotovo": "", "zametka": ""}
        tree["listya"].append(leaf)
    elif v is not None:
        new_tree, parent_leaf = resolve_parent(data, v)
        if new_tree is not tree:
            raise ValueError("лист нельзя перенести в другое дерево")
        if is_descendant(tree, lid, parent_leaf):
            raise ValueError("родитель не может быть самим листом или его потомком")
        leaf["v"] = parent_leaf
    old = leaf["status"]
    if zadacha is not None:
        leaf["zadacha"] = zadacha
    if kto is not None:
        leaf["kto"] = kto
    if zametka is not None:
        leaf["zametka"] = zametka
    if not bez_vremeni:
        stamp_times(leaf, old, status)
    leaf["status"] = status
    return leaf


def ordered(tree):
    """Листья дерева в порядке показа (обход вглубь) → [(лист, глубина, последний_ли_среди_соседей)]."""
    kids = {}
    for leaf in tree["listya"]:
        kids.setdefault(leaf["v"], []).append(leaf)
    out = []

    def walk(parent, depth):
        group = kids.get(parent, [])
        for i, leaf in enumerate(group):
            out.append((leaf, depth, i == len(group) - 1))
            walk(leaf["id"], depth + 1)

    walk("", 0)
    return out


def totals(data):
    """Сводка по всем деревьям: занято щупалец (агенты со статусом «идёт»), ✔, ⏳, ✘, ждут."""
    leaves = [leaf for t in data["derevya"] for leaf in t["listya"]]

    def count(st):
        return sum(1 for x in leaves if x["status"] == st)

    busy = sum(1 for x in leaves if x["status"] == GO and "агент" in x["kto"].lower())
    return {"busy": busy, "done": count(DONE), "go": count(GO),
            "broken": count(BROKEN), "wait": count(WAIT)}


# ── 4. Страница ───────────────────────────────────────────────────────
# Осьминог — из SKILL.md этой папки (заставка).
OCTOPUS = r"""  .  '  *                       *  '  .
   _____          _____          _____
  / * * \        /     \        / * * \
 /* * * *\      | o   o |      /* * * *\
 \_______/      |  \_/  |      \_______/
    | |          \_____/          | |
    | |~~~~~~~~~~/|||||\~~~~~~~~~~| |
 '  | |  .      ~ ~ ~ ~ ~      .  | |  '
  ' | | .                       . | | '
-----------------------------------------"""

PAGE_CSS = """
:root {
  --bg: #f6f5f1; --card: #ffffff; --line: #e3e0d8; --text: #23211d; --muted: #8a867c;
  --ok: #1d7a3e; --bad: #c0302c; --live: #b9770e; --art: #a9a498;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15161a; --card: #1e2025; --line: #2e3037; --text: #e8e6e1; --muted: #8b8e97;
    --ok: #5fcf86; --bad: #ff7a73; --live: #f0b75a; --art: #5b5e68;
  }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--text);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 980px; margin: 0 auto; }
header { margin-bottom: 18px; }
pre.art { margin: 0 0 6px; color: var(--art); font: 10px/1.15 ui-monospace, Consolas, monospace; }
h1 { margin: 0 0 4px; font-size: 1.5rem; }
.sum { margin: 0; color: var(--muted); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
  padding: 12px 14px; margin-bottom: 14px; }
.card h2 { margin: 0 0 8px; font-size: 1.05rem; }
.card h2 small { color: var(--muted); font-weight: 400; }
.row { display: grid; grid-template-columns: 1.4rem minmax(0, 1fr) 7rem 3.2rem 4.2rem;
  gap: 0 10px; align-items: baseline; padding: 4px 0; border-top: 1px solid var(--line); }
.row:first-of-type { border-top: 0; }
.ic { text-align: center; font-weight: 700; }
.task { padding-left: calc(var(--d) * 1.2rem); overflow-wrap: anywhere; }
.zam { color: var(--muted); font-size: .85em; }
.kto, .t, .min { color: var(--muted); font-size: .88em; white-space: nowrap; }
.min { text-align: right; }
.done .ic { color: var(--ok); }
.broken, .broken .kto, .broken .t, .broken .min, .broken .zam { color: var(--bad); }
.wait .task, .wait .ic { color: var(--muted); }
.dot { display: inline-block; width: .7em; height: .7em; border-radius: 50%; background: var(--live); }
@media (prefers-reduced-motion: no-preference) {
  .dot { animation: puls 1.4s ease-in-out infinite; }
  @keyframes puls { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .35; transform: scale(.7); } }
}
.empty { color: var(--muted); }
@media (max-width: 640px) {
  .zam, .kto { display: none; }
  .row { grid-template-columns: 1.4rem minmax(0, 1fr) 3.2rem 4.2rem; }
}
"""

# Минуты считает страница: у «идёт» — от nachato до сейчас, у готовых — от nachato до gotovo.
PAGE_JS = """
(function () {
  var d = JSON.parse(document.getElementById('dannye').textContent), by = {};
  d.derevya.forEach(function (t) { t.listya.forEach(function (x) { by[t.id + '/' + x.id] = x; }); });
  document.querySelectorAll('.min[data-k]').forEach(function (el) {
    var x = by[el.getAttribute('data-k')];
    if (!x || !x.nachato) return;
    var a = new Date(x.nachato).getTime();
    var b = x.status === 'идёт' ? Date.now() : (x.gotovo ? new Date(x.gotovo).getTime() : NaN);
    if (!isNaN(a) && !isNaN(b)) el.textContent = Math.max(0, Math.round((b - a) / 60000)) + ' мин';
  });
})();
"""


def esc(text):
    return html.escape(str(text), quote=True)


def hhmm(iso):
    """'2026-10-24T01:05:09' → '01:05'; пусто/мусор → ''."""
    return iso[11:16] if len(iso) >= 16 else ""


def render_row(tree, leaf, depth):
    st = leaf["status"]
    if st == GO:
        icon = '<span class="dot" role="img" aria-label="идёт"></span>'
    else:
        icon = f'<span role="img" aria-label="{esc(st)}">{ICONS[st]}</span>'
    css = {WAIT: "wait", GO: "go", DONE: "done", BROKEN: "broken"}[st]
    note = f'<div class="zam">{esc(leaf["zametka"])}</div>' if leaf["zametka"] else ""
    key = esc(tree["id"] + "/" + leaf["id"])
    return (f'<div class="row {css}" style="--d:{depth}" title="{esc(st)}">'
            f'<span class="ic">{icon}</span>'
            f'<span class="task">{esc(leaf["zadacha"])}{note}</span>'
            f'<span class="kto">{esc(leaf["kto"])}</span>'
            f'<span class="t">{esc(hhmm(leaf["nachato"]))}</span>'
            f'<span class="min" data-k="{key}"></span></div>')


def render_card(tree):
    rows = "".join(render_row(tree, leaf, depth) for leaf, depth, _ in ordered(tree))
    body = rows or '<div class="empty">листьев пока нет</div>'
    return (f'<section class="card"><h2>{esc(tree["nazvanie"])} <small>{esc(tree["id"])}</small></h2>'
            f'{body}</section>')


def render_html(data):
    """Вся страница одним файлом: без внешних ссылок, данные встроены JSON'ом."""
    s = totals(data)
    summary = (f"щупалец занято {s['busy']} из {TENTACLES} (агенты со статусом идёт) · ✔ {s['done']} · "
               f"⏳ {s['go']} · ✘ {s['broken']} · ждут {s['wait']} · обновлено {hhmm(now())}")
    cards = "".join(render_card(t) for t in data["derevya"]) or '<p class="empty">деревьев пока нет</p>'
    # «<» в JSON заменяем: иначе «</script>» в тексте задачи закрыл бы тег с данными
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return (f'<!doctype html>\n<html lang="ru"><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="10">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="color-scheme" content="light dark">'
            f'<title>Доска осьминога</title><style>{PAGE_CSS}</style></head><body><main>'
            f'<header><pre class="art" aria-hidden="true">{esc(OCTOPUS)}</pre>'
            f'<h1>Доска осьминога</h1><p class="sum">{esc(summary)}</p></header>'
            f'{cards}</main>'
            f'<script type="application/json" id="dannye">{blob}</script>'
            f'<script>{PAGE_JS}</script></body></html>\n')


# ── 5. Консоль ────────────────────────────────────────────────────────
def render_pokaz(data):
    """Сводка деревом, как статус в SKILL.md: ✔ ⏳ ✘ ·"""
    lines = []
    for tree in data["derevya"]:
        lines.append(f"{tree['nazvanie']}  [{tree['id']}]")
        guides = []                                          # по уровням: «последний ли» среди соседей
        for leaf, depth, last in ordered(tree):
            guides = guides[:depth] + [last]
            prefix = "".join("   " if g else "│  " for g in guides[:-1]) + ("└─ " if last else "├─ ")
            who = f" ({leaf['kto']})" if leaf["kto"] else ""
            lines.append(f"{prefix}{ICONS[leaf['status']]} {leaf['id']}  {leaf['zadacha']}{who}")
    return "\n".join(lines) if lines else "доска пуста"


# ── 6. Команды ────────────────────────────────────────────────────────
def cmd_derevo(args):
    data = load()
    add_tree(data, args.id, args.nazvanie)
    save(data)
    print(f"дерево «{args.id}» создано")
    return 0


def cmd_ubrat(args):
    data = load()
    remove_tree(data, args.id)
    save(data)
    print(f"дерево «{args.id}» убрано")
    return 0


def cmd_list(args):
    data = load()
    leaf = set_leaf(data, args.id, args.status, v=args.v, zadacha=args.zadacha, kto=args.kto,
                    zametka=args.zametka, bez_vremeni=args.bez_vremeni)
    save(data)
    print(f"{ICONS[leaf['status']]} {leaf['id']}  {leaf['zadacha']}")
    return 0


def cmd_pokaz(args):
    print(render_pokaz(load()))
    return 0


# ── 7. Запуск ─────────────────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(prog="doska.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("derevo", help="новое дерево (корень)")
    sp.add_argument("id")
    sp.add_argument("nazvanie")
    sp.set_defaults(run=cmd_derevo)

    sp = sub.add_parser("ubrat", help="убрать дерево целиком")
    sp.add_argument("id")
    sp.set_defaults(run=cmd_ubrat)

    sp = sub.add_parser("list", help="создать или обновить лист")
    sp.add_argument("id")
    sp.add_argument("status", choices=STATUSES)
    sp.add_argument("--v", help="родитель: id дерева или листа (при создании обязательно)")
    sp.add_argument("--zadacha")
    sp.add_argument("--kto")
    sp.add_argument("--zametka")
    sp.add_argument("--bez-vremeni", action="store_true", help="не ставить время (для посева старых листов)")
    sp.set_defaults(run=cmd_list)

    sp = sub.add_parser("pokaz", help="сводка деревом в консоль")
    sp.set_defaults(run=cmd_pokaz)
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except ValueError as e:
        print(f"ОТКАЗ: {e}")
        return 1
    except OSError as e:
        print(f"ОШИБКА записи: {e}")
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
