"""Templates: one text file per template, in LifeOS_data/Templates/<tab>."""
import pytest

from app import templates


def test_create_save_rename_delete(data_dir):
    templates.create("Gym", " Push ", "Bench press: kg :")
    assert templates.get_all("Gym") == [{"name": "Push", "body": "Bench press: kg :"}]
    assert (data_dir / "Templates" / "Gym" / "Push.txt").read_text() == "Bench press: kg :"
    assert templates.save("Gym", "push", "Push day", "Bench 5x5") == "Push day"
    assert templates.get_all("Gym") == [{"name": "Push day", "body": "Bench 5x5"}]
    templates.delete("Gym", "Push day")
    assert templates.get_all("Gym") == []


def test_listed_by_name_and_kept_per_tab():
    for name in ["pull", "Legs", "Push"]:
        templates.create("Gym", name)
    templates.create("Food", "Omelette", "- Egg 3")
    assert [t["name"] for t in templates.get_all("Gym")] == ["Legs", "pull", "Push"]
    assert [t["name"] for t in templates.get_all("Food")] == ["Omelette"]


@pytest.mark.parametrize("name", ["  ", "a/b", "a:b", ".hidden"])
def test_names_must_work_as_file_names(name):
    with pytest.raises(ValueError):
        templates.create("Gym", name)


def test_names_are_unique_ignoring_capitals():
    templates.create("Food", "Omelette")
    templates.create("Food", "Porridge")
    with pytest.raises(ValueError):
        templates.create("Food", "OMELETTE")
    with pytest.raises(ValueError):
        templates.save("Food", "Porridge", "omelette", "")
    assert templates.save("Food", "Omelette", "omelette", "") == "omelette"   # just capitals: fine
    assert [t["name"] for t in templates.get_all("Food")] == ["omelette", "Porridge"]


def test_unknown_tab_or_template_refused():
    with pytest.raises(ValueError):
        templates.get_all("Journal")
    with pytest.raises(ValueError):
        templates.save("Gym", "Missing", "Missing", "")
