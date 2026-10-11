"""Tools the agent can call. Each tool returns a plain string."""
import ast
import operator as op
from datetime import datetime
from pathlib import Path

import requests

WORKSPACE = Path(__file__).parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)

# ---------- calculator (safe, no eval) ----------
_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
        ast.Pow: op.pow, ast.Mod: op.mod, ast.USub: op.neg, ast.FloorDiv: op.floordiv}

def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")

def calculator(expression: str) -> str:
    try:
        return str(_eval(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"Error: {e}"

# ---------- weather (Open-Meteo, no API key) ----------
def get_weather(city: str) -> str:
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1}, timeout=10).json()
        if not g.get("results"):
            return f"City '{city}' not found."
        r = g["results"][0]
        w = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": r["latitude"], "longitude": r["longitude"],
                                 "current": "temperature_2m,relative_humidity_2m,wind_speed_10m"},
                         timeout=10).json()["current"]
        return (f"{r['name']}, {r.get('country','')}: {w['temperature_2m']}°C, "
                f"humidity {w['relative_humidity_2m']}%, wind {w['wind_speed_10m']} km/h")
    except Exception as e:
        return f"Error: {e}"

# ---------- web search ----------
def web_search(query: str) -> str:
    try:
        from ddgs import DDGS
        hits = DDGS().text(query, max_results=5)
        return "\n".join(f"- {h['title']}: {h['body']} ({h['href']})" for h in hits) or "No results."
    except Exception as e:
        return f"Error: {e}"

# ---------- file tools (sandboxed to ./workspace) ----------
def _safe(name: str) -> Path:
    p = (WORKSPACE / name).resolve()
    if WORKSPACE.resolve() not in p.parents and p != WORKSPACE.resolve():
        raise ValueError("path outside workspace")
    return p

def write_file(filename: str, content: str) -> str:
    try:
        _safe(filename).write_text(content, encoding="utf-8")
        return f"Saved {filename}"
    except Exception as e:
        return f"Error: {e}"

def read_file(filename: str) -> str:
    try:
        return _safe(filename).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: {e}"

def get_datetime() -> str:
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

# ---------- registry + schemas given to the LLM ----------
REGISTRY = {f.__name__: f for f in
            [calculator, get_weather, web_search, write_file, read_file, get_datetime]}

def _s(name, desc, props=None, req=None):
    d = {"name": name, "description": desc}
    if props:
        d["parameters"] = {"type": "object", "properties": props, "required": req or list(props)}
    return d

STR = lambda d: {"type": "string", "description": d}

TOOL_SCHEMAS = [
    _s("calculator", "Evaluate a math expression, e.g. '(12*7)/3'.", {"expression": STR("Math expression")}),
    _s("get_weather", "Get current weather for a city.", {"city": STR("City name")}),
    _s("web_search", "Search the web for up-to-date information.", {"query": STR("Search query")}),
    _s("write_file", "Save text to a file in the workspace folder.",
       {"filename": STR("File name, e.g. notes.txt"), "content": STR("Text to write")}),
    _s("read_file", "Read a text file from the workspace folder.", {"filename": STR("File name")}),
    _s("get_datetime", "Get the current date and time."),
]
