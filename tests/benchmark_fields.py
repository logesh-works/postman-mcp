"""Field-level accuracy corpus — exercises every extracted dimension.

Beyond the route URL, each app declares typed/validated request bodies, path/query/header
params, auth, and response status codes, with full per-route ground truth. ``R(...)``
builds an expectation; absent dimensions default to empty / no-auth / the success status.
Scored by ``test_field_accuracy.py``.
"""

from __future__ import annotations

from postman_mcp.models import normalize_path


def key(method: str, path: str) -> str:
    return f"{method.upper()}:{normalize_path(path)}"


def R(auth=False, body=None, path_params=None, query_params=None, headers=None, responses=None):
    return {
        "auth": auth,
        "body": set(body or ()),
        "path_params": set(path_params or ()),
        "query_params": set(query_params or ()),
        "headers": set(headers or ()),
        "responses": set(responses or ()),
    }


# --- FastAPI ------------------------------------------------------------------------

FASTAPI_FILES = {
    "main.py": """
from fastapi import FastAPI
from routers import users

app = FastAPI()
app.include_router(users.router, prefix="/api")
""",
    "models.py": """
from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    email: str
    age: int


class UserOut(BaseModel):
    id: str
    name: str
""",
    "routers/__init__.py": "",
    "routers/users.py": """
from fastapi import APIRouter, Depends, Header
from models import UserCreate, UserOut


def get_current_user():
    return None


router = APIRouter(prefix="/users")


@router.get("/")
def list_users(limit: int = 10):
    return []


@router.post("/", response_model=UserOut)
def create_user(body: UserCreate, user=Depends(get_current_user)):
    return {}


@router.get("/{user_id}")
def get_user(user_id: str, verbose: bool = False, x_api_key: str = Header(...)):
    return {}
""",
}

FASTAPI_EXPECTED = {
    key("GET", "/api/users"): R(query_params={"limit"}, responses={200}),
    key("POST", "/api/users"): R(auth=True, body={"name", "email", "age"}, responses={201}),
    key("GET", "/api/users/{id}"): R(
        path_params={"user_id"}, query_params={"verbose"}, headers={"X-Api-Key"},
        responses={200},
    ),
}


# --- NestJS -------------------------------------------------------------------------

NESTJS_FILES = {
    "main.ts": """
import { NestFactory } from '@nestjs/core';
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.setGlobalPrefix('api');
  await app.listen(3000);
}
bootstrap();
""",
    "users.controller.ts": """
import { Controller, Get, Post, Body, Param, Headers, UseGuards } from '@nestjs/common';

class CreateUserDto {
  name: string;
  email: string;
  age: number;
}

@Controller('users')
@UseGuards(AuthGuard)
export class UsersController {
  @Post()
  create(@Body() dto: CreateUserDto) {}

  @Get(':id')
  get(@Param('id') id: string, @Headers('x-api-key') key: string) {}
}
""",
}

NESTJS_EXPECTED = {
    key("POST", "/api/users"): R(auth=True, body={"name", "email", "age"}, responses={201}),
    key("GET", "/api/users/{id}"): R(
        auth=True, path_params={"id"}, headers={"x-api-key"}, responses={200}
    ),
}


# --- Django (DRF ViewSet via router) ------------------------------------------------

DJANGO_FILES = {
    "urls.py": """
from django.urls import path, include

urlpatterns = [path("api/", include("users.urls"))]
""",
    "users/__init__.py": "",
    "users/serializers.py": """
from rest_framework import serializers


class UserSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField()
    age = serializers.IntegerField()
""",
    "users/views.py": """
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from users.serializers import UserSerializer


class UserViewSet(viewsets.ViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return None

    def create(self, request):
        return None

    def retrieve(self, request, pk=None):
        return None
""",
    "users/urls.py": """
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet)

urlpatterns = [path("", include(router.urls))]
""",
}

DJANGO_EXPECTED = {
    key("GET", "/api/users"): R(auth=True, responses={200}),
    key("POST", "/api/users"): R(auth=True, body={"name", "email", "age"}, responses={201}),
    key("GET", "/api/users/{pk}"): R(auth=True, path_params={"pk"}, responses={200}),
}


