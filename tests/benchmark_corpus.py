"""Accuracy benchmark corpus — realistic, varied multi-file apps per framework.

Each entry is a *whole mini-application* (multiple files, the way real projects are laid
out) paired with its ground-truth set of routes as ``METHOD:normalized_path`` keys. The
benchmark scores the parser's extracted routes against this truth (see
``test_accuracy.py``). The corpus deliberately spans many "kinds":

- single-file apps and multi-file/package layouts
- router/blueprint prefixes + mount prefixes (cross-file)
- multi-level nested mounts
- path params, multiple HTTP methods per resource
- plain app-level routes alongside mounted routers
- framework-global prefixes (Nest ``setGlobalPrefix``, Spring ``context-path``)
"""

from __future__ import annotations

from postman_mcp.models import normalize_path


def key(method: str, path: str) -> str:
    return f"{method.upper()}:{normalize_path(path)}"


# --- FastAPI ------------------------------------------------------------------------

FASTAPI_FILES = {
    "main.py": """
from fastapi import FastAPI
from routers import users, payments
from routers.admin import admin_router

app = FastAPI()


@app.get("/health")
def health():
    return {}


app.include_router(users.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(admin_router)
""",
    "routers/__init__.py": "",
    "routers/users.py": """
from fastapi import APIRouter

router = APIRouter(prefix="/users")


@router.get("/")
def list_users():
    return []


@router.post("/")
def create_user():
    return {}


@router.get("/{user_id}")
def get_user(user_id: str):
    return {}


@router.put("/{user_id}")
def update_user(user_id: str):
    return {}


@router.delete("/{user_id}")
def delete_user(user_id: str):
    return {}
""",
    "routers/payments.py": """
from fastapi import APIRouter

router = APIRouter(prefix="/payments")


@router.get("/")
def list_payments():
    return []


@router.post("/")
def create_payment():
    return {}
""",
    "routers/admin/__init__.py": """
from fastapi import APIRouter
from routers.admin.reports import router as reports_router

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(reports_router)
""",
    "routers/admin/reports.py": """
from fastapi import APIRouter

router = APIRouter(prefix="/reports")


@router.get("/")
def list_reports():
    return []
""",
}

FASTAPI_EXPECTED = {
    key("GET", "/health"),
    key("GET", "/api/v1/users"),
    key("POST", "/api/v1/users"),
    key("GET", "/api/v1/users/{id}"),
    key("PUT", "/api/v1/users/{id}"),
    key("DELETE", "/api/v1/users/{id}"),
    key("GET", "/api/v1/payments"),
    key("POST", "/api/v1/payments"),
    key("GET", "/admin/reports"),
}


# --- Flask --------------------------------------------------------------------------

FLASK_FILES = {
    "app.py": """
from flask import Flask
from users.routes import bp as users_bp
from orders.routes import bp as orders_bp

app = Flask(__name__)


@app.get("/health")
def health():
    return {}


app.register_blueprint(users_bp, url_prefix="/api")
app.register_blueprint(orders_bp, url_prefix="/api")
""",
    "users/__init__.py": "",
    "users/routes.py": """
from flask import Blueprint

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.route("/", methods=["GET", "POST"])
def collection():
    return {}


@bp.get("/<user_id>")
def get_user(user_id):
    return {}


@bp.put("/<user_id>")
def update_user(user_id):
    return {}
""",
    "orders/__init__.py": "",
    "orders/routes.py": """
from flask import Blueprint

bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.get("/")
def list_orders():
    return {}


@bp.post("/")
def create_order():
    return {}
""",
}

FLASK_EXPECTED = {
    key("GET", "/health"),
    key("GET", "/api/users"),
    key("POST", "/api/users"),
    key("GET", "/api/users/{id}"),
    key("PUT", "/api/users/{id}"),
    key("GET", "/api/orders"),
    key("POST", "/api/orders"),
}


# --- Django -------------------------------------------------------------------------

