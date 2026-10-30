"""Journal entries are text files in LifeOS_data/Journal Entries, one per day."""
import pytest

from app import db
from app.tabs import journal

DAY = "2026-10-27"


def test_file_named_by_date_with_date_line_on_top(data_dir):
    journal.save_day(DAY, "Slept well.\nGood day.")
    path = data_dir / "Journal Entries" / "2026-10-27.txt"
    assert path.read_text() == "Tuesday, 27 October 2026\n\nSlept well.\nGood day."
    assert journal.read(DAY) == "Slept well.\nGood day."   # date line not part of the text


def test_get_day_and_all_newest_first():
    journal.save_day(DAY, "Note")
    journal.save_day("2026-10-20", "Older")
    assert journal.get_day(DAY) == "Note" and journal.get_day("2026-10-01") == ""
    assert [e["day"] for e in journal.get_all()] == [DAY, "2026-10-20"]


def test_emptying_deletes_the_file(data_dir):
    journal.write(DAY, "Note")
    journal.write(DAY, "  ")
    assert not (data_dir / "Journal Entries" / "2026-10-27.txt").exists()
    assert journal.get_all() == []


def test_files_edited_by_hand_still_read(data_dir):
    folder = data_dir / "Journal Entries"
    folder.mkdir(parents=True)
    (folder / "2026-10-01.txt").write_text("No date line, just text")
    (folder / "notes.txt").write_text("not a journal day")      # ignored
    assert journal.get_all() == [{"day": "2026-10-01", "body": "No date line, just text"}]


def test_backup_copies_the_journal_folder(conn, tmp_path):
    journal.write(DAY, "Note")
    backups = tmp_path / "backups"
    db.backup(conn, backups, folders=[journal.folder()])
    [copy] = backups.glob("journal-entries-*")
    assert (copy / "2026-10-27.txt").read_text().endswith("Note")


def test_bad_day_refused():
    with pytest.raises(ValueError):
        journal.write("27/10/2026", "Note")
