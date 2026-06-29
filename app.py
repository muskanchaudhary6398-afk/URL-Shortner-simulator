"""
api/app.py

Minimal Flask API around URLShortener -- exposes link creation, redirection,
and analytics over HTTP so the simulator can be used like a real shortening
service (e.g. with curl, Postman, or a frontend).

Endpoints:
    POST /api/shorten        body: {"url": "https://..."}    -> {"short_code", "short_url"}
    GET  /<code>                                              -> 302 redirect to the original URL
    GET  /api/analytics/<code>                                -> per-link stats
    GET  /api/stats                                            -> overall summary + leaderboard

Run:
    python api/app.py
    curl -X POST localhost:5000/api/shorten -H "Content-Type: application/json" \
         -d '{"url": "https://example.com/some/very/long/path"}'
"""

from flask import Flask, request, jsonify, redirect

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.shortener import URLShortener
from storage.persistence import SQLiteStore
from analytics.tracker import AnalyticsTracker

app = Flask(__name__)
shortener = URLShortener(store=SQLiteStore("url_shortener.db"))
tracker = AnalyticsTracker(shortener)

BASE_URL = "http://localhost:5000"


@app.route("/api/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True) or {}
    long_url = data.get("url")
    if not long_url:
        return jsonify({"error": "missing 'url' field"}), 400

    code = shortener.shorten(long_url)
    return jsonify({
        "short_code": code,
        "short_url": f"{BASE_URL}/{code}",
        "long_url": long_url,
    }), 201


@app.route("/<code>")
def redirect_to_long_url(code):
    long_url = shortener.resolve(code)
    if long_url is None:
        return jsonify({"error": "short code not found"}), 404
    return redirect(long_url, code=302)


@app.route("/api/analytics/<code>")
def analytics(code):
    stats = tracker.get_link_stats(code)
    if stats is None:
        return jsonify({"error": "short code not found"}), 404
    return jsonify(stats.as_dict())


@app.route("/api/stats")
def overall_stats():
    return jsonify(tracker.summary())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
