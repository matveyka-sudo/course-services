from copy import deepcopy
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from src.core.config import ROOT


def build_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema is not None:
        return app.openapi_schema
    contract = yaml.safe_load((ROOT / "openapi.yaml").read_text())
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["servers"] = contract["servers"]
    schema["tags"] = contract["tags"]
    schema["info"]["description"] = contract["info"]["description"]
    components = deepcopy(contract["components"])
    components.setdefault("schemas", {}).update(
        schema.get("components", {}).get("schemas", {})
    )
    schema["components"] = components
    for path, path_item in schema["paths"].items():
        original_path = contract["paths"].get(path, {})
        if "parameters" in original_path:
            path_item["parameters"] = original_path["parameters"]
        for method, operation in path_item.items():
            if method not in {"get", "post", "patch", "delete"}:
                continue
            original = original_path.get(method)
            if original is None:
                continue
            for key in ("summary", "description", "x-roles"):
                if key in original:
                    operation[key] = original[key]
            operation["parameters"] = original.get("parameters", [])
            responses = deepcopy(original["responses"])
            for status, response in operation["responses"].items():
                if status.startswith("2"):
                    response["description"] = responses.get(status, {}).get(
                        "description", response["description"]
                    )
                    responses[status] = response
            operation["responses"] = responses
    add_request_id_headers(schema)
    app.openapi_schema = schema
    return schema


def add_request_id_headers(schema: dict[str, Any]) -> None:
    request_id_header = {
        "description": "Идентификатор запроса для поиска в логах",
        "schema": {"type": "string", "format": "uuid"},
    }
    for response in schema["components"].get("responses", {}).values():
        response.setdefault("headers", {})["X-Request-ID"] = request_id_header
    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method not in {"get", "post", "patch", "delete"}:
                continue
            for response in operation["responses"].values():
                if "$ref" not in response:
                    response.setdefault("headers", {})[
                        "X-Request-ID"
                    ] = request_id_header
