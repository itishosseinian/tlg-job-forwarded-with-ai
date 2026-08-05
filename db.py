import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def read(name: str) -> dict:
    p = DATA_DIR / f"{name}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def write(name: str, data: dict) -> None:
    p = DATA_DIR / f"{name}.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def next_id(data: dict) -> str:
    """Return the next integer ID as a string."""
    if not data:
        return "1"
    return str(max(int(k) for k in data.keys()) + 1)
