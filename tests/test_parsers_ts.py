"""Django REST Framework + NestJS parsers."""

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


DJANGO_API_VIEW_SRC = '''
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated


class PaymentSerializer(serializers.Serializer):
    amount = serializers.IntegerField()
    currency = serializers.CharField()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def payment_list(request):
    serializer = PaymentSerializer(data=request.data)
    return None
'''

DJANGO_API_VIEW_URLS = '''
from django.urls import path
from .views import payment_list

urlpatterns = [
    path('payments/', payment_list),
]
'''


def test_django_parser_detects_function_based_api_view(tmp_path):
    _write(tmp_path, "views.py", DJANGO_API_VIEW_SRC)
    _write(tmp_path, "urls.py", DJANGO_API_VIEW_URLS)
    routes, skipped = django_parser.parse(tmp_path)
    assert skipped == []
    by_method = {r.method: r for r in routes if r.path == "/payments"}
    assert {"GET", "POST"} == set(by_method)
    assert all(r.auth_required for r in by_method.values())
    post = by_method["POST"]
    assert {f.name for f in post.body.fields} == {"amount", "currency"}


DJANGO_AS_VIEW_MAPPING_URLS = '''
from django.urls import path
from .views import PaymentViewSet

urlpatterns = [
    path('payments/', PaymentViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('payments/<str:pk>/', PaymentViewSet.as_view({'get': 'retrieve'})),
]
'''


def test_django_as_view_mapping_limits_methods_and_strips_converters(tmp_path):
    _write(tmp_path, "views.py", DJANGO_VIEWS)
    _write(tmp_path, "urls.py", DJANGO_AS_VIEW_MAPPING_URLS)
    routes, _ = django_parser.parse(tmp_path)
    keyed = {(r.method, r.path) for r in routes}
    # only the methods named in each .as_view({...}) mapping — no invented PUT/DELETE
    assert keyed == {("GET", "/payments"), ("POST", "/payments"), ("GET", "/payments/{pk}")}


# Django include() composition: the root urlconf mounts an app's urls under a prefix.
# The old leaf-only reader emitted "/payments"; the full URL is "/api/v1/payments".
DJANGO_ROOT_URLS = '''
from django.urls import path, include

urlpatterns = [
    path('api/v1/', include('app.urls')),
]
'''

DJANGO_APP_URLS = '''
from django.urls import path
from .views import PaymentViewSet

urlpatterns = [
    path('payments/', PaymentViewSet.as_view({'get': 'list', 'post': 'create'})),
]
'''


def test_django_include_composes_prefix(tmp_path):
    _write(tmp_path, "urls.py", DJANGO_ROOT_URLS)
    (tmp_path / "app").mkdir()
    _write(tmp_path, "app/__init__.py", "")
    _write(tmp_path, "app/urls.py", DJANGO_APP_URLS)
    _write(tmp_path, "app/views.py", DJANGO_VIEWS)
    routes, _ = django_parser.parse(tmp_path)
    keyed = {(r.method, r.path) for r in routes}
    # composed: 'api/v1/' + 'payments/' → /api/v1/payments — and emitted exactly once
    assert keyed == {("GET", "/api/v1/payments"), ("POST", "/api/v1/payments")}


def test_django_nested_includes(tmp_path):
    # root → api → app, two levels of include() prefixes
    _write(
        tmp_path,
        "urls.py",
        """
from django.urls import path, include
urlpatterns = [path('api/', include('api.urls'))]
""",
    )
    (tmp_path / "api").mkdir()
    _write(tmp_path, "api/__init__.py", "")
    _write(
        tmp_path,
        "api/urls.py",
        """
from django.urls import path, include
urlpatterns = [path('v2/', include('app.urls'))]
""",
    )
    (tmp_path / "app").mkdir()
    _write(tmp_path, "app/__init__.py", "")
    _write(tmp_path, "app/urls.py", DJANGO_APP_URLS)
    _write(tmp_path, "app/views.py", DJANGO_VIEWS)
    routes, _ = django_parser.parse(tmp_path)
    paths = {r.path for r in routes}
    assert paths == {"/api/v2/payments"}


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


NEST_NESTED_DECORATOR_SRC = '''
import { Controller, Get, Post, Body, ApiProperty } from '@nestjs/common';

class CreatePaymentDto {
  @ApiProperty({ type: String, example: "usd" })
  currency: string;

  @ApiProperty({ type: Number })
  amount: number;

  note: string;
}

@Controller('payments')
export class PaymentsController {
  @Post()
  create(@Body() dto: CreatePaymentDto) {
    return dto;
  }
}
'''


def test_nestjs_dto_survives_nested_decorator_braces(tmp_path):
    # A property decorated with an object-literal arg (`@ApiProperty({ type: String })`)
    # used to truncate the whole class at that decorator's first `}` — verifying the
    # class keeps every field declared after it, and that no key from inside the
    # decorator's own object literal (`type`, `example`) leaks in as a bogus field.
    _write(tmp_path, "payments.controller.ts", NEST_NESTED_DECORATOR_SRC)
    routes = {r.key: r for r in nestjs_parser.parse(tmp_path)[0]}
    post = routes["POST:/payments"]
    names = {f.name for f in post.body.fields}
    assert names == {"currency", "amount", "note"}
    assert "type" not in names and "example" not in names


NEST_HEADERS_SRC = '''
import { Controller, Get, Headers } from '@nestjs/common';

@Controller('payments')
export class PaymentsController {
  @Get(':id')
  findOne(@Headers('x-api-key') apiKey: string) {
    return { apiKey };
  }
}
'''


def test_nestjs_headers_param_is_detected(tmp_path):
    _write(tmp_path, "payments.controller.ts", NEST_HEADERS_SRC)
    routes = {r.key: r for r in nestjs_parser.parse(tmp_path)[0]}
    get = routes["GET:/payments/{param}"]
    assert [h.name for h in get.headers] == ["x-api-key"]
    assert get.headers[0].required is True


NEST_MAIN = """
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.setGlobalPrefix('api/v1');
  await app.listen(3000);
}
bootstrap();
"""


def test_nestjs_global_prefix_composes_with_controller_prefix(tmp_path):
    # setGlobalPrefix('api/v1') in main.ts + @Controller('payments') + @Get(':id')
    _write(tmp_path, "main.ts", NEST_MAIN)
    _write(tmp_path, "payments.controller.ts", NEST_SRC)
    keys = {r.key for r in nestjs_parser.parse(tmp_path)[0]}
    assert "POST:/api/v1/payments" in keys
    assert "GET:/api/v1/payments/{param}" in keys
