# Plan: Router-level `openapi_extra` for FastAPI

## Context

FastAPI 目前只在单个路由级别支持 `openapi_extra`（如 `@app.get("/", openapi_extra={...})`），无法在 `APIRouter` 或 `include_router` 层级统一下发一组 OpenAPI 扩展字段。对于需要批量挂载网关扩展字段（`x-*`）的场景，只能逐路由手写，维护成本高。

本次改动在 `APIRouter.__init__` 和 `include_router` 上新增 `openapi_extra` 参数，利用已有的 `deep_dict_update` 工具做三层深度合并，route 级字段始终优先。

## Merge Semantics (三层合并)

```
include_router(openapi_extra=A)     ← 最外层，最低优先级
       ↓ deep_dict_update
APIRouter(openapi_extra=B)          ← 中间层
       ↓ deep_dict_update
@router.get("/", openapi_extra=C)   ← 最内层，最高优先级
       ↓
最终 route.openapi_extra = deep_dict_update(deep_dict_update(A, B), C)
```

`deep_dict_update(main, update)` 行为：
- dict → 递归合并
- list → 拼接
- 标量 → `update` 覆盖 `main`

**Mutation safety**：每次合并前用 `copy.deepcopy` 复制 base dict，防止原始 dict 被污染。

---

## Changes

### 1. `fastapi/routing.py`

#### 1a. 新增 import
```python
import copy  # 在 stdlib import 区添加
```
在已有的 `from fastapi.utils import (...)` 中添加 `deep_dict_update`。

#### 1b. `APIRouter.__init__`（~line 1032）
- 在 `responses` 参数之后添加 `openapi_extra` 参数：
  ```python
  openapi_extra: Annotated[
      dict[str, Any] | None,
      Doc("Extra OpenAPI schema extensions for all path operations in this router.")
  ] = None,
  ```
- 在属性存储区（~line 1309 `self.responses = responses or {}` 之后）添加：
  ```python
  self.openapi_extra: dict[str, Any] | None = openapi_extra
  ```

#### 1c. `APIRouter.add_api_route`（~line 1367）
在 `combined_responses` 计算之后、route 构造之前（~line 1370 之后），添加合并逻辑：
```python
# Merge router-level openapi_extra with route-level (route wins)
if self.openapi_extra is not None:
    combined_openapi_extra = copy.deepcopy(self.openapi_extra)
    if openapi_extra is not None:
        deep_dict_update(combined_openapi_extra, openapi_extra)
else:
    combined_openapi_extra = openapi_extra
```
将 route 构造中的 `openapi_extra=openapi_extra` 改为 `openapi_extra=combined_openapi_extra`。

#### 1d. `APIRouter.include_router`（~line 1578）
- 在 `callbacks` 参数之后添加 `openapi_extra` 参数（同上签名）。
- 在 APIRoute 循环内（~line 1789 `openapi_extra=route.openapi_extra` 处），替换为：
```python
# Merge include-level openapi_extra with route's (already merged with sub-router-level)
if openapi_extra is not None:
    final_openapi_extra = copy.deepcopy(openapi_extra)
    if route.openapi_extra is not None:
        deep_dict_update(final_openapi_extra, route.openapi_extra)
else:
    final_openapi_extra = route.openapi_extra
```
传 `openapi_extra=final_openapi_extra` 给 `self.add_api_route(...)`。

### 2. `fastapi/applications.py`

#### 2a. `FastAPI.include_router`（~line 1358）
- 在 `callbacks` 参数之后添加同样的 `openapi_extra` 参数。
- 在 `self.router.include_router(...)` 转发调用中添加 `openapi_extra=openapi_extra`。

### 3. 不需要改动的文件
- `fastapi/utils.py` — `deep_dict_update` 已存在
- `fastapi/openapi/utils.py` — 已经在 schema 生成时消费 `route.openapi_extra`，无需修改

---

## Tests

新建 `tests/test_openapi_router_extensions.py`，覆盖：

| 测试 | 验证点 |
|------|--------|
| `test_router_level_openapi_extra` | Router 级 `x-*` 扩展应用到所有路由 |
| `test_route_level_overrides_router_level` | Route 级字段覆盖 router 级，未冲突字段保留 |
| `test_include_router_openapi_extra` | 三层合并：include > router > route，route 优先 |
| `test_nested_routers_partial_override` | 嵌套路由（outer → inner），inner router 覆盖 outer router |
| `test_deep_merge_nested_dicts` | 嵌套 dict 递归合并 + list 拼接 |
| `test_no_mutation_of_original_dicts` | 原始 dict 不被合并过程污染 |

使用 `FastAPI` + `TestClient` + 手写 assert（与现有测试风格一致）。

---

## Verification

1. 运行新测试：`pytest tests/test_openapi_router_extensions.py -v`
2. 运行已有 `openapi_extra` 测试确认无回归：`pytest tests/test_openapi_route_extensions.py tests/test_openapi_query_parameter_extension.py -v`
3. 运行完整测试套件：`pytest`