DJANGO_FILES = {
    "urls.py": """
from django.urls import path, include

urlpatterns = [
    path("api/", include("api.urls")),
]
""",
    "api/__init__.py": "",
    "api/urls.py": """
from django.urls import path, include

urlpatterns = [
    path("users/", include("users.urls")),
    path("payments/", include("payments.urls")),
]
""",
    "users/__init__.py": "",
    "users/views.py": """
from rest_framework import viewsets


class UserViewSet(viewsets.ViewSet):
    def list(self, request):
        return None

    def create(self, request):
        return None

    def retrieve(self, request, pk=None):
        return None
""",
    "users/urls.py": """
from django.urls import path
from users.views import UserViewSet

urlpatterns = [
    path("", UserViewSet.as_view({"get": "list", "post": "create"})),
    path("<int:pk>/", UserViewSet.as_view({"get": "retrieve"})),
]
""",
    "payments/__init__.py": "",
    "payments/views.py": """
from rest_framework.decorators import api_view


@api_view(["GET", "POST"])
def payment_list(request):
    return None
""",
    "payments/urls.py": """
from django.urls import path
from payments.views import payment_list

urlpatterns = [
    path("", payment_list),
]
""",
}

DJANGO_EXPECTED = {
    key("GET", "/api/users"),
    key("POST", "/api/users"),
    key("GET", "/api/users/{pk}"),
    key("GET", "/api/payments"),
    key("POST", "/api/payments"),
}


# --- Express ------------------------------------------------------------------------

EXPRESS_FILES = {
    "app.js": """
const express = require('express');
const app = express();

const usersRouter = require('./routes/users');
const paymentsRouter = require('./routes/payments');

app.get('/health', (req, res) => res.json({}));
app.use('/api/users', usersRouter);
app.use('/api/payments', paymentsRouter);
""",
    "routes/users.js": """
const express = require('express');
const router = express.Router();

router.get('/', (req, res) => res.json([]));
router.post('/', (req, res) => res.status(201).json({}));
router.get('/:id', (req, res) => res.json({}));
router.put('/:id', (req, res) => res.json({}));
router.delete('/:id', (req, res) => res.status(204).end());

module.exports = router;
""",
    "routes/payments.js": """
const express = require('express');
const router = express.Router();

router.get('/', (req, res) => res.json([]));
router.post('/', (req, res) => res.status(201).json({}));

module.exports = router;
""",
}

EXPRESS_EXPECTED = {
    key("GET", "/health"),
    key("GET", "/api/users"),
    key("POST", "/api/users"),
    key("GET", "/api/users/{id}"),
    key("PUT", "/api/users/{id}"),
    key("DELETE", "/api/users/{id}"),
    key("GET", "/api/payments"),
    key("POST", "/api/payments"),
}


# --- NestJS -------------------------------------------------------------------------

NESTJS_FILES = {
    "main.ts": """
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.setGlobalPrefix('api');
  await app.listen(3000);
}
bootstrap();
""",
    "users.controller.ts": """
import { Controller, Get, Post, Put, Delete } from '@nestjs/common';

@Controller('users')
export class UsersController {
  @Get()
  list() {}

  @Post()
  create() {}

  @Get(':id')
  get() {}

  @Put(':id')
  update() {}

  @Delete(':id')
  remove() {}
}
""",
    "payments.controller.ts": """
import { Controller, Get, Post } from '@nestjs/common';

@Controller('payments')
export class PaymentsController {
  @Get()
  list() {}

  @Post()
  create() {}
}
""",
}

NESTJS_EXPECTED = {
    key("GET", "/api/users"),
    key("POST", "/api/users"),
    key("GET", "/api/users/{id}"),
    key("PUT", "/api/users/{id}"),
    key("DELETE", "/api/users/{id}"),
    key("GET", "/api/payments"),
    key("POST", "/api/payments"),
}


# --- Spring -------------------------------------------------------------------------

SPRING_FILES = {
    "src/main/resources/application.properties": "server.servlet.context-path=/api\n",
    "src/main/java/com/acme/UserController.java": """
package com.acme;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/users")
public class UserController {

    @GetMapping
    public Object list() { return null; }

    @PostMapping
    public Object create(@RequestBody UserDto dto) { return null; }

    @GetMapping("/{id}")
    public Object get(@PathVariable String id) { return null; }

    @PutMapping("/{id}")
    public Object update(@PathVariable String id) { return null; }

    @DeleteMapping("/{id}")
    public Object remove(@PathVariable String id) { return null; }
}
""",
    "src/main/java/com/acme/PaymentController.java": """
package com.acme;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/payments")
public class PaymentController {

    @GetMapping
    public Object list() { return null; }

    @RequestMapping(value = "/search", method = RequestMethod.GET)
    public Object search() { return null; }
}
""",
    "src/main/java/com/acme/UserDto.java": """
package com.acme;

public class UserDto {
    private String name;
    private String email;
}
""",
}

