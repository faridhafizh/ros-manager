"""Backup storage tests."""

from __future__ import annotations

import re

from ros_manager.storage import backup_filename, prune_backups, write_backup


def test_backup_filename_format():
    name = backup_filename("r1")
    assert re.fullmatch(r"r1_\d{8}T\d{6}\.\d{6}Z\.rsc", name)


def test_write_backup_atomic_and_content(tmp_path):
    directory = tmp_path / "backups"
    path = write_backup(directory, "r1", "/system identity\n")
    assert path.exists()
    assert path.name.startswith("r1_")
    assert path.name.endswith(".rsc")
    assert path.read_text(encoding="utf-8") == "/system identity\n"
    leftovers = [p for p in directory.iterdir() if p.name.startswith(".")]
    assert leftovers == []


def test_prune_backups_keeps_newest(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    names = [
        "r1_20260101T000000.000000Z.rsc",
        "r1_20260102T000000.000000Z.rsc",
        "r1_20260103T000000.000000Z.rsc",
        "r2_20260101T000000.000000Z.rsc",
    ]
    for name in names:
        (directory / name).write_text("x\n", encoding="utf-8")

    deleted = prune_backups(directory, "r1", 2)

    assert [p.name for p in deleted] == [names[0]]
    remaining = sorted(p.name for p in directory.iterdir())
    assert remaining == [
        "r1_20260102T000000.000000Z.rsc",
        "r1_20260103T000000.000000Z.rsc",
        "r2_20260101T000000.000000Z.rsc",
    ]


def test_prune_backups_noop_when_under_limit(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "r1_20260101T000000.000000Z.rsc").write_text("x\n", encoding="utf-8")
    assert prune_backups(directory, "r1", 5) == []


def test_prune_backups_disabled_with_none(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "r1_20260101T000000.000000Z.rsc").write_text("x\n", encoding="utf-8")
    assert prune_backups(directory, "r1", None) == []
