import os
from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

BASE = Path(__file__).parent
APP_ENV = os.environ.get("APP_ENV", "development")

DEFAULTS: Dict[str, Any] = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# OS-level layer assigned for this task; real environment variables win if present.
ASSIGNED_OS_ENV = {"APP_PORT": "8800", "APP_WORKERS": "3"}

ALIASES = {"num_workers": "workers"}
INT_KEYS = {"port", "workers"}
TRUE_VALUES = {"true", "1", "yes", "on"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def coerce(key: str, value: Any) -> Any:
    if key in INT_KEYS:
        if isinstance(value, bool):
            return int(value)
        try:
            return int(str(value).strip())
        except ValueError:
            raise HTTPException(400, f"{key} must be an integer")
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in TRUE_VALUES
    return str(value)


def norm_key(k: str) -> str:
    k = k.strip().lower()
    return ALIASES.get(k, k)


def load_yaml() -> Dict[str, Any]:
    p = BASE / f"config.{APP_ENV}.yaml"
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    return {norm_key(str(k)): v for k, v in data.items()}


def load_dotenv() -> Dict[str, Any]:
    p = BASE / ".env"
    out: Dict[str, Any] = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k.upper().startswith("APP_"):
            k = k[4:]
        out[norm_key(k)] = v
    return out


def load_os_env() -> Dict[str, Any]:
    env = dict(ASSIGNED_OS_ENV)
    env.update({k: v for k, v in os.environ.items() if k.startswith("APP_")})
    return {norm_key(k[4:]): v for k, v in env.items() if k != "APP_ENV"}


@app.get("/effective-config")
def effective_config(set: List[str] = Query(default=[])):
    merged: Dict[str, Any] = dict(DEFAULTS)
    for layer in (load_yaml(), load_dotenv(), load_os_env()):
        merged.update(layer)
    for item in set:
        if "=" not in item:
            raise HTTPException(400, f"Invalid set parameter: {item}")
        k, v = item.split("=", 1)
        merged[norm_key(k)] = v
    result = {k: coerce(k, v) for k, v in merged.items()}
    result["api_key"] = "****"
    return result


@app.get("/")
def root():
    return {"status": "ok", "endpoint": "/effective-config"}