SPRING_EXPECTED = {
    key("GET", "/api/users"),
    key("POST", "/api/users"),
    key("GET", "/api/users/{id}"),
    key("PUT", "/api/users/{id}"),
    key("DELETE", "/api/users/{id}"),
    key("GET", "/api/payments"),
    key("GET", "/api/payments/search"),
}


CORPUS = {
    "fastapi": (FASTAPI_FILES, FASTAPI_EXPECTED),
    "flask": (FLASK_FILES, FLASK_EXPECTED),
    "django": (DJANGO_FILES, DJANGO_EXPECTED),
    "express": (EXPRESS_FILES, EXPRESS_EXPECTED),
    "nestjs": (NESTJS_FILES, NESTJS_EXPECTED),
    "spring": (SPRING_FILES, SPRING_EXPECTED),
}


# ====================================================================================
# HARD corpus — messy, real-world patterns that the leaf-only reader gets wrong.
# ====================================================================================

# --- Django REST Framework routers (the dominant real DRF pattern) ------------------

DJANGO_DRF_FILES = {
    "urls.py": """
from django.urls import path, include

urlpatterns = [
    path("api/v1/", include("catalog.urls")),
]
""",
    "catalog/__init__.py": "",
    "catalog/views.py": """
from rest_framework import viewsets


class ProductViewSet(viewsets.ModelViewSet):
    pass


class TagViewSet(viewsets.ViewSet):
    def list(self, request):
        return None

    def retrieve(self, request, pk=None):
        return None
""",
    "catalog/urls.py": """
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from catalog.views import ProductViewSet, TagViewSet

router = DefaultRouter()
router.register("products", ProductViewSet)
router.register("tags", TagViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
""",
}

DJANGO_DRF_EXPECTED = {
    # ProductViewSet is a ModelViewSet → full CRUD
    key("GET", "/api/v1/products"),
    key("POST", "/api/v1/products"),
    key("GET", "/api/v1/products/{pk}"),
    key("PUT", "/api/v1/products/{pk}"),
    key("PATCH", "/api/v1/products/{pk}"),
    key("DELETE", "/api/v1/products/{pk}"),
    # TagViewSet only defines list + retrieve
    key("GET", "/api/v1/tags"),
    key("GET", "/api/v1/tags/{pk}"),
}

# --- FastAPI: router with no own prefix; prefix only at include; double-versioned ----

FASTAPI_VARIED_FILES = {
    "main.py": """
from fastapi import FastAPI
from items import router as items_router

app = FastAPI()

# Same router mounted under two version prefixes (a real versioning pattern).
app.include_router(items_router, prefix="/v1")
app.include_router(items_router, prefix="/v2")
""",
    "items.py": """
from fastapi import APIRouter

router = APIRouter()  # no own prefix; prefix supplied entirely at include time


@router.get("/items")
def list_items():
    return []


@router.get("/items/{item_id}")
def get_item(item_id: str):
    return {}
""",
}

FASTAPI_VARIED_EXPECTED = {
    key("GET", "/v1/items"),
    key("GET", "/v1/items/{id}"),
    key("GET", "/v2/items"),
    key("GET", "/v2/items/{id}"),
}

# --- Express: arbitrary router variable names, app.use without prefix ----------------

EXPRESS_VARIED_FILES = {
    "server.js": """
const express = require('express');
const app = express();

const authRoutes = require('./auth');
const v1 = require('./api/v1');

app.use(authRoutes);            // mounted with NO prefix
app.use('/api/v1', v1);
""",
    "auth.js": """
const express = require('express');
const authRouter = express.Router();

authRouter.post('/login', (req, res) => res.json({}));
authRouter.post('/logout', (req, res) => res.json({}));

module.exports = authRouter;
""",
    "api/v1.js": """
const express = require('express');
const r = express.Router();

r.get('/orders', (req, res) => res.json([]));
r.get('/orders/:id', (req, res) => res.json({}));

module.exports = r;
""",
}

EXPRESS_VARIED_EXPECTED = {
    key("POST", "/login"),
    key("POST", "/logout"),
    key("GET", "/api/v1/orders"),
    key("GET", "/api/v1/orders/{id}"),
}


HARD_CORPUS = {
    "django_drf": (DJANGO_DRF_FILES, DJANGO_DRF_EXPECTED, "django"),
    "fastapi_varied": (FASTAPI_VARIED_FILES, FASTAPI_VARIED_EXPECTED, "fastapi"),
    "express_varied": (EXPRESS_VARIED_FILES, EXPRESS_VARIED_EXPECTED, "express"),
}
