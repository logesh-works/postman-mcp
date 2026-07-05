"""L1 structural resolver — FastAPI mount-chain prefix composition.

These are the cases the old leaf-only parser got wrong: prefixes from
``APIRouter(prefix=...)`` and ``include_router(prefix=...)`` that live in other files.
Each fixture is a realistic multi-file FastAPI layout; we assert the *full* composed URL.
"""

from __future__ import annotations

from pathlib import Path

from postman_mcp.input import structural
from postman_mcp.input.parsers import fastapi as fastapi_parser


def _write(root: Path, name: str, src: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")


def _keys(root: Path) -> set[str]:
    routes, _ = fastapi_parser.parse(root)
    return {r.key for r in routes}


# --- single file: APIRouter(prefix) on the router itself ----------------------------


def test_apirouter_prefix_composes_with_leaf(tmp_path):
    _write(
        tmp_path,
        "app.py",
        """
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter(prefix="/users")


@router.get("/{user_id}")
def get_user(user_id: str):
    return {}


app.include_router(router)
""",
    )
    assert "GET:/users/{param}" in _keys(tmp_path)


def test_include_router_prefix_stacks_on_router_prefix(tmp_path):
    # include_router(prefix="/api/v1") + APIRouter(prefix="/users") + leaf "/" → /api/v1/users
    _write(
        tmp_path,
        "app.py",
        """
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter(prefix="/users")


@router.post("/")
def create_user():
    return {}


app.include_router(router, prefix="/api/v1")
""",
    )
    assert "POST:/api/v1/users" in _keys(tmp_path)


# --- cross-file: the dominant real layout (routers in their own modules) ------------

MAIN = """
from fastapi import FastAPI
from app.routers import users, payments

app = FastAPI()
app.include_router(users.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
"""

USERS = """
from fastapi import APIRouter

router = APIRouter(prefix="/users")


@router.get("/{user_id}")
def get_user(user_id: str):
    return {}


@router.post("/")
def create_user():
    return {}
"""

PAYMENTS = """
from fastapi import APIRouter

router = APIRouter(prefix="/payments")


@router.get("/{payment_id}")
def get_payment(payment_id: str):
    return {}
"""


def test_cross_file_include_router_composes_full_paths(tmp_path):
    _write(tmp_path, "app/main.py", MAIN)
    _write(tmp_path, "app/routers/__init__.py", "")
    _write(tmp_path, "app/routers/users.py", USERS)
    _write(tmp_path, "app/routers/payments.py", PAYMENTS)
    keys = _keys(tmp_path)
    assert "GET:/api/v1/users/{param}" in keys
    assert "POST:/api/v1/users" in keys
    assert "GET:/api/v1/payments/{param}" in keys


def test_cross_file_aliased_symbol_import(tmp_path):
    # `from .routers.users import router as users_router` then include_router(users_router)
    _write(
        tmp_path,
        "app/main.py",
        """
from fastapi import FastAPI
from app.routers.users import router as users_router

app = FastAPI()
app.include_router(users_router, prefix="/api")
""",
    )
    _write(tmp_path, "app/routers/__init__.py", "")
    _write(tmp_path, "app/routers/users.py", USERS)
    keys = _keys(tmp_path)
    assert "GET:/api/users/{param}" in keys
    assert "POST:/api/users" in keys


def test_relative_import_include(tmp_path):
    # main.py uses a relative `from .routers import users`
    _write(
        tmp_path,
        "app/main.py",
        """
from fastapi import FastAPI
from .routers import users

app = FastAPI()
app.include_router(users.router, prefix="/api/v2")
""",
    )
    _write(tmp_path, "app/__init__.py", "")
    _write(tmp_path, "app/routers/__init__.py", "")
    _write(tmp_path, "app/routers/users.py", USERS)
    assert "GET:/api/v2/users/{param}" in _keys(tmp_path)


# --- nested routers: router includes a sub-router, then app includes the router ------


def test_nested_three_level_mount(tmp_path):
    _write(
        tmp_path,
        "app/main.py",
        """
from fastapi import FastAPI
from app.api import api_router

app = FastAPI()
app.include_router(api_router, prefix="/api")
""",
    )
    _write(tmp_path, "app/__init__.py", "")
    _write(
        tmp_path,
        "app/api/__init__.py",
        """
from fastapi import APIRouter
from app.api.users import router as users_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(users_router)
""",
    )
    _write(
        tmp_path,
        "app/api/users.py",
        """
from fastapi import APIRouter

router = APIRouter(prefix="/users")


@router.get("/{user_id}")
def get_user(user_id: str):
    return {}
""",
    )
    # /api  +  /v1  +  /users  +  /{user_id}
    assert "GET:/api/v1/users/{param}" in _keys(tmp_path)


# --- backward compatibility: plain @app.post with no router is unchanged -------------


def test_plain_app_routes_unchanged(tmp_path):
    _write(
        tmp_path,
        "app.py",
        """
from fastapi import FastAPI

app = FastAPI()


@app.post("/payments")
def create_payment():
    return {}
""",
    )
    assert "POST:/payments" in _keys(tmp_path)


# --- known-unknown: orphan router (defined, never mounted) is flagged unresolved -----


def test_orphan_router_is_unresolved(tmp_path):
    _write(
        tmp_path,
        "app/routers/orphan.py",
        """
from fastapi import APIRouter

router = APIRouter(prefix="/orphan")


@router.get("/x")
def x():
    return {}
""",
    )
    structure = structural.build_fastapi(tmp_path)
    resolved = structure.prefix("app.routers.orphan", "router")
    # We still apply the router's own prefix, but flag that we could not confirm a mount.
    assert resolved.prefix == "/orphan"
    assert resolved.resolved is False


# --- unit-level checks on the composition primitive ---------------------------------


def test_compose_handles_slashes():
    assert structural.compose("/api/v1", "/users") == "/api/v1/users"
    assert structural.compose("/api/v1", "users") == "/api/v1/users"
    assert structural.compose("/users", "/") == "/users"
    assert structural.compose("", "/payments") == "/payments"
    assert structural.compose("/api/", "/users/") == "/api/users/"
