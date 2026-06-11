from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

# --- Scenario 1: Same router reused at two mount points with different overrides ---

shared_router = APIRouter()


@shared_router.post("/items/")
async def shared_post(data: dict):
    return data


app_reuse = FastAPI()
app_reuse.include_router(shared_router, prefix="/lax", strict_content_type=False)
app_reuse.include_router(shared_router, prefix="/strict", strict_content_type=True)

client_reuse = TestClient(app_reuse)


def test_reuse_lax_mount_accepts_no_content_type():
    response = client_reuse.post("/lax/items/", content='{"key": "value"}')
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


def test_reuse_strict_mount_rejects_no_content_type():
    response = client_reuse.post("/strict/items/", content='{"key": "value"}')
    assert response.status_code == 422


def test_reuse_both_accept_json_content_type():
    for prefix in ["/lax", "/strict"]:
        response = client_reuse.post(f"{prefix}/items/", json={"key": "value"})
        assert response.status_code == 200
        assert response.json() == {"key": "value"}


# --- Scenario 2: Router-level explicit setting overrides include_router argument ---

router_explicit_strict = APIRouter(strict_content_type=True)


@router_explicit_strict.post("/items/")
async def explicit_strict_post(data: dict):
    return data


app_router_override = FastAPI()
app_router_override.include_router(
    router_explicit_strict, prefix="/test", strict_content_type=False
)

client_router_override = TestClient(app_router_override)


def test_router_level_strict_overrides_include_router_lax():
    response = client_router_override.post(
        "/test/items/", content='{"key": "value"}'
    )
    assert response.status_code == 422


def test_router_level_strict_overrides_include_router_lax_with_json():
    response = client_router_override.post("/test/items/", json={"key": "value"})
    assert response.status_code == 200


# --- Scenario 3: include_router argument overrides app default ---

app_strict_default = FastAPI()
router_no_setting = APIRouter()


@router_no_setting.post("/items/")
async def no_setting_post(data: dict):
    return data


app_strict_default.include_router(
    router_no_setting, prefix="/lax", strict_content_type=False
)

client_include_override = TestClient(app_strict_default)


def test_include_router_lax_overrides_strict_app():
    response = client_include_override.post(
        "/lax/items/", content='{"key": "value"}'
    )
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


def test_include_router_lax_overrides_strict_app_with_json():
    response = client_include_override.post("/lax/items/", json={"key": "value"})
    assert response.status_code == 200


# --- Scenario 4: Nested include_router inherits override ---

app_nested = FastAPI()
outer_router_nested = APIRouter()
inner_router_nested = APIRouter()


@inner_router_nested.post("/items/")
async def nested_inner_post(data: dict):
    return data


outer_router_nested.include_router(inner_router_nested, prefix="/inner")
app_nested.include_router(
    outer_router_nested, prefix="/outer", strict_content_type=False
)

client_nested = TestClient(app_nested)


def test_nested_inner_inherits_lax_from_include_router():
    response = client_nested.post(
        "/outer/inner/items/", content='{"key": "value"}'
    )
    assert response.status_code == 200
    assert response.json() == {"key": "value"}


def test_nested_inner_accepts_json_content_type():
    response = client_nested.post("/outer/inner/items/", json={"key": "value"})
    assert response.status_code == 200


# --- Scenario 5: Default behavior unchanged (no strict_content_type arg) ---

app_default = FastAPI()
router_default = APIRouter()


@router_default.post("/items/")
async def default_post(data: dict):
    return data


app_default.include_router(router_default, prefix="/default")

client_default = TestClient(app_default)


def test_default_behavior_rejects_no_content_type():
    response = client_default.post("/default/items/", content='{"key": "value"}')
    assert response.status_code == 422


def test_default_behavior_accepts_json_content_type():
    response = client_default.post("/default/items/", json={"key": "value"})
    assert response.status_code == 200
    assert response.json() == {"key": "value"}
