import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(DB_DIR, 'dashboard.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')

db = SQLAlchemy(app)


class Entry(db.Model):
    """Unified model: represents what were previously Sessions and Incidents.
    Fields are named to match existing template expectations (started_at, occurred_at, confidence, incident_type, images).
    """
    id = db.Column(db.Integer, primary_key=True)
    # used when the item acted as a 'session' (camera start time)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    description = db.Column(db.Text, default='')

    # used when the item acted as an 'incident'
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow)
    confidence = db.Column(db.Float, nullable=True)
    incident_type = db.Column(db.String(100), default='suspicious')
    images_json = db.Column(db.Text, default='[]')

    @property
    def images(self):
        try:
            imgs = json.loads(self.images_json)
        except Exception:
            imgs = []

        # Resolve each image path to an existing static file. If the file
        # doesn't exist (common with seeded demo data), fall back to a
        # placeholder image so the UI doesn't show 404s.
        resolved = []
        for p in imgs:
            if not p:
                continue
            full = os.path.join(BASE_DIR, 'static', p)
            if os.path.exists(full):
                resolved.append(p)
            else:
                resolved.append('uploads/placeholder.svg')
        return resolved

    def to_dict(self):
        return {
            'id': self.id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'occurred_at': self.occurred_at.isoformat() if self.occurred_at else None,
            'confidence': self.confidence,
            'type': self.incident_type,
            'images': self.images,
            'description': self.description,
        }


def ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with app.app_context():
        db.create_all()


def setup_db():
    # create DB and seed if necessary
    os.makedirs(DB_DIR, exist_ok=True)
    # For development: if DB is missing the unified 'entry' table, drop it and recreate to avoid schema mismatches.
    try:
        if os.path.exists(DB_PATH):
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            conn.close()
            # If the DB doesn't have our 'entry' table, or still has old tables, recreate it.
            if 'entry' not in tables or 'session' in tables or 'incident' in tables:
                try:
                    os.remove(DB_PATH)
                    print('Removed old DB to recreate unified schema...')
                except Exception:
                    pass
    except Exception:
        pass

    ensure_db()

    with app.app_context():
        if Entry.query.count() == 0:
            # seed a few unified entries for demo
            e1 = Entry(description='Camera turned on - monitoring started', started_at=datetime.utcnow(), occurred_at=datetime.utcnow(), confidence=None)
            e2 = Entry(description='Camera restarted - suspicious motion', started_at=datetime.utcnow(), occurred_at=datetime.utcnow(), confidence=52.2, incident_type='loiter', images_json=json.dumps(['uploads/sample2.jpg']))
            e3 = Entry(description='Active session - possible grab detected', started_at=datetime.utcnow(), occurred_at=datetime.utcnow(), confidence=92.1, incident_type='grab', images_json=json.dumps(['uploads/sample3.jpg','uploads/sample4.jpg']))
            e4 = Entry(description='Follow-up incident', started_at=datetime.utcnow(), occurred_at=datetime.utcnow(), confidence=66.7, incident_type='reach', images_json=json.dumps(['uploads/sample5.jpg']))
            db.session.add_all([e1, e2, e3, e4])
            db.session.commit()


# Initialize DB on startup
setup_db()


@app.route('/')
def index():
    sessions = Entry.query.order_by(Entry.started_at.desc()).all()

    # current session -> latest entry
    current_session = sessions[0] if sessions else None

    # recent incidents -> latest 3 entries that have a confidence value (treat as incidents)
    recent_incidents = Entry.query.filter(Entry.confidence != None).order_by(Entry.occurred_at.desc()).limit(3).all()

    sessions_for_conf = Entry.query.order_by(Entry.started_at.desc()).limit(4).all()
    labels = [f'S-{s.id}' for s in sessions_for_conf]
    confidences = [round(s.confidence or 0, 1) for s in sessions_for_conf]

    return render_template('index.html', sessions=sessions, current_session=current_session,
                           recent_incidents=recent_incidents,
                           chart_labels=labels, chart_data=confidences)


@app.route('/sessions/<int:session_id>')
def session_detail(session_id):
    e = Entry.query.get_or_404(session_id)
    # render event detail using the incident detail template for consistency
    return render_template('incident.html', incident=e)


@app.route('/sessions')
def sessions_list():
    # return the most recent 3 sessions (past 3 sessions)
    sessions = Entry.query.order_by(Entry.started_at.desc()).limit(3).all()
    return render_template('sessions.html', sessions=sessions)


@app.route('/sessions/all')
def sessions_all():
    # full sessions list
    sessions = Entry.query.order_by(Entry.started_at.desc()).all()
    return render_template('sessions_all.html', sessions=sessions)


@app.route('/all-sessions')
def all_sessions_redirect():
    # convenience redirect to canonical URL
    return redirect(url_for('sessions_all'))


@app.route('/incidents/<int:incident_id>')
def incident_detail(incident_id):
    inc = Entry.query.get_or_404(incident_id)
    return render_template('incident.html', incident=inc)


@app.route('/sessions/<int:session_id>/delete', methods=['POST'])
def delete_session(session_id):
    s = Entry.query.get_or_404(session_id)
    db.session.delete(s)
    db.session.commit()
    flash(f'Session {session_id} deleted', 'success')
    return redirect(url_for('index'))


@app.route('/incidents/<int:incident_id>/delete', methods=['POST'])
def delete_incident(incident_id):
    inc = Entry.query.get_or_404(incident_id)
    db.session.delete(inc)
    db.session.commit()
    flash(f'Incident {incident_id} deleted', 'success')
    return redirect(url_for('index'))


@app.route('/start_session', methods=['POST'])
def start_session():
    desc = request.form.get('description', 'Camera started - new session')
    s = Entry(description=desc, started_at=datetime.utcnow(), occurred_at=datetime.utcnow())
    db.session.add(s)
    db.session.commit()
    flash(f'Session {s.id} started', 'success')
    return redirect(url_for('index'))


@app.route('/add_incident', methods=['POST'])
def add_incident():
    try:
        # session_id is optional in unified model; ignore if provided
        _ = request.form.get('session_id')
    except Exception:
        # continue even if missing
        _ = None
    confidence = float(request.form.get('confidence', 0))
    itype = request.form.get('incident_type', 'suspicious')
    images = []
    upload_folder = os.path.join(BASE_DIR, 'static', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    for f in request.files.getlist('images'):
        if f and f.filename:
            filename = secure_filename(f.filename)
            dest = os.path.join(upload_folder, filename)
            f.save(dest)
            images.append(f'uploads/{filename}')

    inc = Entry(description=request.form.get('description',''), occurred_at=datetime.utcnow(), confidence=confidence, incident_type=itype, images_json=json.dumps(images))
    db.session.add(inc)
    db.session.commit()
    flash('Incident added', 'success')
    return redirect(url_for('index'))


@app.route('/static/<path:filename>')
def custom_static(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)


if __name__ == '__main__':
    ensure_db()
    app.run(debug=True)