# --- Express ------------------------------------------------------------------------

EXPRESS_FILES = {
    "app.js": """
const express = require('express');
const app = express();
const usersRouter = require('./routes/users');
app.use('/api/users', usersRouter);
""",
    "routes/users.js": """
const express = require('express');
const Joi = require('joi');
const router = express.Router();

const userSchema = Joi.object({
  name: Joi.string().required(),
  email: Joi.string().required(),
  age: Joi.number(),
});

router.post('/', requireAuth, (req, res) => {
  const { error } = userSchema.validate(req.body);
  res.status(201).json({});
});

router.get('/:id', (req, res) => res.json({}));

module.exports = router;
""",
}

EXPRESS_EXPECTED = {
    key("POST", "/api/users"): R(auth=True, body={"name", "email", "age"}, responses={201}),
    key("GET", "/api/users/{id}"): R(path_params={"id"}, responses={200}),
}


# --- Flask --------------------------------------------------------------------------

FLASK_FILES = {
    "app.py": """
from flask import Flask
from users.routes import bp

app = Flask(__name__)
app.register_blueprint(bp, url_prefix="/api")
""",
    "users/__init__.py": "",
    "users/routes.py": """
from flask import Blueprint, request

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.post("/")
@login_required
def create_user():
    name = request.json["name"]
    email = request.json["email"]
    return {}


@bp.get("/<user_id>")
def get_user(user_id):
    return {}
""",
}

FLASK_EXPECTED = {
    key("POST", "/api/users"): R(auth=True, body={"name", "email"}, responses={201}),
    key("GET", "/api/users/{id}"): R(path_params={"user_id"}, responses={200}),
}


# --- Spring -------------------------------------------------------------------------

SPRING_FILES = {
    "src/main/java/com/acme/UserController.java": """
package com.acme;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @PostMapping
    public Object create(@RequestBody UserDto dto) { return null; }

    @GetMapping("/{id}")
    public Object get(@PathVariable String id) { return null; }
}
""",
    "src/main/java/com/acme/UserDto.java": """
package com.acme;

public class UserDto {
    private String name;
    private String email;
    private Integer age;
}
""",
}

SPRING_EXPECTED = {
    key("POST", "/api/users"): R(body={"name", "email", "age"}, responses={201}),
    key("GET", "/api/users/{id}"): R(path_params={"id"}, responses={200}),
}


FIELD_CORPUS = {
    "fastapi": (FASTAPI_FILES, FASTAPI_EXPECTED),
    "nestjs": (NESTJS_FILES, NESTJS_EXPECTED),
    "django": (DJANGO_FILES, DJANGO_EXPECTED),
    "express": (EXPRESS_FILES, EXPRESS_EXPECTED),
    "flask": (FLASK_FILES, FLASK_EXPECTED),
    "spring": (SPRING_FILES, SPRING_EXPECTED),
}


# ====================================================================================
# HARD field cases — typed/Optional query params, destructured bodies, get_json(),
# List<Dto> bodies, multiple path vars, full ModelViewSet CRUD.
# ====================================================================================

# FastAPI: Optional[int] and Query()-defaulted query params (Optional was dropped before).
FASTAPI_HARD_FILES = {
    "main.py": """
from fastapi import FastAPI
from search import router as search_router

app = FastAPI()
app.include_router(search_router, prefix="/api")
""",
    "search.py": """
from typing import Optional
from fastapi import APIRouter, Query

router = APIRouter(prefix="/search")


@router.get("/")
def search(q: str, page: Optional[int] = None, limit: int = Query(20)):
    return []
""",
}
FASTAPI_HARD_EXPECTED = {
    key("GET", "/api/search"): R(query_params={"q", "page", "limit"}, responses={200}),
}

