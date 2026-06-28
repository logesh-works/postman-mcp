"""Framework code parsers — Path B fallback."""

from __future__ import annotations

from postman_mcp.input.parsers import express as express_parser
from postman_mcp.input.parsers import fastapi as fastapi_parser
from postman_mcp.models import FieldType, InputSource, ParamLocation


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


FASTAPI_HEADER_SRC = '''
from fastapi import FastAPI, Header
from typing import Optional

app = FastAPI()


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str, x_api_key: str = Header(...), x_trace_id: Optional[str] = Header(None)):
    """Fetch a payment."""
    return {}
'''


def test_fastapi_parser_reads_header_params(tmp_path):
    _write(tmp_path, "app.py", FASTAPI_HEADER_SRC)
    routes = {r.key: r for r in fastapi_parser.parse(tmp_path)[0]}
    get = routes["GET:/payments/{param}"]
    headers = {h.name: h for h in get.headers}
    assert set(headers) == {"X-Api-Key", "X-Trace-Id"}
    assert headers["X-Api-Key"].location is ParamLocation.HEADER
    assert headers["X-Api-Key"].required is True
    assert headers["X-Trace-Id"].required is False


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


EXPRESS_DESTRUCTURE_SRC = """
const express = require('express');
const app = express();

app.post('/payments', requireAuth, (req, res) => {
  const { amount, currency: curr, method = 'card', ...rest } = req.body;
  res.status(201).json({ id: 'pay_1' });
});
"""


def test_express_destructured_body_fields_are_extracted(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_DESTRUCTURE_SRC)
    routes = {r.key: r for r in express_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    # aliased/defaulted fields resolve to their original key; the rest-spread is dropped
    assert {f.name for f in post.body.fields} == {"amount", "currency", "method"}
    assert post.body.low_confidence is True  # still just inferred from usage


EXPRESS_JSDOC_SRC = """
const express = require('express');
const app = express();

/**
 * Create a new payment.
 * @route POST /payments
 * @body {number} amount   Amount in minor units
 * @body {string} currency ISO 4217 currency code
 */
app.post('/payments', requireAuth, (req, res) => {
  const { amount, currency } = req.body;
  res.status(201).json({ id: 'pay_1' });
});
"""


def test_express_jsdoc_body_tags_are_high_confidence(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_JSDOC_SRC)
    routes = {r.key: r for r in express_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    assert post.body.low_confidence is False
    fields = {f.name: f.type for f in post.body.fields}
    assert fields == {"amount": FieldType.NUMBER, "currency": FieldType.STRING}


EXPRESS_JOI_SRC = """
const express = require('express');
const Joi = require('joi');
const app = express();

const paymentSchema = Joi.object({
  amount: Joi.number().required(),
  currency: Joi.string().required(),
});

app.post('/payments', requireAuth, (req, res) => {
  const { error } = paymentSchema.validate(req.body);
  res.status(201).json({ id: 'pay_1' });
});
"""


def test_express_joi_schema_is_high_confidence(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_JOI_SRC)
    routes = {r.key: r for r in express_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    assert post.body.low_confidence is False
    assert {f.name for f in post.body.fields} == {"amount", "currency"}


EXPRESS_INLINE_ZOD_SRC = """
const express = require('express');
const { z } = require('zod');
const app = express();

app.post('/payments', requireAuth, (req, res) => {
  const result = z.object({ amount: z.number(), currency: z.string() }).parse(req.body);
  res.status(201).json({ id: 'pay_1' });
});
"""


def test_express_inline_zod_schema_is_high_confidence(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_INLINE_ZOD_SRC)
    routes = {r.key: r for r in express_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    assert post.body.low_confidence is False
    assert {f.name for f in post.body.fields} == {"amount", "currency"}


EXPRESS_GLOBAL_AUTH_SRC = """
const express = require('express');
const app = express();
app.use(requireAuth);

app.get('/payments/:id', (req, res) => {
  res.json({ id: req.params.id });
});
"""


def test_express_global_use_middleware_marks_auth(tmp_path):
    _write(tmp_path, "app.js", EXPRESS_GLOBAL_AUTH_SRC)
    routes = {r.key: r for r in express_parser.parse(tmp_path)[0]}
    get = routes["GET:/payments/{param}"]
    assert get.auth_required is True  # no inline middleware — only app.use(requireAuth)
