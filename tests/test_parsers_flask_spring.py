"""Flask (blueprint composition) and Spring (class+method mapping composition) parsers."""

from __future__ import annotations

from postman_mcp.input.parsers import flask as flask_parser
from postman_mcp.input.parsers import spring as spring_parser
from postman_mcp.models import FieldType, InputSource


def _write(tmp_path, name, src):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")


# --- Flask --------------------------------------------------------------------------


def test_flask_app_route_methods_kwarg(tmp_path):
    _write(
        tmp_path,
        "app.py",
        """
from flask import Flask, request

app = Flask(__name__)


@app.route('/payments', methods=['POST'])
def create_payment():
    amount = request.json['amount']
    currency = request.json.get('currency')
    return {}


@app.route('/payments/<int:payment_id>')
def get_payment(payment_id):
    return {}
""",
    )
    routes = {r.key: r for r in flask_parser.parse(tmp_path)[0]}
    assert "POST:/payments" in routes
    assert "GET:/payments/{param}" in routes
    post = routes["POST:/payments"]
    assert post.source is InputSource.CODE
    assert post.body.low_confidence is True
    assert {f.name for f in post.body.fields} == {"amount", "currency"}
    get = routes["GET:/payments/{param}"]
    assert [p.name for p in get.path_params] == ["payment_id"]


def test_flask_blueprint_prefix_composition(tmp_path):
    # Blueprint(url_prefix='/users') + register_blueprint(url_prefix='/api/v1'), cross-file
    _write(
        tmp_path,
        "app.py",
        """
from flask import Flask
from users.routes import bp

app = Flask(__name__)
app.register_blueprint(bp, url_prefix='/api/v1')
""",
    )
    _write(tmp_path, "users/__init__.py", "")
    _write(
        tmp_path,
        "users/routes.py",
        """
from flask import Blueprint, request

bp = Blueprint('users', __name__, url_prefix='/users')


@bp.get('/<user_id>')
def get_user(user_id):
    return {}


@bp.post('/')
@login_required
def create_user():
    name = request.json['name']
    return {}
""",
    )
    routes = {r.key: r for r in flask_parser.parse(tmp_path)[0]}
    # /api/v1 + /users + leaf
    assert "GET:/api/v1/users/{param}" in routes
    assert "POST:/api/v1/users" in routes
    assert routes["POST:/api/v1/users"].auth_required is True


def test_flask_skips_syntax_error(tmp_path):
    _write(tmp_path, "broken.py", "def (:\n")
    routes, skipped = flask_parser.parse(tmp_path)
    assert any("broken.py" in s for s in skipped)


# --- Spring -------------------------------------------------------------------------

SPRING_DTO = """
package com.acme.api;

public class PaymentRequest {
    private String currency;
    private Integer amount;
    private boolean recurring;
}
"""

SPRING_CONTROLLER = """
package com.acme.api;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/payments")
public class PaymentController {

    @PostMapping
    public Payment create(@RequestBody PaymentRequest req) {
        return null;
    }

    @GetMapping("/{id}")
    public Payment get(@PathVariable String id) {
        return null;
    }

    @RequestMapping(value = "/search", method = RequestMethod.GET)
    public Object search() {
        return null;
    }
}
"""


def test_spring_class_and_method_mapping_compose(tmp_path):
    _write(tmp_path, "PaymentRequest.java", SPRING_DTO)
    _write(tmp_path, "PaymentController.java", SPRING_CONTROLLER)
    routes = {r.key: r for r in spring_parser.parse(tmp_path)[0]}
    assert "POST:/api/v1/payments" in routes
    assert "GET:/api/v1/payments/{param}" in routes  # /{id}
    assert "GET:/api/v1/payments/search" in routes


def test_spring_request_body_resolves_dto_fields(tmp_path):
    _write(tmp_path, "PaymentRequest.java", SPRING_DTO)
    _write(tmp_path, "PaymentController.java", SPRING_CONTROLLER)
    routes = {r.key: r for r in spring_parser.parse(tmp_path)[0]}
    post = routes["POST:/api/v1/payments"]
    fields = {f.name: f.type for f in post.body.fields}
    assert fields == {
        "currency": FieldType.STRING,
        "amount": FieldType.INTEGER,
        "recurring": FieldType.BOOLEAN,
    }


def test_spring_context_path_prepended(tmp_path):
    _write(tmp_path, "src/main/resources/application.properties", "server.servlet.context-path=/svc\n")
    _write(tmp_path, "PaymentController.java", SPRING_CONTROLLER)
    routes = {r.key for r in spring_parser.parse(tmp_path)[0]}
    assert "POST:/svc/api/v1/payments" in routes
