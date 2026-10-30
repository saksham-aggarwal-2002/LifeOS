"""The bridge: every public method here can be called from JavaScript as
`await window.pywebview.api.<method_name>(...)`.

Keep these methods thin: pass the connection to a tab's function and return
its result. The real logic lives in app/tabs/.
"""
from app import datafolder, extract, templates
from app.tabs import body, food, gym, journal, log, settings, todo


class Api:
    def __init__(self, conn):
        # Leading underscore: pywebview only exposes public names to JS.
        self._conn = conn

    # --- To Do ---
    def todo_get_lists(self):
        return todo.get_lists(self._conn)

    def todo_create_list(self, name):
        return todo.create_list(self._conn, name)

    def todo_rename_list(self, list_id, name):
        return todo.rename_list(self._conn, list_id, name)

    def todo_reorder_lists(self, list_ids):
        return todo.reorder_lists(self._conn, list_ids)

    def todo_delete_list(self, list_id):
        return todo.delete_list(self._conn, list_id)

    def todo_get_tasks(self, list_id):
        return todo.get_tasks(self._conn, list_id)

    def todo_get_my_day(self):
        return todo.get_my_day(self._conn)

    def todo_get_calendar(self, start, end):
        return todo.get_calendar(self._conn, start, end)

    def todo_get_unscheduled(self):
        return todo.get_unscheduled(self._conn)

    def todo_set_do_date(self, task_id, do_date):
        return todo.set_do_date(self._conn, task_id, do_date)

    def todo_add_task(self, list_id, title, do_date=None):
        return todo.add_task(self._conn, list_id, title, do_date)

    def todo_toggle_task(self, task_id):
        return todo.toggle_task(self._conn, task_id)

    def todo_rename_task(self, task_id, title):
        return todo.rename_task(self._conn, task_id, title)

    def todo_delete_task(self, task_id):
        return todo.delete_task(self._conn, task_id)

    def todo_restore_task(self, task_id):
        return todo.restore_task(self._conn, task_id)

    def todo_get_deleted(self):
        return todo.get_deleted(self._conn)

    # --- Gym ---
    def gym_get_sessions(self):
        return gym.get_sessions(self._conn)

    def gym_save_sets(self, entry_id, sets):
        return gym.save_sets(self._conn, entry_id, sets)

    def gym_get_exercises(self):
        return gym.get_exercises(self._conn)

    def gym_add_exercise(self, name):
        return gym.add_exercise(self._conn, name)

    def gym_rename_exercise(self, exercise_id, name):
        return gym.rename_exercise(self._conn, exercise_id, name)

    def gym_delete_exercise(self, exercise_id):
        return gym.delete_exercise(self._conn, exercise_id)

    # --- Food ---
    def food_get_foods(self):
        return food.get_foods(self._conn)

    def food_create_food(self, name):
        return food.create_food(self._conn, name)

    def food_update_food(self, food_id, fields):
        return food.update_food(self._conn, food_id, fields)

    def food_delete_food(self, food_id):
        return food.delete_food(self._conn, food_id)

    def food_get_diary(self):
        return food.get_diary(self._conn)

    def food_save_items(self, entry_id, items):
        return food.save_items(self._conn, entry_id, items)

    # --- Templates (Gym's workouts, Food's recipes): text files ---
    # tab is "Gym" or "Food"; a template is known by its name.
    def templates_get(self, tab):
        return templates.get_all(tab)

    def templates_create(self, tab, name):
        return templates.create(tab, name)

    def templates_save(self, tab, name, new_name, body):
        return templates.save(tab, name, new_name, body)

    def templates_delete(self, tab, name):
        return templates.delete(tab, name)

    # --- Extract Structured Data (AI) ---
    def extract_workout(self, entry_id):
        return extract.extract_workout(self._conn, entry_id)

    def extract_food(self, entry_id):
        return extract.extract_food(self._conn, entry_id)

    # --- Overview (reads each tab's day; saving goes to the tab) ---
    def log_get_day(self, day):
        return log.get_day(self._conn, day)

    # --- Daily logs, owned by each tab ---
    def gym_get_day(self, day):
        return gym.get_day(self._conn, day)

    def food_get_day(self, day):
        return food.get_day(self._conn, day)

    def journal_get_day(self, day):
        return journal.get_day(day)

    def gym_save_day(self, day, text):
        return gym.save_day(self._conn, day, text)

    def food_save_day(self, day, text):
        return food.save_day(self._conn, day, text)

    def journal_save_day(self, day, text):
        return journal.save_day(day, text)

    def journal_get_all(self):
        return journal.get_all()

    # --- Body ---
    def body_get_weight(self, day):
        return body.get_weight(self._conn, day)

    def body_save_weight(self, day, kg):
        return body.save_weight(self._conn, day, kg)

    def body_get_weights(self):
        return body.get_weights(self._conn)

    # --- Settings ---
    def settings_get_data_folder(self):
        return datafolder.status()

    def settings_use_data_folder(self, which):
        self._conn = datafolder.switch(self._conn, which)
        return datafolder.status()

    def settings_reset_test_data(self):
        self._conn = datafolder.reset_test(self._conn)
        return datafolder.status()

    def settings_get_readme(self):
        return settings.get_readme(self._conn)
