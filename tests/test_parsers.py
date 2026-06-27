"""Framework code parsers — Path B fallback (PRD §9.4)."""

from __future__ import annotations

from postman_mcp.input.parsers import express as express_parser
from postman_mcp.input.parsers import fastapi as fastapi_parser
from postman_mcp.models import FieldType, InputSource


# --- FastAPI (AST-based, version-agnostic) -----------------------------------------

FASTAPI_SRC = '''
from fastapi import Depends, FastAPI
from pydantic import BaseModel

app = FastAPI()


def get_current_user(token: str = ""):
    return token


class PaymentRequest(BaseModel):
    amount: int
    currency: str
    note: str = "n/a"


class PaymentResponse(BaseModel):
    id: str
    status: str


@app.post("/payments", response_model=PaymentResponse)
def create_payment(body: PaymentRequest, user=Depends(get_current_user)):
    """Create a payment."""
    return body


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str, verbose: bool = False):
    """Fetch a payment."""
    return {}
'''


def _write(tmp_path, name, src):
    (tmp_path / name).write_text(src, encoding="utf-8")


def test_fastapi_parser_extracts_routes(tmp_path):
    _write(tmp_path, "app.py", FASTAPI_SRC)
    routes, skipped = fastapi_parser.parse(tmp_path)
    assert skipped == []
    by_key = {r.key: r for r in routes}
    assert "POST:/payments" in by_key
    assert "GET:/payments/{param}" in by_key


def test_fastapi_parser_reads_body_auth_and_docstring(tmp_path):
    _write(tmp_path, "app.py", FASTAPI_SRC)
    routes = {r.key: r for r in fastapi_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    assert post.source is InputSource.CODE
    assert post.auth_required is True
    assert post.docstring == "Create a payment."
    field_names = {f.name for f in post.body.fields}
    assert {"amount", "currency", "note"} == field_names
    amount = next(f for f in post.body.fields if f.name == "amount")
    assert amount.type is FieldType.INTEGER
    # response_model resolved
    resp = post.responses[0]
    assert resp.status == 201
    assert {f.name for f in resp.body.fields} == {"id", "status"}


def test_fastapi_parser_path_and_query_params(tmp_path):
    _write(tmp_path, "app.py", FASTAPI_SRC)
    routes = {r.key: r for r in fastapi_parser.parse(tmp_path)[0]}
    get = routes["GET:/payments/{param}"]
    assert [p.name for p in get.path_params] == ["payment_id"]
    assert [p.name for p in get.query_params] == ["verbose"]
    assert get.auth_required is False


def test_fastapi_parser_skips_syntax_error(tmp_path):
    _write(tmp_path, "broken.py", "def oops(:\n")
    _write(tmp_path, "app.py", FASTAPI_SRC)
    routes, skipped = fastapi_parser.parse(tmp_path)
    assert any("broken.py" in s for s in skipped)
    # the good file still parsed
    assert routes


# --- Express (regex/heuristic, low confidence) -------------------------------------

EXPRESS_SRC = """
const express = require('express');
const app = express();

app.post('/payments', requireAuth, (req, res) => {
  const amount = req.body.amount;
  const currency = req.body.currency;
  res.status(201).json({ id: 'pay_1' });
});

app.get('/payments/:id', (req, res) => {
  res.json({ id: req.params.id });
});
"""


def test_express_parser_extracts_routes(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_SRC)
    routes, skipped = express_parser.parse(tmp_path)
    assert skipped == []
    by_key = {r.key: r for r in routes}
    assert "POST:/payments" in by_key
    assert "GET:/payments/{param}" in by_key


def test_express_post_is_low_confidence_with_body_fields(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_SRC)
    routes = {r.key: r for r in express_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    assert post.auth_required is True  # requireAuth middleware detected
    assert post.body.low_confidence is True
    assert {f.name for f in post.body.fields} == {"amount", "currency"}


def test_express_get_has_no_body(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_SRC)
    routes = {r.key: r for r in express_parser.parse(tmp_path)[0]}
    get = routes["GET:/payments/{param}"]
    assert get.body is None
    assert [p.name for p in get.path_params] == ["id"]
