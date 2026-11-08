#!/usr/bin/env python3
"""Папки агентов (git worktree): создать одной командой и безопасно убрать слитые.

Запуск:
  python -I papki.py spisok --repo <путь>
  python -I papki.py ubrat  --repo <путь> [--baza master] [--svezhee-chasov 12] [--da]
  python -I papki.py novaya --repo <путь> --put <папка> --vetka <имя> [--ot master]
Выход:   0 — всё хорошо · 1 — на какой-то папке ошибка / отказ · 2 — ошибка запуска

Без --da «ubrat» только печатает, что убрал бы, и ничего не трогает.

Оглавление:
  1. Git      — вызов git и разбор «git worktree list --porcelain»
  2. Проверки — чистая ли папка, слита ли, когда её трогали в последний раз
  3. Разбор   — состояние каждой папки и что с ней будет
  4. Команды  — spisok, ubrat, novaya
  5. Запуск   — аргументы, код выхода
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path


# ── 1. Git ────────────────────────────────────────────────────────────
def git(repo, *args):
    """git в папке repo → (код выхода, вывод). Список аргументов, UTF-8, без кавычек вокруг кириллицы."""
    done = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    return done.returncode, (done.stdout + done.stderr).strip()


def read_worktrees(repo):
    """«git worktree list --porcelain» → [{'path', 'branch', 'locked', 'prunable'}].
    Первая запись — главная папка."""
    code, out = git(repo, "worktree", "list", "--porcelain")
    if code != 0:
        raise RuntimeError(f"не прочитать список папок: {out}")
    trees, cur = [], None
    for line in out.splitlines() + [""]:
        if not line.strip():                       # пустая строка — конец записи
            if cur:
                trees.append(cur)
            cur = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            cur = {"path": Path(value), "branch": None, "locked": False, "prunable": False}
        elif cur is not None and key == "branch":
            cur["branch"] = value.removeprefix("refs/heads/")
        elif cur is not None and key in ("locked", "prunable"):
            cur[key] = True
    return trees


# ── 2. Проверки ───────────────────────────────────────────────────────
def is_clean(wt):
    """Чистая: ни правок, ни новых файлов. Игнорируемые (bin/obj) git сам не показывает.
    --no-optional-locks — чтобы проверка не переписала index и не «освежила» папку."""
    code, out = git(wt, "--no-optional-locks", "status", "--porcelain")
    return code == 0 and not out, (None if code == 0 else out)


def is_merged(repo, wt, base):
    """HEAD папки — предок базы? True / False; ошибка git (нет базы) → RuntimeError."""
    code, head = git(wt, "rev-parse", "HEAD")
    if code != 0:
        raise RuntimeError(f"нет HEAD: {head}")
    code, out = git(repo, "merge-base", "--is-ancestor", head, base)
    if code in (0, 1):
        return code == 0
    raise RuntimeError(f"не сверить с «{base}»: {out}")


def gitdir_of(wt):
    """Служебная папка worktree — путь из файла .git внутри неё («gitdir: …»)."""
    text = (wt / ".git").read_text(encoding="utf-8", errors="replace")
    line = text.strip().splitlines()[0]
    path = Path(line.removeprefix("gitdir:").strip())
    return path if path.is_absolute() else (wt / path).resolve()


def last_touched(wt):
    """Когда папку трогали в последний раз: max mtime файлов HEAD, index, logs/HEAD в её gitdir."""
    gd = gitdir_of(wt)
    times = [(gd / name).stat().st_mtime
             for name in ("HEAD", "index", "logs/HEAD") if (gd / name).exists()]
    return max(times) if times else gd.stat().st_mtime


# ── 3. Разбор ─────────────────────────────────────────────────────────
# Состояния; «уберу» ставим только слитой / несуществующей папке.
MAIN, LOCKED, DIRTY, UNMERGED, FRESH, MERGED, GONE, ERROR = (
    "главная", "заперта", "грязная", "не слита", "свежая", "слита", "нет каталога", "ошибка проверки")


def inspect(repo, tree, base, fresh_hours, is_main):
    """Одна папка → словарь: path, branch, state, note, remove (bool), prune_only (bool)."""
    row = {"path": tree["path"], "branch": tree["branch"], "state": None,
           "note": "", "remove": False, "prune_only": False}

    def done(state, note="", remove=False, prune_only=False):
        row.update(state=state, note=note, remove=remove, prune_only=prune_only)
        return row

    if is_main:
        return done(MAIN)
    if tree["locked"]:
        return done(LOCKED)
    if tree["prunable"] or not tree["path"].exists():
        return done(GONE, "только prune", prune_only=True)
    try:
        touched = last_touched(tree["path"])                 # до status: тот не должен влиять
        clean, err = is_clean(tree["path"])
        if err is not None:
            return done(ERROR, err.splitlines()[0] if err else "status")
        if not clean:
            return done(DIRTY)
        if not is_merged(repo, tree["path"], base):
            return done(UNMERGED)
    except (RuntimeError, OSError) as e:
        return done(ERROR, str(e).splitlines()[0] if str(e) else "?")
    hours = (time.time() - touched) / 3600
    if hours < fresh_hours:
        return done(FRESH, f"трогали {hours:.1f} ч назад")
    return done(MERGED, f"не трогали {hours:.0f} ч", remove=True)


def inspect_all(repo, base, fresh_hours):
    trees = read_worktrees(repo)
    return [inspect(repo, t, base, fresh_hours, i == 0) for i, t in enumerate(trees)]


def verdict(row):
    """Что будет с папкой — одним словом для таблицы."""
    if row["prune_only"]:
        return "prune"
    return "уберу" if row["remove"] else "оставлю"


def count_left(rows):
    """Оставленные по причинам: 'грязная 2, свежая 1'."""
    counts = {}
    for r in rows:
        if not r["remove"] and not r["prune_only"]:
            counts[r["state"]] = counts.get(r["state"], 0) + 1
    return ", ".join(f"{k} {v}" for k, v in counts.items()) or "нет"


# ── 4. Команды ────────────────────────────────────────────────────────
def cmd_spisok(args):
    rows = inspect_all(args.repo, args.baza, args.svezhee_chasov)
    table = [("путь", "ветка", "состояние", "что будет")]
    for r in rows:
        state = r["state"] + (f" ({r['note']})" if r["note"] else "")
        table.append((str(r["path"]), r["branch"] or "detached", state, verdict(r)))
    widths = [max(len(line[i]) for line in table) for i in range(4)]
    for line in table:
        print("  ".join(cell.ljust(w) for cell, w in zip(line, widths)).rstrip())
    return 0


def cmd_ubrat(args):
    rows = inspect_all(args.repo, args.baza, args.svezhee_chasov)
    todo = [r for r in rows if r["remove"] or r["prune_only"]]
    removed, problems = 0, []

    for r in todo:
        name = f"{r['path']} ({r['branch'] or 'detached'})"
        if not args.da:
            print(f"убрал бы: {name} — {r['state']}" + (f", {r['note']}" if r["note"] else ""))
            continue
        if r["prune_only"]:                                   # каталога нет — уберёт prune в конце
            print(f"prune: {name}")
            removed += 1
            continue
        code, out = git(args.repo, "worktree", "remove", str(r["path"]))   # без --force
        if code != 0:
            problems.append(f"{name}: {out.splitlines()[-1] if out else 'отказ git'}")
            print(f"ОШИБКА: {problems[-1]}")
            continue
        removed += 1
        print(f"убрана: {name}")
        if r["branch"] and r["branch"] != args.baza:         # ветку — только слитую, базу не трогаем
            code, out = git(args.repo, "branch", "-d", r["branch"])
            if code != 0:
                problems.append(f"ветка {r['branch']}: {out.splitlines()[-1] if out else 'отказ git'}")
                print(f"ветка осталась: {problems[-1]}")
    if args.da:
        git(args.repo, "worktree", "prune")

    verb = "убрано" if args.da else "убрал бы"
    print(f"{verb} {len(todo) if not args.da else removed}; оставлено {len(rows) - len(todo)}"
          f" — по причинам: {count_left(rows)}")
    if not args.da and todo:
        print("(ничего не тронуто; чтобы убрать — добавь --da)")
    return 1 if problems else 0


def cmd_novaya(args):
    path = Path(args.put).resolve()
    if path.exists():
        print(f"ОТКАЗ: папка уже есть: {path}")
        return 1
    code, _ = git(args.repo, "show-ref", "--verify", "--quiet", f"refs/heads/{args.vetka}")
    if code == 0:
        print(f"ОТКАЗ: ветка «{args.vetka}» уже есть — возьми другое имя")
        return 1
    code, out = git(args.repo, "worktree", "add", "-b", args.vetka, str(path), args.ot)
    if code != 0:
        print(f"ОШИБКА git: {out}")
        return 1
    print(f"готово: {path} (ветка {args.vetka} от {args.ot})")
    return 0


# ── 5. Запуск ─────────────────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(prog="papki.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--repo", required=True, help="путь к репозиторию")

    sp = sub.add_parser("spisok", help="таблица папок и что с ними будет")
    common(sp)
    sp.add_argument("--baza", default="master")
    sp.add_argument("--svezhee-chasov", type=float, default=12)
    sp.set_defaults(run=cmd_spisok)

    sp = sub.add_parser("ubrat", help="убрать слитые старые папки (без --da — только показать)")
    common(sp)
    sp.add_argument("--baza", default="master")
    sp.add_argument("--svezhee-chasov", type=float, default=12)
    sp.add_argument("--da", action="store_true", help="правда убрать")
    sp.set_defaults(run=cmd_ubrat)

    sp = sub.add_parser("novaya", help="создать папку агента с новой веткой")
    common(sp)
    sp.add_argument("--put", required=True, help="куда положить папку")
    sp.add_argument("--vetka", required=True, help="имя новой ветки")
    sp.add_argument("--ot", default="master", help="от чего ветка")
    sp.set_defaults(run=cmd_novaya)
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    code, out = git(args.repo, "rev-parse", "--git-dir")
    if code != 0:
        print(f"«{args.repo}» — не git-репозиторий: {out}")
        return 2
    try:
        return args.run(args)
    except RuntimeError as e:
        print(f"ОШИБКА: {e}")
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
