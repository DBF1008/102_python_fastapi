from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


def test_router_level_openapi_extra():
    """Router-level openapi_extra applies to all routes in the router."""
    router = APIRouter(openapi_extra={"x-custom-extension": "router-value"})

    @router.get("/a")
    def route_a():
        return {}

    @router.get("/b")
    def route_b():
        return {}

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/a"]["get"]["x-custom-extension"] == "router-value"
    assert schema["paths"]["/b"]["get"]["x-custom-extension"] == "router-value"


def test_route_level_overrides_router_level():
    """Route-level openapi_extra takes precedence over router-level for the same key."""
    router = APIRouter(
        openapi_extra={"x-custom-extension": "router-value", "x-other": "keep"}
    )

    @router.get("/", openapi_extra={"x-custom-extension": "route-value"})
    def root():
        return {}

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    # Route-level overrides router-level for the same key
    assert schema["paths"]["/"]["get"]["x-custom-extension"] == "route-value"
    # Router-level key not in route-level is preserved
    assert schema["paths"]["/"]["get"]["x-other"] == "keep"


def test_include_router_openapi_extra():
    """include_router openapi_extra is merged with router-level and route-level."""
    router = APIRouter(
        openapi_extra={"x-router": "yes", "x-shared": "router"}
    )

    @router.get("/", openapi_extra={"x-route": "yes", "x-shared": "route"})
    def root():
        return {}

    app = FastAPI()
    app.include_router(
        router, openapi_extra={"x-include": "yes", "x-shared": "include"}
    )
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/"]["get"]

    assert operation["x-include"] == "yes"  # from include_router
    assert operation["x-router"] == "yes"  # from router
    assert operation["x-route"] == "yes"  # from route
    # Route-level wins on conflicts
    assert operation["x-shared"] == "route"


def test_nested_routers_partial_override():
    """Nested routers merge openapi_extra at each level, inner wins over outer."""
    inner = APIRouter(
        openapi_extra={"x-inner": "yes", "x-depth": "inner"}
    )

    @inner.get("/nested")
    def nested():
        return {}

    outer = APIRouter(
        openapi_extra={"x-outer": "yes", "x-depth": "outer"}
    )
    outer.include_router(inner, prefix="/api")

    app = FastAPI()
    app.include_router(outer)
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/nested"]["get"]

    assert operation["x-outer"] == "yes"
    assert operation["x-inner"] == "yes"
    # Inner router's value wins over outer router's
    assert operation["x-depth"] == "inner"


def test_deep_merge_nested_dicts():
    """Nested dict structures are recursively merged, lists are concatenated."""
    router = APIRouter(
        openapi_extra={
            "x-meta": {"author": "team", "version": "1.0", "tags": ["api"]}
        }
    )

    @router.get(
        "/",
        openapi_extra={"x-meta": {"version": "2.0", "tags": ["v2"]}},
    )
    def root():
        return {}

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    meta = schema["paths"]["/"]["get"]["x-meta"]

    # Preserved from router-level (not overridden by route)
    assert meta["author"] == "team"
    # Route-level scalar overrides router-level
    assert meta["version"] == "2.0"
    # Lists are concatenated
    assert meta["tags"] == ["api", "v2"]


def test_no_mutation_of_original_dicts():
    """Original openapi_extra dicts are not mutated by the merging process."""
    router_extra: dict[str, Any] = {"x-shared": "original", "x-nested": {"a": 1}}
    route_extra: dict[str, Any] = {"x-shared": "override", "x-nested": {"b": 2}}

    router = APIRouter(openapi_extra=router_extra)

    @router.get("/", openapi_extra=route_extra)
    def root():
        return {}

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    _ = client.get("/openapi.json").json()

    # Original dicts must not be mutated
    assert router_extra == {"x-shared": "original", "x-nested": {"a": 1}}
    assert route_extra == {"x-shared": "override", "x-nested": {"b": 2}}


def test_no_mutation_with_include_router():
    """include_router-level openapi_extra dicts are not mutated either."""
    include_extra: dict[str, Any] = {"x-include": "yes", "x-shared": "include"}
    router_extra: dict[str, Any] = {"x-router": "yes", "x-shared": "router"}
    route_extra: dict[str, Any] = {"x-route": "yes", "x-shared": "route"}

    router = APIRouter(openapi_extra=router_extra)

    @router.get("/", openapi_extra=route_extra)
    def root():
        return {}

    app = FastAPI()
    app.include_router(router, openapi_extra=include_extra)
    client = TestClient(app)
    _ = client.get("/openapi.json").json()

    assert include_extra == {"x-include": "yes", "x-shared": "include"}
    assert router_extra == {"x-router": "yes", "x-shared": "router"}
    assert route_extra == {"x-route": "yes", "x-shared": "route"}


def test_none_openapi_extra_no_interference():
    """When no openapi_extra is set at any level, behavior is unchanged."""
    router = APIRouter()

    @router.get("/")
    def root():
        return {}

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/"]["get"]

    # No x- extensions should be present
    x_keys = [k for k in operation if k.startswith("x-")]
    assert x_keys == []


def test_only_include_router_level_extra():
    """openapi_extra set only on include_router applies to routes without their own."""
    router = APIRouter()

    @router.get("/plain")
    def plain():
        return {}

    @router.get("/own", openapi_extra={"x-own": "yes"})
    def own():
        return {}

    app = FastAPI()
    app.include_router(router, openapi_extra={"x-gateway": "v1"})
    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    # Route without its own extra gets include_router-level
    assert schema["paths"]["/plain"]["get"]["x-gateway"] == "v1"
    # Route with its own extra gets both (merged)
    assert schema["paths"]["/own"]["get"]["x-gateway"] == "v1"
    assert schema["paths"]["/own"]["get"]["x-own"] == "yes"


def test_three_layer_nested_merge():
    """Full three-layer merge: include_router > APIRouter > route, route wins."""
    router = APIRouter(
        openapi_extra={
            "x-layer": "router",
            "x-meta": {"source": "router", "version": "1"},
        }
    )

    @router.get(
        "/",
        openapi_extra={
            "x-layer": "route",
            "x-meta": {"version": "2"},
        },
    )
    def root():
        return {}

    app = FastAPI()
    app.include_router(
        router,
        openapi_extra={
            "x-layer": "include",
            "x-include-only": "yes",
            "x-meta": {"source": "include", "env": "prod"},
        },
    )
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/"]["get"]

    # Scalar: route wins
    assert operation["x-layer"] == "route"
    # Key only in include_router: preserved
    assert operation["x-include-only"] == "yes"
    # Nested dict: deep merged, route scalar wins, router fills gaps
    meta = operation["x-meta"]
    assert meta["version"] == "2"  # route overrides router
    assert meta["source"] == "router"  # router overrides include
    assert meta["env"] == "prod"  # include-only key preserved
