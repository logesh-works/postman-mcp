"""Django REST Framework + NestJS parsers (PRD §9.4)."""

from __future__ import annotations

from postman_mcp.input.parsers import django as django_parser
from postman_mcp.input.parsers import nestjs as nestjs_parser
from postman_mcp.models import FieldType, InputSource


def _write(tmp_path, name, src):
    (tmp_path / name).write_text(src, encoding="utf-8")


# --- Django ------------------------------------------------------------------------

DJANGO_VIEWS = '''
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated


class PaymentSerializer(serializers.Serializer):
    amount = serializers.IntegerField()
    currency = serializers.CharField()


class PaymentViewSet(viewsets.ViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request):
        return None

    def list(self, request):
        return None
'''

DJANGO_URLS = '''
from django.urls import path
from .views import PaymentViewSet

urlpatterns = [
    path('payments/', PaymentViewSet.as_view()),
]
'''


def test_django_parser_routes_and_auth(tmp_path):
    _write(tmp_path, "views.py", DJANGO_VIEWS)
    _write(tmp_path, "urls.py", DJANGO_URLS)
    routes, skipped = django_parser.parse(tmp_path)
    assert skipped == []
    assert routes
    assert all(r.source is InputSource.CODE for r in routes)
    # the viewset declares get/post/put/delete (ViewSet default) — auth required
    assert any(r.path == "/payments" for r in routes)
    assert all(r.auth_required for r in routes)


def test_django_parser_serializer_body(tmp_path):
    _write(tmp_path, "views.py", DJANGO_VIEWS)
    _write(tmp_path, "urls.py", DJANGO_URLS)
    routes, _ = django_parser.parse(tmp_path)
    post = next((r for r in routes if r.method == "POST"), None)
    assert post is not None
    names = {f.name for f in post.body.fields}
    assert {"amount", "currency"} == names
    amount = next(f for f in post.body.fields if f.name == "amount")
    assert amount.type is FieldType.INTEGER


def test_django_parser_skips_syntax_error(tmp_path):
    _write(tmp_path, "broken.py", "def (:\n")
    routes, skipped = django_parser.parse(tmp_path)
    assert any("broken.py" in s for s in skipped)


# --- NestJS ------------------------------------------------------------------------

NEST_SRC = '''
import { Controller, Get, Post, Body, Param, UseGuards } from '@nestjs/common';

class CreatePaymentDto {
  amount: number;
  currency: string;
}

@Controller('payments')
@UseGuards(AuthGuard)
export class PaymentsController {
  @Post()
  create(@Body() dto: CreatePaymentDto) {
    return dto;
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return { id };
  }
}
'''


def test_nestjs_parser_routes_with_controller_prefix(tmp_path):
    _write(tmp_path, "payments.controller.ts", NEST_SRC)
    routes, skipped = nestjs_parser.parse(tmp_path)
    assert skipped == []
    by_key = {r.key: r for r in routes}
    assert "POST:/payments" in by_key
    assert "GET:/payments/{param}" in by_key


def test_nestjs_parser_dto_body_and_guard(tmp_path):
    _write(tmp_path, "payments.controller.ts", NEST_SRC)
    routes = {r.key: r for r in nestjs_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    assert post.auth_required is True  # class-level @UseGuards
    names = {f.name for f in post.body.fields}
    assert {"amount", "currency"} == names
    amount = next(f for f in post.body.fields if f.name == "amount")
    assert amount.type is FieldType.NUMBER


def test_nestjs_get_has_path_param(tmp_path):
    _write(tmp_path, "payments.controller.ts", NEST_SRC)
    routes = {r.key: r for r in nestjs_parser.parse(tmp_path)[0]}
    get = routes["GET:/payments/{param}"]
    assert [p.name for p in get.path_params] == ["id"]
    assert get.body is None