# Express: body inferred from destructuring (no schema) + dot access.
EXPRESS_HARD_FILES = {
    "app.js": """
const express = require('express');
const app = express();
app.use('/api/posts', require('./routes/posts'));
""",
    "routes/posts.js": """
const express = require('express');
const router = express.Router();

router.post('/', (req, res) => {
  const { title, body: content } = req.body;
  const author = req.body.author;
  res.status(201).json({});
});

module.exports = router;
""",
}
EXPRESS_HARD_EXPECTED = {
    key("POST", "/api/posts"): R(body={"title", "body", "author"}, responses={201}),
}

# Flask: body via request.get_json() + request.form.
FLASK_HARD_FILES = {
    "app.py": """
from flask import Flask
from posts.routes import bp

app = Flask(__name__)
app.register_blueprint(bp, url_prefix="/api")
""",
    "posts/__init__.py": "",
    "posts/routes.py": """
from flask import Blueprint, request

bp = Blueprint("posts", __name__, url_prefix="/posts")


@bp.post("/")
def create():
    data = request.get_json()
    title = data["title"]
    tag = request.form["tag"]
    return {}
""",
}
FLASK_HARD_EXPECTED = {
    key("POST", "/api/posts"): R(body={"title", "tag"}, responses={201}),
}

# Spring: List<Dto> body + multiple path variables.
SPRING_HARD_FILES = {
    "src/main/java/com/acme/OrderController.java": """
package com.acme;

import java.util.List;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class OrderController {

    @PostMapping("/{userId}/orders")
    public Object bulk(@PathVariable String userId, @RequestBody List<OrderDto> orders) {
        return null;
    }

    @GetMapping("/{userId}/orders/{orderId}")
    public Object get(@PathVariable String userId, @PathVariable String orderId) {
        return null;
    }
}
""",
    "src/main/java/com/acme/OrderDto.java": """
package com.acme;

public class OrderDto {
    private String sku;
    private Integer quantity;
}
""",
}
SPRING_HARD_EXPECTED = {
    key("POST", "/api/users/{userId}/orders"): R(
        body={"sku", "quantity"}, path_params={"userId"}, responses={201}
    ),
    key("GET", "/api/users/{userId}/orders/{orderId}"): R(
        path_params={"userId", "orderId"}, responses={200}
    ),
}

# Django: full ModelViewSet (all six CRUD actions) with a ModelSerializer.
DJANGO_HARD_FILES = {
    "urls.py": """
from django.urls import path, include

urlpatterns = [path("api/", include("shop.urls"))]
""",
    "shop/__init__.py": "",
    "shop/serializers.py": """
from rest_framework import serializers


class ProductSerializer(serializers.Serializer):
    title = serializers.CharField()
    price = serializers.DecimalField()
""",
    "shop/views.py": """
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from shop.serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
""",
    "shop/urls.py": """
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from shop.views import ProductViewSet

router = DefaultRouter()
router.register("products", ProductViewSet)

urlpatterns = [path("", include(router.urls))]
""",
}
DJANGO_HARD_EXPECTED = {
    key("GET", "/api/products"): R(auth=True, responses={200}),
    key("POST", "/api/products"): R(auth=True, body={"title", "price"}, responses={201}),
    key("GET", "/api/products/{pk}"): R(auth=True, path_params={"pk"}, responses={200}),
    key("PUT", "/api/products/{pk}"): R(
        auth=True, body={"title", "price"}, path_params={"pk"}, responses={200}
    ),
    key("PATCH", "/api/products/{pk}"): R(
        auth=True, body={"title", "price"}, path_params={"pk"}, responses={200}
    ),
    key("DELETE", "/api/products/{pk}"): R(auth=True, path_params={"pk"}, responses={200}),
}


HARD_FIELD_CORPUS = {
    "fastapi_hard": (FASTAPI_HARD_FILES, FASTAPI_HARD_EXPECTED, "fastapi"),
    "express_hard": (EXPRESS_HARD_FILES, EXPRESS_HARD_EXPECTED, "express"),
    "flask_hard": (FLASK_HARD_FILES, FLASK_HARD_EXPECTED, "flask"),
    "spring_hard": (SPRING_HARD_FILES, SPRING_HARD_EXPECTED, "spring"),
    "django_hard": (DJANGO_HARD_FILES, DJANGO_HARD_EXPECTED, "django"),
}
