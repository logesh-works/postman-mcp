"""A minimal Flask payments API, mounted on a blueprint.

Run it:
    pip install -r requirements.txt
    flask --app app run

The blueprint is mounted under ``/payments`` in a separate ``register_blueprint`` call,
so this example also demonstrates the structural resolver: reading only the
``@bp.route(...)`` decorator would give you ``/`` and ``/<payment_id>``, not the real
``/payments`` and ``/payments/<payment_id>`` Postman needs to hit.
"""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, Flask, jsonify, request

app = Flask(__name__)
bp = Blueprint("payments", __name__)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not request.headers.get("Authorization"):
            return jsonify({"error": "Not authenticated"}), 401
        return fn(*args, **kwargs)

    return wrapper


@bp.route("/", methods=["POST"])
@login_required
def create_payment():
    """Create a new payment."""
    amount = request.json.get("amount")
    currency = request.json.get("currency")
    return jsonify({"id": "pay_abc123", "amount": amount, "currency": currency, "status": "succeeded"}), 201


@bp.get("/<payment_id>")
@login_required
def get_payment(payment_id):
    """Fetch a single payment by id."""
    return jsonify({"id": payment_id, "amount": 4200, "currency": "USD", "status": "succeeded"})


@bp.route("/<payment_id>", methods=["DELETE"])
@login_required
def refund_payment(payment_id):
    """Refund (delete) a payment by id."""
    return "", 204


app.register_blueprint(bp, url_prefix="/payments")
