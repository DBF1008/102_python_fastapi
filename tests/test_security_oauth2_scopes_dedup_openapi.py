from typing import Annotated

from fastapi import Depends, FastAPI, Security
from fastapi.security import OAuth2AuthorizationCodeBearer, SecurityScopes
from fastapi.testclient import TestClient
from inline_snapshot import snapshot

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="authorize",
    tokenUrl="token",
    scopes={"items": "Items access", "read": "Read access", "write": "Write access"},
)

app = FastAPI()


# Scenario 1: Same scheme in two sibling dependency chains with different scopes
async def dep_read(
    token: Annotated[str, Security(oauth2_scheme, scopes=["read"])],
):
    return token


async def dep_write(
    token: Annotated[str, Security(oauth2_scheme, scopes=["write"])],
):
    return token


@app.get("/multi-scope")
async def multi_scope_endpoint(
    r: Annotated[str, Depends(dep_read)],
    w: Annotated[str, Depends(dep_write)],
):
    return {"r": r, "w": w}


# Scenario 2: Deep 3-level chain with Security at each level
async def dep_inner(
    scopes: SecurityScopes,
    token: Annotated[str, Security(oauth2_scheme, scopes=["write"])],
):
    return token


async def dep_outer(
    scopes: SecurityScopes,
    inner: Annotated[str, Security(dep_inner, scopes=["items"])],
):
    return inner


@app.get("/deep")
async def deep_endpoint(
    result: Annotated[str, Security(dep_outer, scopes=["read"])],
):
    return {"result": result}


# Scenario 3: Same scheme both directly and indirectly
async def dep_via_depends(token: Annotated[str, Depends(oauth2_scheme)]):
    return token


@app.get("/direct-and-indirect")
async def direct_and_indirect_endpoint(
    t1: Annotated[str, Security(oauth2_scheme, scopes=["read"])],
    t2: Annotated[str, Depends(dep_via_depends)],
):
    return {"t1": t1, "t2": t2}


# Scenario 4: Overlapping scopes across chains
async def dep_rw(
    token: Annotated[str, Security(oauth2_scheme, scopes=["read", "write"])],
):
    return token


async def dep_ri(
    token: Annotated[str, Security(oauth2_scheme, scopes=["read", "items"])],
):
    return token


@app.get("/overlapping")
async def overlapping_endpoint(
    a: Annotated[str, Depends(dep_rw)],
    b: Annotated[str, Depends(dep_ri)],
):
    return {"a": a, "b": b}


client = TestClient(app)


def test_multi_scope():
    response = client.get("/multi-scope", headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200


def test_deep():
    response = client.get("/deep", headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200


def test_direct_and_indirect():
    response = client.get(
        "/direct-and-indirect", headers={"Authorization": "Bearer testtoken"}
    )
    assert response.status_code == 200


def test_overlapping():
    response = client.get(
        "/overlapping", headers={"Authorization": "Bearer testtoken"}
    )
    assert response.status_code == 200


def test_openapi_schema():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json() == snapshot(
        {
            "openapi": "3.1.0",
            "info": {"title": "FastAPI", "version": "0.1.0"},
            "paths": {
                "/multi-scope": {
                    "get": {
                        "summary": "Multi Scope Endpoint",
                        "operationId": "multi_scope_endpoint_multi_scope_get",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {"application/json": {"schema": {}}},
                            }
                        },
                        "security": [
                            {
                                "OAuth2AuthorizationCodeBearer": [
                                    "read",
                                    "write",
                                ]
                            }
                        ],
                    }
                },
                "/deep": {
                    "get": {
                        "summary": "Deep Endpoint",
                        "operationId": "deep_endpoint_deep_get",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {"application/json": {"schema": {}}},
                            }
                        },
                        "security": [
                            {
                                "OAuth2AuthorizationCodeBearer": [
                                    "items",
                                    "read",
                                    "write",
                                ]
                            }
                        ],
                    }
                },
                "/direct-and-indirect": {
                    "get": {
                        "summary": "Direct And Indirect Endpoint",
                        "operationId": "direct_and_indirect_endpoint_direct_and_indirect_get",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {"application/json": {"schema": {}}},
                            }
                        },
                        "security": [
                            {"OAuth2AuthorizationCodeBearer": ["read"]}
                        ],
                    }
                },
                "/overlapping": {
                    "get": {
                        "summary": "Overlapping Endpoint",
                        "operationId": "overlapping_endpoint_overlapping_get",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {"application/json": {"schema": {}}},
                            }
                        },
                        "security": [
                            {
                                "OAuth2AuthorizationCodeBearer": [
                                    "items",
                                    "read",
                                    "write",
                                ]
                            }
                        ],
                    }
                },
            },
            "components": {
                "securitySchemes": {
                    "OAuth2AuthorizationCodeBearer": {
                        "type": "oauth2",
                        "flows": {
                            "authorizationCode": {
                                "scopes": {
                                    "items": "Items access",
                                    "read": "Read access",
                                    "write": "Write access",
                                },
                                "authorizationUrl": "authorize",
                                "tokenUrl": "token",
                            }
                        },
                    }
                }
            },
        }
    )
