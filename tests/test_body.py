"""Body: one weight per day."""
import pytest

from app.tabs import body

DAY = "2026-10-29"


def test_save_update_and_clear_weight(conn):
    assert body.get_weight(conn, DAY) is None
    body.save_weight(conn, DAY, "80.4")          # the textbox sends text
    body.save_weight(conn, DAY, 80.1)            # same day: replaced
    assert body.get_weight(conn, DAY) == 80.1
    body.save_weight(conn, DAY, "")              # emptied: gone
    assert body.get_weight(conn, DAY) is None


@pytest.mark.parametrize("bad", ["abc", 0, -5, 1000])
def test_refuses_bad_weights(conn, bad):
    with pytest.raises(ValueError):
        body.save_weight(conn, DAY, bad)


def test_weights_newest_first(conn):
    body.save_weight(conn, "2026-10-27", 80)
    body.save_weight(conn, "2026-10-29", 79.4)
    body.save_weight(conn, "2026-10-28", 80.5)
    assert body.get_weights(conn) == [
        {"day": "2026-10-29", "kg": 79.4}, {"day": "2026-10-28", "kg": 80.5}, {"day": "2026-10-27", "kg": 80},
    ]
