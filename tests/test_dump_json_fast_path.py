from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field


class Item(BaseModel):
    name: str
    price: float


class AliasedItem(BaseModel):
    item_name: str = Field(alias="itemName")
    price: float


class CustomJSONResponse(JSONResponse):
    media_type = "application/vnd.custom+json"


# --- App with default response class (DefaultPlaceholder) ---

app_default = FastAPI()


@app_default.get("/item")
def get_default_item() -> Item:
    return Item(name="widget", price=9.99)


# --- App with explicit JSONResponse on route ---

app_explicit = FastAPI()


@app_explicit.get("/item", response_class=JSONResponse)
def get_explicit_item() -> Item:
    return Item(name="widget", price=9.99)


# --- App with custom JSONResponse subclass on route ---

app_custom = FastAPI()


@app_custom.get("/item", response_class=CustomJSONResponse)
def get_custom_item() -> Item:
    return Item(name="widget", price=9.99)


# --- App with default_response_class set at app level ---

app_global = FastAPI(default_response_class=JSONResponse)


@app_global.get("/item")
def get_global_item() -> Item:
    return Item(name="widget", price=9.99)


# --- App with custom subclass as default_response_class ---

app_global_custom = FastAPI(default_response_class=CustomJSONResponse)


@app_global_custom.get("/item")
def get_global_custom_item() -> Item:
    return Item(name="widget", price=9.99)


# --- App with non-JSON response class ---

app_non_json = FastAPI()


@app_non_json.get("/text", response_class=HTMLResponse)
def get_html():
    return "<h1>Hello</h1>"


# --- App for by_alias test ---

app_alias = FastAPI()


@app_alias.get("/aliased")
def get_aliased() -> AliasedItem:
    return AliasedItem(itemName="gadget", price=5.0)


@app_alias.get("/aliased-explicit", response_class=JSONResponse)
def get_aliased_explicit() -> AliasedItem:
    return AliasedItem(itemName="gadget", price=5.0)


# --- App for validation error media type test ---

app_validation = FastAPI()


@app_validation.get("/item/{item_id}")
def get_validation_item(item_id: int) -> Item:
    return Item(name="widget", price=9.99)


@app_validation.get(
    "/item-explicit/{item_id}", response_class=JSONResponse
)
def get_validation_item_explicit(item_id: int) -> Item:
    return Item(name="widget", price=9.99)


# --- Tests ---


def _assert_fast_path(client: TestClient, path: str) -> None:
    with patch(
        "starlette.responses.json.dumps", wraps=__import__("json").dumps
    ) as mock_dumps:
        response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"name": "widget", "price": 9.99}
    mock_dumps.assert_not_called()


def test_default_response_class_uses_fast_path():
    client = TestClient(app_default)
    _assert_fast_path(client, "/item")


def test_explicit_json_response_uses_fast_path():
    client = TestClient(app_explicit)
    _assert_fast_path(client, "/item")


def test_custom_json_subclass_uses_fast_path():
    client = TestClient(app_custom)
    with patch(
        "starlette.responses.json.dumps", wraps=__import__("json").dumps
    ) as mock_dumps:
        response = client.get("/item")
    assert response.status_code == 200
    assert response.json() == {"name": "widget", "price": 9.99}
    assert response.headers["content-type"] == "application/vnd.custom+json"
    mock_dumps.assert_not_called()


def test_global_default_response_class_uses_fast_path():
    client = TestClient(app_global)
    _assert_fast_path(client, "/item")


def test_global_custom_subclass_uses_fast_path():
    client = TestClient(app_global_custom)
    with patch(
        "starlette.responses.json.dumps", wraps=__import__("json").dumps
    ) as mock_dumps:
        response = client.get("/item")
    assert response.status_code == 200
    assert response.json() == {"name": "widget", "price": 9.99}
    assert response.headers["content-type"] == "application/vnd.custom+json"
    mock_dumps.assert_not_called()


def test_non_json_response_class_skips_fast_path():
    client = TestClient(app_non_json)
    response = client.get("/text")
    assert response.status_code == 200
    assert response.text == "<h1>Hello</h1>"
    assert "text/html" in response.headers["content-type"]


def test_by_alias_preserved_with_default_class():
    client = TestClient(app_alias)
    response = client.get("/aliased")
    assert response.status_code == 200
    data = response.json()
    assert "itemName" in data
    assert "item_name" not in data
    assert data == {"itemName": "gadget", "price": 5.0}


def test_by_alias_preserved_with_explicit_class():
    client = TestClient(app_alias)
    response = client.get("/aliased-explicit")
    assert response.status_code == 200
    data = response.json()
    assert "itemName" in data
    assert "item_name" not in data
    assert data == {"itemName": "gadget", "price": 5.0}


def test_validation_error_media_type_default():
    client = TestClient(app_validation)
    response = client.get("/item/not-an-int")
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert "detail" in response.json()


def test_validation_error_media_type_explicit():
    client = TestClient(app_validation)
    response = client.get("/item-explicit/not-an-int")
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert "detail" in response.json()
