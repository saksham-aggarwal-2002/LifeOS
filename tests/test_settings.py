"""Settings shows the data folder's README (switching folders: test_datafolder.py)."""
from app.tabs import settings


def test_readme_is_written_and_returned_current(conn, data_dir):
    from app.tabs import body
    body.save_weight(conn, "2026-10-29", 80)
    text = settings.get_readme(conn)
    assert text == (data_dir / "README.md").read_text()
    assert "#### `weights` (1 row)" in text
