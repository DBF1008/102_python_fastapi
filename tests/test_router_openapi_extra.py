from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from inline_snapshot import snapshot


def test_router_level_openapi_extra_applies_to_all_routes():
    app = FastAPI()
    router = APIRouter()

    @router.get("/items")
    def get_items():
        return []

    @router.get("/users")
    def get_users():
        return []

    app.include_router(
        router,
        prefix="/api",
        openapi_extra={"x-gateway": "internal", "x-rate-limit": 100},
    )

    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    items_op = schema["paths"]["/api/items"]["get"]
    users_op = schema["paths"]["/api/users"]["get"]
    assert items_op["x-gateway"] == "internal"
    assert items_op["x-rate-limit"] == 100
    assert users_op["x-gateway"] == "internal"
    assert users_op["x-rate-limit"] == 100


def test_route_level_overrides_router_level():
    app = FastAPI()
    router = APIRouter()

    @router.get(
        "/items",
        openapi_extra={"x-gateway": "public", "x-custom": "per-route"},
    )
    def get_items():
        return []

    @router.get("/users")
    def get_users():
        return []

    app.include_router(
        router,
        prefix="/api",
        openapi_extra={"x-gateway": "internal", "x-rate-limit": 100},
    )

    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    items_op = schema["paths"]["/api/items"]["get"]
    users_op = schema["paths"]["/api/users"]["get"]
    # route-level "x-gateway" overrides router-level
    assert items_op["x-gateway"] == "public"
    # router-level default still applies where route doesn't override
    assert items_op["x-rate-limit"] == 100
    # route-level only field present
    assert items_op["x-custom"] == "per-route"
    # route with no openapi_extra gets pure router defaults
    assert users_op["x-gateway"] == "internal"
    assert users_op["x-rate-limit"] == 100
    assert "x-custom" not in users_op


def test_deep_merge_nested_dicts():
    app = FastAPI()
    router = APIRouter()

    @router.get(
        "/items",
        openapi_extra={
            "x-metadata": {"owner": "team-b", "priority": "high"},
        },
    )
    def get_items():
        return []

    app.include_router(
        router,
        prefix="/api",
        openapi_extra={
            "x-metadata": {"owner": "team-a", "region": "us-east"},
        },
    )

    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    items_op = schema["paths"]["/api/items"]["get"]
    # deep merge: route "owner" wins, router "region" preserved, route "priority" added
    assert items_op["x-metadata"] == {
        "owner": "team-b",
        "region": "us-east",
        "priority": "high",
    }


def test_nested_routers_openapi_extra():
    app = FastAPI()
    inner_router = APIRouter()
    outer_router = APIRouter()

    @inner_router.get("/items")
    def get_items():
        return []

    @inner_router.get(
        "/special",
        openapi_extra={"x-level": "route"},
    )
    def get_special():
        return []

    outer_router.include_router(
        inner_router,
        prefix="/inner",
        openapi_extra={"x-level": "inner", "x-inner-only": True},
    )
    app.include_router(
        outer_router,
        prefix="/outer",
        openapi_extra={"x-level": "outer", "x-outer-only": True},
    )

    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    items_op = schema["paths"]["/outer/inner/items"]["get"]
    special_op = schema["paths"]["/outer/inner/special"]["get"]

    # inner router's include_router merges inner-level over route (no route-level here)
    # then outer router's include_router merges outer-level as base
    # inner-level overrides outer-level for x-level
    assert items_op["x-level"] == "inner"
    assert items_op["x-inner-only"] is True
    assert items_op["x-outer-only"] is True

    # route-level overrides inner-level for x-level
    assert special_op["x-level"] == "route"
    assert special_op["x-inner-only"] is True
    assert special_op["x-outer-only"] is True


def test_callbacks_and_responses_unaffected():
    app = FastAPI()
    router = APIRouter()
    callback_router = APIRouter()

    @callback_router.post("/callback")
    def the_callback(data: str):
        pass  # pragma: nocover

    @router.post(
        "/items",
        callbacks=callback_router.routes,
        responses={201: {"description": "Created"}},
    )
    def create_item():
        return {}

    app.include_router(
        router,
        prefix="/api",
        openapi_extra={"x-gateway": "internal"},
    )

    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    items_op = schema["paths"]["/api/items"]["post"]
    assert items_op["x-gateway"] == "internal"
    assert "201" in items_op["responses"]
    assert items_op["responses"]["201"]["description"] == "Created"
    assert "callbacks" in items_op


def test_router_openapi_extra_no_mutation():
    """The original openapi_extra dict passed to include_router must not be mutated."""
    app = FastAPI()
    router = APIRouter()

    @router.get("/a", openapi_extra={"x-route": "a"})
    def get_a():
        return []

    @router.get("/b", openapi_extra={"x-route": "b"})
    def get_b():
        return []

    original = {"x-base": "value", "x-nested": {"key": "original"}}
    app.include_router(router, prefix="/api", openapi_extra=original)

    client = TestClient(app)
    client.get("/openapi.json").json()
    assert original == {"x-base": "value", "x-nested": {"key": "original"}}


def test_openapi_extra_full_schema():
    """Full snapshot test of the generated OpenAPI schema."""
    app = FastAPI()
    router = APIRouter()

    @router.get("/default")
    def get_default():
        return {}

    @router.get("/override", openapi_extra={"x-gateway": "public"})
    def get_override():
        return {}

    app.include_router(
        router,
        prefix="/api",
        openapi_extra={"x-gateway": "internal"},
    )

    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json() == snapshot(
        {
            "openapi": "3.1.0",
            "info": {"title": "FastAPI", "version": "0.1.0"},
            "paths": {
                "/api/default": {
                    "get": {
                        "summary": "Get Default",
                        "operationId": "get_default_api_default_get",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {"application/json": {"schema": {}}},
                            }
                        },
                        "x-gateway": "internal",
                    }
                },
                "/api/override": {
                    "get": {
                        "summary": "Get Override",
                        "operationId": "get_override_api_override_get",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {"application/json": {"schema": {}}},
                            }
                        },
                        "x-gateway": "public",
                    }
                },
            },
        }
    )
