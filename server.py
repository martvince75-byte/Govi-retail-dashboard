"""
KVM Retail POS — Cloud Dashboard
---------------------------------
Receives sync data from the local POS and serves a read-only
owner dashboard. Deployed on Render (or any host).

Data is stored in a JSON file on disk (Render's ephemeral storage
is fine — the local POS re-syncs after every EOD).
"""
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

API_KEY   = os.environ.get('API_KEY', 'change-me')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'latest_sync.json')


# ── Helpers ──────────────────────────────────────────────────────────────

def _ensure_data_dir():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)


def _load_data():
    """Load the latest sync snapshot. Returns dict or None."""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_data(payload):
    _ensure_data_dir()
    with open(DATA_FILE, 'w') as f:
        json.dump(payload, f, indent=2, default=str)


def _fmt(amount):
    """Format integer amount with thousand separators."""
    if amount is None:
        return '0'
    try:
        return f'{int(float(amount)):,}'
    except (ValueError, TypeError):
        return '0'


# ── API endpoint (receives sync from local POS) ─────────────────────────

@app.route('/api/sync', methods=['POST'])
def api_sync():
    key = request.headers.get('X-API-Key', '')
    if key != API_KEY:
        return jsonify({'ok': False, 'error': 'Invalid API key.'}), 403

    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({'ok': False, 'error': 'Empty payload.'}), 400

        payload['received_at'] = datetime.utcnow().isoformat()
        _save_data(payload)

        return jsonify({'ok': True, 'message': 'Sync received.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Health check ─────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    data = _load_data()
    return jsonify({
        'ok': True,
        'has_data': data is not None,
        'last_sync': data.get('synced_at') if data else None,
    })


# ── Dashboard ────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    data = _load_data()
    return render_template('dashboard.html', data=data, fmt=_fmt)


# ── Run (dev only — Render uses gunicorn) ────────────────────────────────

if __name__ == '__main__':
    _ensure_data_dir()
    app.run(debug=True, port=5050)
