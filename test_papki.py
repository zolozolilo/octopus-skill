"""Тесты papki.py: временный репозиторий в tmp_path, настоящий git.
Запуск:  python -m pytest test_papki.py -q
Старость папки задаём os.utime на файлах её gitdir (HEAD, index, logs/HEAD).
"""
import os
import shutil
import subprocess
import time

import pytest

import papki

DAY = 24 * 3600


def run(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          encoding="utf-8", errors="replace")
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """Репозиторий с одним коммитом в master и .gitignore для bin/."""
    r = tmp_path / "repo"
    r.mkdir()
    run(r, "init", "-b", "master")
    run(r, "config", "user.email", "t@t")
    run(r, "config", "user.name", "t")
    (r / ".gitignore").write_text("bin/\n")
    (r / "a.txt").write_text("a")
    run(r, "add", ".")
    run(r, "commit", "-m", "first")
    return r


def add_tree(repo, name, branch="feat", detach=False):
    path = repo.parent / name
    if detach:
        run(repo, "worktree", "add", "--detach", str(path), "master")
    else:
        run(repo, "worktree", "add", "-b", branch, str(path), "master")
    return path


def make_old(path, days=2):
    """Состарить папку: все файлы её gitdir — на days суток назад."""
    gd = papki.gitdir_of(path)
    old = time.time() - days * DAY
    for p in [gd, *gd.rglob("*")]:
        os.utime(p, (old, old))


def go(capsys, *args):
    code = papki.main([*args])
    return code, capsys.readouterr().out


def branches(repo):
    return run(repo, "branch", "--format=%(refname:short)").split()


def test_sliataya_staraya_ubiraetsya(repo, capsys):
    wt = add_tree(repo, "wt1")
    make_old(wt)
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert code == 0, out
    assert not wt.exists()
    assert "feat" not in branches(repo)
    assert "убрано 1" in out


def test_nesliataya_s_kommitom_ostayotsya(repo, capsys):
    wt = add_tree(repo, "wt2")
    (wt / "b.txt").write_text("b")
    run(wt, "add", ".")
    run(wt, "commit", "-m", "work")
    make_old(wt)
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert code == 0, out
    assert wt.exists() and "feat" in branches(repo)
    assert "не слита 1" in out


def test_gryaznaya_ostayotsya(repo, capsys):
    wt = add_tree(repo, "wt3")
    (wt / "new.txt").write_text("не закоммичено")
    make_old(wt)
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert wt.exists() and "грязная 1" in out


def test_ignoriruemye_bin_ne_gryaz(repo, capsys):
    wt = add_tree(repo, "wt3b")
    (wt / "bin").mkdir()
    (wt / "bin" / "x.dll").write_text("x")
    make_old(wt)
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert code == 0, out
    assert not wt.exists()


def test_svezhaya_bez_kommitov_ostayotsya_po_vozrastu(repo, capsys):
    wt = add_tree(repo, "wt4")
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert wt.exists() and "свежая 1" in out
    # а с порогом «0 часов» та же папка уже подходит
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da", "--svezhee-chasov", "0")
    assert not wt.exists()


def test_detached_sliataya_staraya_ubiraetsya(repo, capsys):
    wt = add_tree(repo, "wt5", detach=True)
    make_old(wt)
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert code == 0, out
    assert not wt.exists()


def test_locked_ostayotsya(repo, capsys):
    wt = add_tree(repo, "wt6")
    make_old(wt)
    run(repo, "worktree", "lock", str(wt))
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert wt.exists() and "заперта 1" in out


def test_bez_da_nichego_ne_udalyaetsya(repo, capsys):
    wt = add_tree(repo, "wt7")
    make_old(wt)
    code, out = go(capsys, "ubrat", "--repo", str(repo))
    assert code == 0
    assert wt.exists() and "feat" in branches(repo)
    assert "убрал бы 1" in out and "убрал бы:" in out


def test_kirillitsa_v_imeni_papki(repo, capsys):
    wt = add_tree(repo, "папка агента", branch="vetka-ru")
    make_old(wt)
    code, out = go(capsys, "spisok", "--repo", str(repo))
    assert "папка агента" in out and "уберу" in out
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert code == 0, out
    assert not wt.exists() and "vetka-ru" not in branches(repo)


def test_net_katalogaa_tolko_prune(repo, capsys):
    wt = add_tree(repo, "wt8")
    shutil.rmtree(wt, ignore_errors=True)
    code, out = go(capsys, "ubrat", "--repo", str(repo), "--da")
    assert code == 0, out
    assert len(papki.read_worktrees(repo)) == 1


def test_glavnaya_nikogda_ne_ubiraetsya(repo, capsys):
    go(capsys, "ubrat", "--repo", str(repo), "--da", "--svezhee-chasov", "0")
    assert repo.exists() and "master" in branches(repo)


def test_novaya_sozdayot_i_otkazyvaet(repo, capsys):
    put = repo.parent / "новая"
    code, out = go(capsys, "novaya", "--repo", str(repo), "--put", str(put), "--vetka", "nv")
    assert code == 0 and put.exists() and "nv" in branches(repo)
    code, out = go(capsys, "novaya", "--repo", str(repo), "--put", str(put), "--vetka", "other")
    assert code == 1 and "папка уже есть" in out
    code, out = go(capsys, "novaya", "--repo", str(repo),
                   "--put", str(repo.parent / "dr"), "--vetka", "nv")
    assert code == 1 and "ветка" in out and not (repo.parent / "dr").exists()


def test_ne_repozitoriy_kod_2(tmp_path, capsys):
    code, out = go(capsys, "spisok", "--repo", str(tmp_path))
    assert code == 2
