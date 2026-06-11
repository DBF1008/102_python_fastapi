from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Scenario 1 & 2 & 3: include_router-level override on a default router
# ---------------------------------------------------------------------------

router_default = APIRouter()


@router_default.post("/items/")
async def default_post(data: dict):
    return data


# 1) Lax mount on strict app
app_lax_mount = FastAPI()  # strict by default
app_lax_mount.include_router(router_default, prefix="/lax", strict_content_type=False)
client_lax_mount = TestClient(app_lax_mount)


def test_lax_mount_accepts_no_content_type():
    response = client_lax_mount.post("/lax/items/", content='{"key": "value"}')
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


# 2) Strict mount on strict app (explicit True, same as default)
app_strict_mount = FastAPI()
app_strict_mount.include_router(router_default, prefix="/strict", strict_content_type=True)
client_strict_mount = TestClient(app_strict_mount)


def test_strict_mount_rejects_no_content_type():
    response = client_strict_mount.post("/strict/items/", content='{"key": "value"}')
    assert response.status_code == 422


# 3) Default mount (no override) inherits from app
app_default_mount = FastAPI()  # strict by default
app_default_mount.include_router(router_default, prefix="/default")
client_default_mount = TestClient(app_default_mount)


def test_default_mount_inherits_strict_from_app():
    response = client_default_mount.post("/default/items/", content='{"key": "value"}')
    assert response.status_code == 422


app_default_mount_lax = FastAPI(strict_content_type=False)
app_default_mount_lax.include_router(router_default, prefix="/default")
client_default_mount_lax = TestClient(app_default_mount_lax)


def test_default_mount_inherits_lax_from_app():
    response = client_default_mount_lax.post("/default/items/", content='{"key": "value"}')
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


# ---------------------------------------------------------------------------
# Scenario 4: route-level strict_content_type wins over mount-point override
# ---------------------------------------------------------------------------

router_route_level = APIRouter()


async def route_level_lax(data: dict):
    return data


router_route_level.add_api_route(
    "/items/",
    route_level_lax,
    methods=["POST"],
    strict_content_type=False,
)

app_route_level = FastAPI()
app_route_level.include_router(
    router_route_level, strict_content_type=True
)
client_route_level = TestClient(app_route_level)


def test_route_level_lax_wins_over_strict_mount():
    """Route has strict_content_type=False; mount says True. Route wins → accepts."""
    response = client_route_level.post("/items/", content='{"key": "value"}')
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


# ---------------------------------------------------------------------------
# Scenario 5: router-definition lax, mount-point strict → mount wins
# ---------------------------------------------------------------------------

router_lax_def = APIRouter(strict_content_type=False)


@router_lax_def.post("/items/")
async def lax_def_post(data: dict):
    return data


app_mount_overrides_lax = FastAPI()
app_mount_overrides_lax.include_router(
    router_lax_def, strict_content_type=True
)
client_mount_overrides_lax = TestClient(app_mount_overrides_lax)


def test_mount_strict_overrides_router_lax():
    """Router says lax, mount says strict. Mount wins → rejects."""
    response = client_mount_overrides_lax.post("/items/", content='{"key": "value"}')
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Scenario 6: router-definition strict, mount-point lax → mount wins
# ---------------------------------------------------------------------------

router_strict_def = APIRouter(strict_content_type=True)


@router_strict_def.post("/items/")
async def strict_def_post(data: dict):
    return data


app_mount_overrides_strict = FastAPI()
app_mount_overrides_strict.include_router(
    router_strict_def, strict_content_type=False
)
client_mount_overrides_strict = TestClient(app_mount_overrides_strict)


def test_mount_lax_overrides_router_strict():
    """Router says strict, mount says lax. Mount wins → accepts."""
    response = client_mount_overrides_strict.post("/items/", content='{"key": "value"}')
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


# ---------------------------------------------------------------------------
# Scenario 7: nested routers — outer mount lax, inner default inherits
# ---------------------------------------------------------------------------

app_nested_outer_lax = FastAPI()  # strict by default
outer_router_7 = APIRouter(prefix="/outer")
inner_router_7 = APIRouter(prefix="/inner")


@inner_router_7.post("/items/")
async def nested_inner_post(data: dict):
    return data


outer_router_7.include_router(inner_router_7)
app_nested_outer_lax.include_router(
    outer_router_7, strict_content_type=False
)
client_nested_outer_lax = TestClient(app_nested_outer_lax)


def test_nested_inner_inherits_lax_from_outer_mount():
    """Outer mount is lax, inner router is default → inherits lax."""
    response = client_nested_outer_lax.post(
        "/outer/inner/items/", content='{"key": "value"}'
    )
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


# ---------------------------------------------------------------------------
# Scenario 8: nested — strict app, default outer, inner included with lax
# ---------------------------------------------------------------------------

app_nested_inner_lax = FastAPI()  # strict by default
outer_router_8 = APIRouter(prefix="/outer")
inner_router_8 = APIRouter(prefix="/inner")


@inner_router_8.post("/items/")
async def nested_inner_post_8(data: dict):
    return data


outer_router_8.include_router(inner_router_8, strict_content_type=False)
app_nested_inner_lax.include_router(outer_router_8)
client_nested_inner_lax = TestClient(app_nested_inner_lax)


def test_nested_inner_lax_via_include_override():
    """Inner router included with strict_content_type=False → accepts."""
    response = client_nested_inner_lax.post(
        "/outer/inner/items/", content='{"key": "value"}'
    )
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


# ---------------------------------------------------------------------------
# Scenario 9: same router mounted at two different points, strict and lax
# ---------------------------------------------------------------------------

shared_router = APIRouter()


@shared_router.post("/items/")
async def shared_post(data: dict):
    return data


app_dual = FastAPI()
app_dual.include_router(shared_router, prefix="/strict", strict_content_type=True)
app_dual.include_router(shared_router, prefix="/lax", strict_content_type=False)
client_dual = TestClient(app_dual)


def test_dual_mount_strict_rejects():
    response = client_dual.post("/strict/items/", content='{"key": "value"}')
    assert response.status_code == 422


def test_dual_mount_lax_accepts():
    response = client_dual.post("/lax/items/", content='{"key": "value"}')
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


# ---------------------------------------------------------------------------
# Scenario 10: JSON Content-Type always works regardless of settings
# ---------------------------------------------------------------------------


def test_json_content_type_always_works_on_strict_mount():
    response = client_strict_mount.post("/strict/items/", json={"key": "value"})
    assert response.status_code == 200


def test_json_content_type_always_works_on_lax_mount():
    response = client_lax_mount.post("/lax/items/", json={"key": "value"})
    assert response.status_code == 200


def test_json_content_type_always_works_on_dual_mounts():
    response_s = client_dual.post("/strict/items/", json={"key": "value"})
    response_l = client_dual.post("/lax/items/", json={"key": "value"})
    assert response_s.status_code == 200
    assert response_l.status_code == 200
