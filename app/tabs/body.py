"""Body: health metrics over time. For now just weight, one weigh-in per day
in kg; more (e.g. blood test reports) will be added here."""
from datetime import date


def _check_date(value):
    return date.fromisoformat(value).isoformat()


def _kg(value):
    """None/'' -> None (no weigh-in); otherwise a weight above 0 (or refuse)."""
    if value is None or value == "":
        return None
    try:
        kg = float(value)
    except (TypeError, ValueError):
        raise ValueError("Weight must be a number") from None
    if not 0 < kg < 1000:
        raise ValueError("Weight must be between 0 and 1000 kg")
    return kg


def get_weight(conn, day):
    """The day's weight in kg, or None if you didn't weigh in."""
    row = conn.execute("SELECT kg FROM weights WHERE day = ?", (_check_date(day),)).fetchone()
    return row["kg"] if row else None


def save_weight(conn, day, kg):
    """Set the day's weight; empty removes it."""
    day, kg = _check_date(day), _kg(kg)
    with conn:
        if kg is None:
            conn.execute("DELETE FROM weights WHERE day = ?", (day,))
        else:
            conn.execute(
                "INSERT INTO weights (day, kg) VALUES (?, ?)"
                " ON CONFLICT (day) DO UPDATE SET kg = excluded.kg",
                (day, kg),
            )


def get_weights(conn):
    """Every weigh-in, newest first: the weights table as it is."""
    return [dict(row) for row in conn.execute("SELECT day, kg FROM weights ORDER BY day DESC")]
