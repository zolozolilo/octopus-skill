# octopus — скилл для Claude Code

Любая задача — дерево. Осьминог трясёт его и снимает листья **параллельно**, каждую ветку ведёт **с двух концов навстречу**: от причины и от результата. Проверки — тоже листья и идут рядом с кодом, а не после.

<p align="center"><img src="art/banner.gif" width="800" alt="octopus — осьминог трясёт дерево задач"></p>

## Что внутри

| Файл | Что делает |
|---|---|
| `SKILL.md` | Сам скилл: дерево → ветки → листья → сегменты, пара «строитель + приёмщик» на каждый лист, красный прогон до правки, критик до слияния, статус деревом |
| `skorost-sveta.md` | Режим «полный газ» поверх дерева: подмога строителю, агент текстов с первой минуты, прогрев — ворота не режутся |
| `agents/kritik.md` | Агент-критик: проверяет работу агента по заданию и диффу, а не по отчёту автора; вердикт ПРИНЯТЬ / ВЕРНУТЬ |
| `SKILL.en.md` | English version of `SKILL.md` |
| `peresechenie.py` | Пересечения заданий агентов: один файл в двух заданиях — стоп. С `--graphify` ловит скрытые связи по карте кода; `zadeto` — кого задевает правка; `sverka` — «обещал / сделал» по git |
| `papki.py` | Отдельные рабочие папки (git worktree) для агентов и уборка только слитых и чистых |
| `doska.py` | Доска листьев: `doska/derevo.json` и локальная страница `doska/doska.html` без сети |
| `skhema-*.png` | Рисунки схемы от руки |
| `art/banner.py`, `art/skorost-sveta.py` | Анимации README — нарисованы кодом: `python art/banner.py` (нужен Pillow) |
| `test_*.py` | Тесты всех трёх скриптов |

## Скорость света

Когда торопят — режим поверх дерева (`skorost-sveta.md`): подмога строителю, агент текстов с первой минуты, прогрев кэшей. Режется ожидание, а не проверки.

<p align="center"><img src="art/skorost-sveta.gif" width="512" alt="скорость света — осьминог на микроволновке греет кэш"></p>

## Установка

```bash
git clone https://github.com/zolozolilo/octopus-skill ~/.claude/skills/octopus
```

Критик — отдельный агент, его кладут к агентам:

```bash
mkdir -p ~/.claude/agents && cp ~/.claude/skills/octopus/agents/kritik.md ~/.claude/agents/
```

Claude Code подхватит скилл сам: он срабатывает на любой многошаговой задаче и на словах «осьминог», «дерево», «параллельно», «с двух концов».

Нужны Python 3 и git. Карта кода [Graphify](https://docs.graphify.com) — по желанию: без неё `peresechenie.py` проверяет пересечения по именам файлов и честно пишет «карта: НЕ ЗНАЮ».

Тесты:

```bash
cd ~/.claude/skills/octopus && python -m pytest -q
```

## English

**octopus** is a Claude Code skill for multi-step work. Every task is a tree; independent leaves run in parallel, and each branch is worked from both ends at once — from the cause and from the delivered result. Every leaf is a builder/acceptor pair: the acceptor writes failing acceptance tests first, and a red run is saved before the fix. An independent critic reviews agent work before merge. Helper scripts check that agent tasks do not touch the same files (optionally via a [Graphify](https://docs.graphify.com) code map), manage agent worktrees, and render a local task board. The skill text is in Russian; for English, use `SKILL.en.md` as `SKILL.md`:

```bash
cd ~/.claude/skills/octopus && mv SKILL.md SKILL.ru.md && mv SKILL.en.md SKILL.md
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
