"""SQLite file with the ward plan, which tasks are done and every visit record."""
import os
import sqlite3
from threading import Lock

TASK_FIELDS = ['id', 'bed', 'time', 'daily', 'temperature', 'pulse_oximeter', 'hopper', 'count']

SCHEMA = '''
CREATE TABLE IF NOT EXISTS beds (number INTEGER PRIMARY KEY, occupied INTEGER);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, bed INTEGER, time TEXT, daily INTEGER,
    temperature INTEGER, pulse_oximeter INTEGER, hopper INTEGER, count INTEGER);
CREATE TABLE IF NOT EXISTS done (task TEXT, day TEXT, PRIMARY KEY (task, day));
CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, trip TEXT,
    bed INTEGER, tasks TEXT, temperature REAL, heart_rate REAL, spo2 REAL, pills INTEGER,
    collected INTEGER, status TEXT);
'''


class WardDB:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # the plan arrives on the executor thread, visits are saved on the main one
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = Lock()
        self.db.executescript(SCHEMA)

    def save_plan(self, beds, tasks):
        """beds is {number: occupied}, tasks a list of dicts with TASK_FIELDS."""
        with self.lock, self.db:
            self.db.execute('DELETE FROM beds')
            self.db.execute('DELETE FROM tasks')
            self.db.executemany('INSERT INTO beds VALUES (?, ?)', beds.items())
            self.db.executemany('INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                [[t[k] for k in TASK_FIELDS] for t in tasks])

    def load_plan(self):
        with self.lock:
            beds = dict(self.db.execute('SELECT number, occupied FROM beds').fetchall())
            rows = self.db.execute(f'SELECT {", ".join(TASK_FIELDS)} FROM tasks').fetchall()
        beds = {n: bool(o) for n, o in beds.items()}
        tasks = []
        for row in rows:
            task = dict(zip(TASK_FIELDS, row))
            # SQLite keeps booleans as 0 and 1
            for k in ('daily', 'temperature', 'pulse_oximeter'):
                task[k] = bool(task[k])
            tasks.append(task)
        return beds, tasks

    def is_done(self, task, day):
        with self.lock:
            row = self.db.execute('SELECT 1 FROM done WHERE task = ? AND day = ?', (task, day))
            return row.fetchone() is not None

    def mark_done(self, task, day):
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO done VALUES (?, ?)', (task, day))

    def add_visit(self, r):
        with self.lock, self.db:
            self.db.execute(
                'INSERT INTO visits (time, trip, bed, tasks, temperature, heart_rate, spo2, pills,'
                ' collected, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (r.time, r.trip, r.bed, ','.join(r.tasks), r.temperature, r.heart_rate, r.spo2,
                 r.pills, r.collected, r.status))
