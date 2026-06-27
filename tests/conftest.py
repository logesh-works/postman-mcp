"""Shared fixtures for the Postman MCP test suite.

All tests are offline: the Postman REST API is never called here. Fixtures build the
in-memory contracts (route models, collections, specs) the pure logic operates on.
"""

from __future__ import annotations

import pytest

from postman_mcp.models import (
    BodyField,
    BodyModel,
    FieldType,
    InputSource,
    Param,
    ParamLocation,
    ResponseModel,
    RouteModel,
)


@pytest.fixture
def payment_body() -> BodyModel:
    return BodyModel(
        name="PaymentRequest",
        fields=[
            BodyField(name="amount", type=FieldType.INTEGER, required=True),
            BodyField(name="currency", type=FieldType.STRING, required=True),
            BodyField(name="method", type=FieldType.STRING, required=True),
        ],
    )


@pytest.fixture
def create_payment_route(payment_body: BodyModel) -> RouteModel:
    return RouteModel(
        method="POST",
        path="/payments",
        body=payment_body,
        responses=[ResponseModel(status=201, description="Created")],
        auth_required=True,
        docstring="Create a new payment.",
        source=InputSource.OPENAPI,
    )


@pytest.fixture
def get_payment_route() -> RouteModel:
    return RouteModel(
        method="GET",
        path="/payments/{payment_id}",
        path_params=[Param(name="payment_id", location=ParamLocation.PATH, required=True)],
        source=InputSource.CODE,
    )


@pytest.fixture
def empty_collection() -> dict:
    return {"info": {"name": "Acme Backend"}, "item": []}


@pytest.fixture
def openapi_spec() -> dict:
    """A small but realistic OpenAPI 3.x doc exercising $ref, allOf, and security."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Acme Payments", "version": "1.0.0"},
        "components": {
            "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}},
            "schemas": {
                "Money": {
                    "type": "object",
                    "properties": {"amount": {"type": "integer"}},
                    "required": ["amount"],
                },
                "PaymentRequest": {
                    "allOf": [
                        {"$ref": "#/components/schemas/Money"},
                        {
                            "type": "object",
                            "properties": {
                                "currency": {"type": "string"},
                                "method": {"type": "string"},
                            },
                            "required": ["currency"],
                        },
                    ]
                },
                "PaymentResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
            },
        },
        "security": [{"bearer": []}],
        "paths": {
            "/payments": {
                "post": {
                    "summary": "Create a payment",
                    "operationId": "create_payment",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PaymentRequest"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PaymentResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/payments/{payment_id}": {
                "parameters": [
                    {"name": "payment_id", "in": "path", "required": True,
                     "schema": {"type": "string"}}
                ],
                "get": {
                    "summary": "Fetch a payment",
                    "operationId": "get_payment",
                    "responses": {"200": {"description": "OK"}},
                },
            },
        },
    }
