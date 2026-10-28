import webbrowser
import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'studysync.db'
app = Flask(__name__)
app.secret_key = 'studysync-ai-local-dev-key'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    with get_db() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#6c63ff',
            total_topics INTEGER NOT NULL DEFAULT 0,
            completed_topics INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject_id INTEGER,
            due_date TEXT,
            priority TEXT NOT NULL DEFAULT 'Medium',
            status TEXT NOT NULL DEFAULT 'Pending',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject_id INTEGER,
            exam_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE SET NULL
        );
        ''')
        count = db.execute('SELECT COUNT(*) FROM subjects').fetchone()[0]
        if count == 0:
            db.executemany('INSERT INTO subjects(name,color,total_topics,completed_topics) VALUES(?,?,?,?)', [
                ('Data Mining & Warehousing', '#6c63ff', 12, 5),
                ('Software Architecture', '#12b886', 10, 4),
                ('Big Data', '#f59f00', 14, 6),
            ])
            db.executemany('INSERT INTO tasks(title,subject_id,due_date,priority,status,notes) VALUES(?,?,?,?,?,?)', [
                ('Revise Unit 2 notes', 1, (date.today()+timedelta(days=1)).isoformat(), 'High', 'Pending', 'Focus on important definitions'),
                ('Complete assignment draft', 2, (date.today()+timedelta(days=3)).isoformat(), 'Medium', 'Pending', ''),
                ('Practice Hadoop questions', 3, (date.today()+timedelta(days=2)).isoformat(), 'Low', 'Completed', ''),
            ])
            db.executemany('INSERT INTO exams(title,subject_id,exam_date,notes) VALUES(?,?,?,?)', [
                ('MST Practice Test', 1, (date.today()+timedelta(days=7)).isoformat(), 'Revise Units 1 and 2'),
                ('Big Data Test', 3, (date.today()+timedelta(days=12)).isoformat(), 'Practice short answers'),
            ])


def subject_rows(db):
    rows = db.execute('''SELECT s.*, CASE WHEN total_topics > 0 THEN ROUND(100.0*completed_topics/total_topics) ELSE 0 END AS progress
                         FROM subjects s ORDER BY s.name''').fetchall()
    return rows


@app.route('/')
def dashboard():
    with get_db() as db:
        subjects = subject_rows(db)
        tasks = db.execute('''SELECT t.*, s.name AS subject_name FROM tasks t LEFT JOIN subjects s ON s.id=t.subject_id
                              ORDER BY CASE t.status WHEN 'Pending' THEN 0 ELSE 1 END,
                              CASE t.priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
                              COALESCE(t.due_date,'9999-12-31') LIMIT 6''').fetchall()
        exams = db.execute('''SELECT e.*, s.name AS subject_name FROM exams e LEFT JOIN subjects s ON s.id=e.subject_id
                              WHERE e.exam_date >= ? ORDER BY e.exam_date LIMIT 5''', (date.today().isoformat(),)).fetchall()
        total_tasks = db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status='Completed'").fetchone()[0]
        pending_tasks = total_tasks - completed_tasks
        overall = round(sum(s['progress'] for s in subjects) / len(subjects)) if subjects else 0
        week = []
        for offset in range(6, -1, -1):
            day = date.today() - timedelta(days=offset)
            done = db.execute("SELECT COUNT(*) FROM tasks WHERE status='Completed' AND date(created_at)=?", (day.isoformat(),)).fetchone()[0]
            week.append({'label': day.strftime('%a'), 'done': done})
    return render_template('index.html', subjects=subjects, tasks=tasks, exams=exams,
                           total_tasks=total_tasks, completed_tasks=completed_tasks,
                           pending_tasks=pending_tasks, overall=overall, week=week,
                           today=date.today().isoformat())


@app.route('/subjects', methods=['GET', 'POST'])
def subjects_page():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#6c63ff')
        total = max(0, int(request.form.get('total_topics') or 0))
        if not name:
            flash('Please enter a subject name.', 'error')
        else:
            with get_db() as db:
                db.execute('INSERT INTO subjects(name,color,total_topics,completed_topics) VALUES(?,?,?,0)', (name, color, total))
            flash('Subject added successfully!', 'success')
        return redirect(url_for('subjects_page'))
    with get_db() as db:
        subjects = subject_rows(db)
    return render_template('subjects.html', subjects=subjects)


@app.post('/subjects/<int:subject_id>/progress')
def update_progress(subject_id):
    try:
        completed = max(0, int(request.form.get('completed_topics') or 0))
    except ValueError:
        completed = 0
    with get_db() as db:
        row = db.execute('SELECT total_topics FROM subjects WHERE id=?', (subject_id,)).fetchone()
        if row:
            completed = min(completed, row['total_topics']) if row['total_topics'] > 0 else completed
            db.execute('UPDATE subjects SET completed_topics=? WHERE id=?', (completed, subject_id))
            flash('Syllabus progress updated.', 'success')
    return redirect(url_for('subjects_page'))


@app.post('/subjects/<int:subject_id>/delete')
def delete_subject(subject_id):
    with get_db() as db:
        db.execute('DELETE FROM subjects WHERE id=?', (subject_id,))
    flash('Subject deleted.', 'success')
    return redirect(url_for('subjects_page'))


@app.route('/tasks', methods=['GET', 'POST'])
def tasks_page():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Task title is required.', 'error')
            return redirect(url_for('tasks_page'))
        subject_id = request.form.get('subject_id') or None
        due_date = request.form.get('due_date') or None
        priority = request.form.get('priority', 'Medium')
        notes = request.form.get('notes', '').strip()
        with get_db() as db:
            db.execute('INSERT INTO tasks(title,subject_id,due_date,priority,notes) VALUES(?,?,?,?,?)',
                       (title, subject_id, due_date, priority, notes))
        flash('Task added!', 'success')
        return redirect(url_for('tasks_page'))
    with get_db() as db:
        tasks = db.execute('''SELECT t.*, s.name AS subject_name FROM tasks t LEFT JOIN subjects s ON s.id=t.subject_id
                              ORDER BY CASE t.status WHEN 'Pending' THEN 0 ELSE 1 END, COALESCE(t.due_date,'9999-12-31')''').fetchall()
        subjects = subject_rows(db)
    return render_template('tasks.html', tasks=tasks, subjects=subjects, today=date.today().isoformat())


@app.post('/tasks/<int:task_id>/toggle')
def toggle_task(task_id):
    with get_db() as db:
        row = db.execute('SELECT status FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row:
            status = 'Completed' if row['status'] != 'Completed' else 'Pending'
            db.execute('UPDATE tasks SET status=? WHERE id=?', (status, task_id))
    return redirect(request.referrer or url_for('tasks_page'))


@app.post('/tasks/<int:task_id>/delete')
def delete_task(task_id):
    with get_db() as db:
        db.execute('DELETE FROM tasks WHERE id=?', (task_id,))
    flash('Task deleted.', 'success')
    return redirect(request.referrer or url_for('tasks_page'))


@app.route('/exams', methods=['GET', 'POST'])
def exams_page():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        exam_date = request.form.get('exam_date', '').strip()
        if not title or not exam_date:
            flash('Exam name and date are required.', 'error')
            return redirect(url_for('exams_page'))
        with get_db() as db:
            db.execute('INSERT INTO exams(title,subject_id,exam_date,notes) VALUES(?,?,?,?)',
                       (title, request.form.get('subject_id') or None, exam_date, request.form.get('notes', '').strip()))
        flash('Exam added to planner!', 'success')
        return redirect(url_for('exams_page'))
    with get_db() as db:
        exams = db.execute('''SELECT e.*, s.name AS subject_name FROM exams e LEFT JOIN subjects s ON s.id=e.subject_id
                              ORDER BY e.exam_date''').fetchall()
        subjects = subject_rows(db)
    return render_template('exams.html', exams=exams, subjects=subjects, today=date.today().isoformat())


@app.post('/exams/<int:exam_id>/delete')
def delete_exam(exam_id):
    with get_db() as db:
        db.execute('DELETE FROM exams WHERE id=?', (exam_id,))
    flash('Exam removed.', 'success')
    return redirect(url_for('exams_page'))


@app.route('/timetable', methods=['GET', 'POST'])
def timetable():
    plan = []
    if request.method == 'POST':
        try:
            available = max(1, min(12, int(request.form.get('hours') or 3)))
        except ValueError:
            available = 3
        with get_db() as db:
            subjects = subject_rows(db)
            tasks = db.execute("SELECT t.*, s.name AS subject_name FROM tasks t LEFT JOIN subjects s ON s.id=t.subject_id WHERE t.status='Pending' ORDER BY CASE t.priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, COALESCE(t.due_date,'9999-12-31')").fetchall()
        candidates = []
        for task in tasks:
            candidates.append({'title': task['title'], 'subject': task['subject_name'] or 'General', 'kind': 'Task', 'priority': task['priority']})
        for subject in sorted(subjects, key=lambda s: s['progress']):
            candidates.append({'title': 'Revise syllabus', 'subject': subject['name'], 'kind': 'Revision', 'priority': 'Medium'})
        slots = min(available, len(candidates))
        for i, item in enumerate(candidates[:slots]):
            start_hour = 9 + i
            plan.append({**item, 'time': f'{start_hour:02d}:00 - {start_hour+1:02d}:00'})
    return render_template('timetable.html', plan=plan)


@app.get('/api/summary')
def api_summary():
    with get_db() as db:
        subjects = subject_rows(db)
        counts = db.execute("SELECT status, COUNT(*) AS count FROM tasks GROUP BY status").fetchall()
    return jsonify({'subjects': [{'name': s['name'], 'progress': s['progress']} for s in subjects],
                    'tasks': {row['status']: row['count'] for row in counts}})


@app.errorhandler(404)
def not_found(_error):
    return render_template('404.html'), 404


init_db()

if __name__ == "__main__":
    threading.Timer(
        1.5,
        lambda: webbrowser.open("http://127.0.0.1:5000")
    ).start()

    app.run(debug=False, port=5000)
