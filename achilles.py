"""
Achilles — standalone workout tracker (Flet desktop dashboard).

Run:  python achilles.py
Deps: pip install -r requirements.txt
Later (exe):  flet pack achilles.py
Data: data.json next to this file
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import flet as ft
from flet.controls.core import canvas as cv
from flet.controls.painting import Paint, PaintingStyle

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
BG = "#0b1220"
SIDEBAR = "#0e1626"
SURFACE = "#162033"
SURFACE2 = "#1d2b40"
BORDER = "#2a3b55"
TEXT = "#eef2f7"
MUTED = "#8b97ab"
GOLD = "#d4a84b"
GOLD_DIM = "#9a7a28"
GREEN = "#3dd68c"
CRIMSON = "#e05a4f"
BLUE = "#6aaee8"

BLOCK_TITLES = {"strength": "STRENGTH", "core": "CORE", "cardio": "CARDIO"}
DATA_VERSION = 5
MEASUREMENT_FIELDS = [
    ("weight", "Body weight", "lb"),
    ("body_fat", "Body fat", "%"),
    ("muscle_mass", "Muscle mass", "lb"),
    ("waist", "Waist", "in"),
    ("arm", "Arm", "in"),
    ("leg", "Leg", "in"),
    ("shoulders", "Shoulders", "in"),
]
WAVE_LOAD_PCT = {1: 0.80, 2: 0.85, 3: 0.90, 4: 1.00}
WAVE_4_GOAL_PCT = 1.05
CHART_COLORS = [GOLD, BLUE, GREEN, CRIMSON, "#c084fc", "#fb923c", "#67e8f9"]
NAV = {
    "dashboard": 0,
    "log": 1,
    "strength": 2,
    "goals": 3,
    "program": 4,
    "history": 5,
    "measurements": 6,
}
PB_LIFTS = [
    {"name": "Marathon Builder", "metric": "distance", "unit": "mi", "higher": True, "auto": "plus_one_mile"},
    {"name": "Chin-Ups (Max reps)", "metric": "reps", "unit": "reps", "higher": True},
    {"name": "Weighted Chin-Ups", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Overhead Press", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Plank", "metric": "seconds", "unit": "sec", "higher": True},
    {"name": "Squat", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Trap-Bar Deadlift", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Bench", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Pull-Ups (reps)", "metric": "reps", "unit": "reps", "higher": True},
    {"name": "Weighted Pull-Ups", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Curls", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Skull-Crushers", "metric": "weight", "unit": "lb", "higher": True},
    {"name": "Mile Time", "metric": "pace", "unit": "min/mi", "higher": False},
    {"name": "Push-Ups (reps)", "metric": "reps", "unit": "reps", "higher": True},
    {"name": "Dead Hang", "metric": "seconds", "unit": "sec", "higher": True},
]
PB_ALIASES = {
    "Squat": ["Squat", "Squat Power Waves"],
    "Trap-Bar Deadlift": ["Trap-Bar Deadlift", "Trap-Bar Deadlift Power Waves"],
    "Bench": ["Bench", "Bench Power Waves"],
    "Overhead Press": ["Overhead Press"],
    "Weighted Chin-Ups": ["Weighted Chin-Ups", "Chin-Ups"],
    "Chin-Ups (Max reps)": ["Chin-Ups (Max reps)", "Chin-Ups (max)", "Chin-Ups"],
    "Weighted Pull-Ups": ["Weighted Pull-Ups", "Pull-Ups"],
    "Pull-Ups (reps)": ["Pull-Ups (reps)", "Pull-Ups"],
    "Curls": ["Curls"],
    "Skull-Crushers": ["Skull-Crushers", "Skull-crushers"],
    "Marathon Builder": ["Marathon Builder"],
    "Plank": ["Plank"],
    "Mile Time": ["Mile Time", "1 Mile"],
    "Push-Ups (reps)": ["Push-Ups (reps)", "Push-ups"],
    "Dead Hang": ["Dead Hang"],
}
SEED_GOALS = {
    "Squat": 425,
    "Trap-Bar Deadlift": 575,
    "Bench": 315,
    "Overhead Press": 225,
    "Weighted Chin-Ups": 135,
}
SPEED_NAMES = {"Speed Trap Bar", "Speed Squats", "Speed Cleans"}
TOTAL_LIFTS = ("Bench", "Squat", "Trap-Bar Deadlift")


def E(
    name: str,
    kind: str,
    scheme: str,
    block: str = "strength",
    focus: bool = False,
    **kw: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "scheme": scheme,
        "block": block,
        "focus": focus,
        "highlight": bool(kw.pop("highlight", False) or focus),
    }
    item.update(kw)
    return item


DEFAULT_PROGRAM = [
    {
        "day": 1,
        "name": "Marathon Builder",
        "short": "Marathon",
        "is_rest": False,
        "tag": "Run",
        "exercises": [
            E(
                "Marathon Builder",
                "run",
                "1 long run — push maximum distance each cycle. Track distance and pace.",
                "cardio",
                highlight=True,
                focus_metric="distance",
            ),
        ],
    },
    {
        "day": 2,
        "name": "Upper B",
        "short": "Upper B",
        "is_rest": False,
        "tag": "Push / pull",
        "exercises": [
            E(
                "Weighted Chin-Ups",
                "power_wave",
                "1 warm-up, 4× Power Waves (weighted), 1 close-set max reps",
                highlight=True,
                has_max=True,
                one_rm_key="Weighted Chin-Ups",
                max_pb_key="Chin-Ups (Max reps)",
            ),
            E("Overhead Press", "power_wave", "1 warm-up, 4× Power Waves", highlight=True, one_rm_key="Overhead Press"),
            E("Chest-Supported DB Row", "strength", "1 warm-up + 3×8–10"),
            E("DB Bench", "strength", "1 warm-up, 3×8–10"),
            E("Row Machine", "strength", "2×8–10"),
            E("Lat Pull-down", "strength", "2×8–10"),
            E("Accessory Curls", "strength", "2×8–10"),
            E("Band Pull-aparts", "reps", "2×12–15"),
            E("Recovery Bike", "bike", "Easy–moderate recovery ride", "cardio"),
        ],
    },
    {
        "day": 3,
        "name": "Core A",
        "short": "Core A",
        "is_rest": False,
        "tag": "Core + bike",
        "exercises": [
            E("Sit-ups", "reps", "4×30+", "core"),
            E("Pallof Holds", "timed", "3×30 seconds+", "core"),
            E("Plank", "timed", "1× max time", "core", highlight=True),
            E("Russian Twists", "max_reps", "1× max reps", "core"),
            E("Alternating Toe Taps", "reps", "2×16", "core"),
            E("Long Bike Ride", "bike", "Long ride after core", "cardio"),
        ],
    },
    {
        "day": 4,
        "name": "Lower B",
        "short": "Lower B",
        "is_rest": False,
        "tag": "Squat",
        "exercises": [
            E("Box Jumps", "reps", "3×6–8"),
            E(
                "Squat Power Waves",
                "power_wave",
                "2× warm-up, 4× Power Waves, 1× cool-down",
                highlight=True,
                one_rm_key="Squat",
            ),
            E("Speed Trap Bar", "strength", "6×2–5", speed=True, one_rm_key="Trap-Bar Deadlift"),
            E("Light Lunge", "strength", "2×8–10"),
            E("Calf Raises", "strength", "3×15"),
            E("Leg Extensions", "strength", "2×12–15"),
            E("Short Run", "run", "Short run finisher", "cardio", focus_metric="pace"),
        ],
    },
    {
        "day": 5,
        "name": "Upper A",
        "short": "Upper A",
        "is_rest": False,
        "tag": "Bench / pull",
        "exercises": [
            E(
                "Bench Power Waves",
                "power_wave",
                "2× warm-up, 4× Power Waves, 1× cool-down",
                highlight=True,
                one_rm_key="Bench",
            ),
            E(
                "Weighted Pull-Ups",
                "power_wave",
                "1× warm-up, 4× Power Waves, 1× max reps",
                highlight=True,
                has_max=True,
                one_rm_key="Weighted Pull-Ups",
                max_pb_key="Pull-Ups (reps)",
            ),
            E("Incline DB Press", "strength", "3×8–10"),
            E("Bird Dog Rows", "strength", "3×8–10"),
            E("Dips", "max_reps", "2× max"),
            E("DB Shoulder Press", "strength", "2×8–10"),
            E("Band Pull-aparts", "reps", "2×12–15"),
            E("Overhead Tricep Extension", "strength", "2×10"),
            E("Moderate Run", "run", "Moderate run finisher", "cardio", focus_metric="pace"),
        ],
    },
    {
        "day": 6,
        "name": "Tempo Run",
        "short": "Tempo",
        "is_rest": False,
        "tag": "Run",
        "exercises": [
            E(
                "Tempo Run",
                "run",
                "Track distance and pace. Beat last Marathon Builder pace.",
                "cardio",
                focus_metric="pace",
            ),
        ],
    },
    {
        "day": 7,
        "name": "Lower A",
        "short": "Lower A",
        "is_rest": False,
        "tag": "Deadlift",
        "exercises": [
            E(
                "Trap-Bar Deadlift Power Waves",
                "power_wave",
                "3× warm-up, 4× Power Waves, 1× cool-down",
                highlight=True,
                one_rm_key="Trap-Bar Deadlift",
            ),
            E("Speed Squats", "strength", "6×2–5", speed=True, one_rm_key="Squat"),
            E("Bulgarian Lunges", "strength", "2×8–10"),
            E("Side Lunge Squats (barbell)", "strength", "1×10 each side"),
            E("Hamstring Curls", "strength", "2×12–15"),
            E("Leg Extensions", "strength", "2×12–15"),
            E("Wall Squat", "timed", "1× max"),
            E("Moderate Bike", "bike", "Moderate bike finisher", "cardio"),
        ],
    },
    {
        "day": 8,
        "name": "Arms",
        "short": "Arms",
        "is_rest": False,
        "tag": "Arms + mile",
        "exercises": [
            E("Push-ups", "max_reps", "1× max reps", highlight=True, pb_key="Push-Ups (reps)"),
            E("Curls", "power_wave", "1× warm-up, 3× Power Waves", highlight=True, one_rm_key="Curls"),
            E("Skull-crushers", "power_wave", "1× warm-up, 3× Power Waves", highlight=True, one_rm_key="Skull-Crushers"),
            E("Lateral Raises", "strength", "3×6–15 (fatigue dictates weight)"),
            E("Inside Hammer Curls", "strength", "3×8–10"),
            E("Overhead Tricep Extension", "strength", "3×8–12"),
            E("DB Shoulder Press", "strength", "3×8–12"),
            E("Archer Pulls", "strength", "2×8–10"),
            E("Chin-Ups (Max reps)", "max_reps", "1× max reps", highlight=True),
            E("Dips (max)", "max_reps", "1× max reps"),
            E(
                "1 Mile",
                "run",
                "1 mile, fast as possible. Track pace.",
                "cardio",
                highlight=True,
                focus_metric="pace",
                fixed_distance=1,
                pb_key="Mile Time",
            ),
        ],
    },
    {
        "day": 9,
        "name": "Core B",
        "short": "Core B",
        "is_rest": False,
        "tag": "Core + flush",
        "exercises": [
            E("Sit-ups", "reps", "4×30+", "core"),
            E("Side Planks", "timed", "2×45 seconds+", "core"),
            E("Supermans", "timed", "2×60 seconds+", "core"),
            E("Dead Hang", "timed", "1× max", "core", highlight=True),
            E("Pistol Squats (BOSU)", "reps", "1×10", "core"),
            E("Single-Leg Deadlift (BOSU)", "reps", "1×25", "core"),
            E("Flush Cardio", "cardio_choice", "Flush legs with bike or light run", "cardio"),
        ],
    },
]


def clone_program() -> list[dict[str, Any]]:
    return json.loads(json.dumps(DEFAULT_PROGRAM))


def program_is_current(program: Any) -> bool:
    if not (isinstance(program, list) and len(program) == 9 and isinstance(program[0], dict)):
        return False
    if not isinstance(program[0].get("exercises"), list):
        return False
    day2 = next((d for d in program if d.get("day") == 2), None)
    day7 = next((d for d in program if d.get("day") == 7), None)
    day8 = next((d for d in program if d.get("day") == 8), None)
    if not day2 or not day7 or not day8:
        return False
    names2 = [e.get("name") for e in day2.get("exercises") or []]
    names7 = [e.get("name") for e in day7.get("exercises") or []]
    names8 = [e.get("name") for e in day8.get("exercises") or []]
    hammers = next((e for e in (day8.get("exercises") or []) if e.get("name") == "Inside Hammer Curls"), None)
    hammer_scheme = (hammers or {}).get("scheme") or ""
    return (
        "Weighted Chin-Ups" in names2
        and "Speed Cleans" not in names7
        and "Leg Extensions" in names7
        and "DB Shoulder Press" in names8
        and hammer_scheme.startswith("3")
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def legacy_data_path() -> Path:
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "Achilles" / "data.json"
    return Path.home() / ".achilles" / "data.json"


def data_path() -> Path:
    local = app_dir() / "data.json"
    if not local.exists():
        old = legacy_data_path()
        if old.exists():
            local.write_bytes(old.read_bytes())
    return local


WAVE_COUNT_RE = re.compile(r"(\d+)\s*[×x]\s*Power Waves", re.I)
WARMUP_RE = re.compile(r"\d+\s*[×x]?\s*warm-?ups?", re.I)
WORK_SET_RE = re.compile(r"(\d+)\s*[×x]\s*(?:\d|max)", re.I)


def epley_1rm(weight: float, reps: int) -> float:
    if reps <= 1:
        return weight
    return round(weight * (1 + reps / 30.0), 1)


def power_wave_meta(ex: dict[str, Any]) -> dict[str, Any]:
    scheme = ex.get("scheme") or ""
    count = int(ex.get("wave_count") or 0)
    if not count:
        match = WAVE_COUNT_RE.search(scheme)
        count = int(match.group(1)) if match else 4
    if "cooldown" in ex:
        cooldown = bool(ex.get("cooldown"))
    else:
        cooldown = "cool-down" in scheme.lower() or "cooldown" in scheme.lower()
    return {"count": max(1, count), "cooldown": cooldown, "has_max": bool(ex.get("has_max"))}


def scheme_work_count(ex: dict[str, Any], last: dict[str, Any] | None = None) -> int:
    if ex.get("work_count"):
        return max(1, int(ex["work_count"]))
    cleaned = WARMUP_RE.sub(" ", ex.get("scheme") or "")
    match = WORK_SET_RE.search(cleaned)
    if match:
        return max(1, int(match.group(1)))
    if last:
        raw = last.get("work_sets")
        if isinstance(raw, list) and raw:
            nums = [int(s.get("n") or 0) for s in raw if isinstance(s, dict)]
            return max(1, max(nums) if nums else len(raw))
        if last.get("sets"):
            return max(1, int(last["sets"]))
    return 2


def parse_set_list(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        w = float(item.get("weight") or 0)
        r = int(item.get("reps") or 0)
        if w or r:
            out.append({"n": int(item.get("n") or i + 1), "weight": w, "reps": r})
    return out


def working_wave_sets(entry: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("wave_sets", "work_sets"):
        parsed = parse_set_list(entry.get(key))
        if parsed:
            return parsed
    w = float(entry.get("weight") or 0)
    r = int(entry.get("reps") or 0)
    if w or r:
        return [{"n": 1, "weight": w, "reps": r}]
    return []


def last_set_prefill(last: dict[str, Any] | None, index: int) -> dict[str, Any] | None:
    sets = working_wave_sets(last) if last else []
    by_n = {int(s.get("n") or i + 1): s for i, s in enumerate(sets)}
    if index + 1 in by_n:
        return by_n[index + 1]
    if len(sets) == 1:
        return sets[0]
    return None


def format_set_list(sets: list[dict[str, Any]], unit: str) -> str:
    parts: list[str] = []
    for item in sets:
        w, r = item.get("weight"), item.get("reps")
        if w and r:
            parts.append(f"{fmt_num(float(w))}×{int(r)}")
        elif w:
            parts.append(f"{fmt_num(float(w))} {unit}")
        elif r:
            parts.append(f"{int(r)} reps")
    return "  ·  ".join(parts)


def primary_wave_load(entry: dict[str, Any]) -> tuple[float, int]:
    best_w, best_r, best_e = 0.0, 0, 0.0
    for item in working_wave_sets(entry):
        w, r = float(item.get("weight") or 0), int(item.get("reps") or 0)
        est = epley_1rm(w, r) if w and r else w
        if est > best_e:
            best_w, best_r, best_e = w, r, est
    return best_w, best_r


def row_weight_reps(row: dict[str, Any]) -> list[tuple[float, int]]:
    if row.get("kind") in ("power_wave", "strength") or row.get("wave_sets") or row.get("work_sets"):
        return [(float(s.get("weight") or 0), int(s.get("reps") or 0)) for s in working_wave_sets(row)]
    w = float(row.get("weight") or 0)
    r = int(row.get("reps") or 0)
    return [(w, r)] if w or r else []


def parse_float(value: str) -> float | None:
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        n = int(float(text))
        return n if n > 0 else None
    except ValueError:
        return None


def parse_pace(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    if ":" in text:
        parts = text.split(":")
        if len(parts) != 2:
            return None
        minutes, seconds = parse_float(parts[0]), parse_float(parts[1])
        if minutes is None or seconds is None:
            return None
        return minutes + seconds / 60.0
    return parse_float(text)


def format_pace(minutes: float) -> str:
    if minutes <= 0:
        return "—"
    m = int(minutes)
    s = int(round((minutes - m) * 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"


def parse_duration_seconds(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    if ":" in text:
        parts = text.split(":")
        if len(parts) != 2:
            return None
        minutes, seconds = parse_float(parts[0]), parse_float(parts[1])
        if minutes is None or seconds is None:
            return None
        return minutes * 60 + seconds
    return parse_float(text)


def format_seconds(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{int(seconds)}s" if abs(seconds - int(seconds)) < 0.05 else f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = int(round(seconds % 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"


def fmt_num(n: float) -> str:
    if n <= 0:
        return "—"
    return str(int(n)) if abs(n - int(n)) < 0.05 else f"{n:.1f}"


def grouped_exercises(day: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    current_block: str | None = None
    current: list[dict[str, Any]] = []
    for ex in day.get("exercises") or []:
        block = ex.get("block") or "strength"
        if block != current_block:
            if current:
                groups.append((current_block or "strength", current))
            current_block = block
            current = [ex]
        else:
            current.append(ex)
    if current:
        groups.append((current_block or "strength", current))
    return groups


def focus_names(day: dict[str, Any]) -> list[str]:
    return [ex["name"] for ex in day.get("exercises") or [] if ex.get("highlight") or ex.get("focus")]


def pb_spec(name: str) -> dict[str, Any] | None:
    return next((item for item in PB_LIFTS if item["name"] == name), None)


def round_load(weight: float) -> float:
    if weight >= 100:
        return float(int(round(weight / 5.0) * 5))
    return round(weight, 1)


def is_highlighted(ex: dict[str, Any]) -> bool:
    return bool(ex.get("highlight") or ex.get("focus"))


def goal_spec(ex: dict[str, Any]) -> tuple[str, str, bool]:
    kind = ex.get("kind")
    metric = ex.get("focus_metric")
    if kind == "run":
        if metric == "pace":
            return "pace", "min/mi", False
        return "distance", "mi", True
    if kind == "timed":
        return "seconds", "sec", True
    if kind in ("max_reps", "reps"):
        return "reps", "reps", True
    if kind == "bike":
        return "minutes", "min", True
    return "e1rm", "lb", True


def format_logged(entry: dict[str, Any], unit: str) -> str:
    kind = entry.get("kind") or "strength"
    name = entry.get("name", "Exercise")
    bits: list[str] = []
    if kind == "run":
        if entry.get("distance"):
            bits.append(f"{fmt_num(float(entry['distance']))} mi")
        if entry.get("pace"):
            bits.append(f"{format_pace(float(entry['pace']))} /mi")
    elif kind == "bike":
        if entry.get("minutes"):
            bits.append(f"{fmt_num(float(entry['minutes']))} min")
        if entry.get("distance"):
            bits.append(f"{fmt_num(float(entry['distance']))} mi")
    elif kind == "cardio_choice":
        if entry.get("mode"):
            bits.append(str(entry["mode"]))
        if entry.get("minutes"):
            bits.append(f"{fmt_num(float(entry['minutes']))} min")
        if entry.get("distance"):
            bits.append(f"{fmt_num(float(entry['distance']))} mi")
    elif kind == "timed":
        if entry.get("seconds"):
            bits.append(format_seconds(float(entry["seconds"])))
    elif kind == "max_reps":
        if entry.get("reps"):
            bits.append(f"{entry['reps']} reps")
        if entry.get("weight"):
            bits.append(f"{fmt_num(float(entry['weight']))} {unit}")
    elif kind == "reps":
        sets, reps = entry.get("sets"), entry.get("reps")
        if sets and reps:
            bits.append(f"{sets}×{reps}")
        elif reps:
            bits.append(f"{reps} reps")
    elif kind == "power_wave":
        waves = working_wave_sets(entry)
        if waves:
            bits.append(format_set_list(waves, unit))
        cd = entry.get("cooldown") if isinstance(entry.get("cooldown"), dict) else {}
        if cd.get("weight") and cd.get("reps"):
            bits.append(f"cool-down {fmt_num(float(cd['weight']))}×{int(cd['reps'])}")
        elif cd.get("weight"):
            bits.append(f"cool-down {fmt_num(float(cd['weight']))} {unit}")
        elif cd.get("reps"):
            bits.append(f"cool-down {int(cd['reps'])} reps")
        if entry.get("max_reps"):
            bits.append(f"max {entry['max_reps']}")
        w, r = primary_wave_load(entry)
        if w and r:
            bits.append(f"est. 1RM {fmt_num(epley_1rm(w, r))}")
    else:
        work = parse_set_list(entry.get("work_sets"))
        if work:
            bits.append(format_set_list(work, unit))
            w, r = primary_wave_load(entry)
            if w and r:
                bits.append(f"est. 1RM {fmt_num(epley_1rm(w, r))}")
        else:
            w, s, r = entry.get("weight"), entry.get("sets"), entry.get("reps")
            if w:
                bits.append(f"{fmt_num(float(w))} {unit}")
            if s and r:
                bits.append(f"{s}×{r}")
            elif r:
                bits.append(f"{r} reps")
            if entry.get("max_reps"):
                bits.append(f"max {entry['max_reps']}")
            if w and r:
                bits.append(f"est. 1RM {fmt_num(epley_1rm(float(w), int(r)))}")
    return f"{name}  ·  " + "  ·  ".join(bits) if bits else name


def format_bits(entry: dict[str, Any], unit: str = "lb") -> str:
    line = format_logged(entry, unit)
    name = entry.get("name", "Exercise")
    prefix = f"{name}  ·  "
    return line[len(prefix):] if line.startswith(prefix) else line


def metric_text(metric: str, value: float, unit: str) -> str:
    if not value:
        return "—"
    if metric == "pace":
        return f"{format_pace(value)} /mi"
    if metric == "seconds":
        return format_seconds(value)
    if metric == "distance":
        return f"{fmt_num(value)} mi"
    if metric == "minutes":
        return f"{fmt_num(value)} min"
    if metric == "reps":
        return f"{fmt_num(value)} reps"
    if metric == "weight":
        return f"{fmt_num(value)} {unit}"
    return f"{fmt_num(value)} {unit}"


def y_format_for_metric(metric: str) -> Callable[[float], str]:
    if metric == "pace":
        return format_pace
    if metric == "seconds":
        return format_seconds
    return fmt_num


def chart_lift_key(ex: dict[str, Any]) -> str:
    return str(ex.get("one_rm_key") or ex.get("pb_key") or ex["name"])


def chart_shapes(
    width: float,
    height: float,
    series: list[tuple[str, str, list[tuple[datetime, float]]]],
    y_formatter: Callable[[float], str] | None = None,
) -> list[Any]:
    pad_l, pad_r, pad_t, pad_b = 52, 16, 18, 36
    shapes: list[Any] = []
    if width < 80 or height < 80:
        return shapes
    plot_w = max(10, width - pad_l - pad_r)
    plot_h = max(10, height - pad_t - pad_b)
    axis = Paint(color=BORDER, stroke_width=1)
    shapes.append(cv.Line(pad_l, pad_t, pad_l, pad_t + plot_h, paint=axis))
    shapes.append(cv.Line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, paint=axis))
    label = y_formatter or fmt_num
    if not series:
        shapes.append(
            cv.Text(
                width / 2,
                height / 2,
                value="Not enough history yet",
                style=ft.TextStyle(size=12, color=MUTED),
                alignment=ft.Alignment.CENTER,
            )
        )
        return shapes
    all_vals = [v for _n, _c, pts in series for _d, v in pts]
    all_dates = [d for _n, _c, pts in series for d, _v in pts]
    vmin, vmax = min(all_vals), max(all_vals)
    if abs(vmax - vmin) < 1e-6:
        vmin -= 1
        vmax += 1
    tmin, tmax = min(all_dates), max(all_dates)
    span = (tmax - tmin).total_seconds() or 1.0

    def xy(dt: datetime, val: float) -> tuple[float, float]:
        x = pad_l + ((dt - tmin).total_seconds() / span) * plot_w
        y = pad_t + plot_h - ((val - vmin) / (vmax - vmin)) * plot_h
        return x, y

    shapes.append(
        cv.Text(pad_l - 6, pad_t, value=label(vmax), style=ft.TextStyle(size=10, color=MUTED), alignment=ft.Alignment.CENTER_RIGHT)
    )
    shapes.append(
        cv.Text(
            pad_l - 6,
            pad_t + plot_h,
            value=label(vmin),
            style=ft.TextStyle(size=10, color=MUTED),
            alignment=ft.Alignment.CENTER_RIGHT,
        )
    )
    for _name, color, pts in series:
        paint = Paint(color=color, stroke_width=2, style=PaintingStyle.STROKE)
        ordered = sorted(pts, key=lambda p: p[0])
        for i in range(len(ordered) - 1):
            x1, y1 = xy(*ordered[i])
            x2, y2 = xy(*ordered[i + 1])
            shapes.append(cv.Line(x1, y1, x2, y2, paint=paint))
        for dt, val in ordered:
            x, y = xy(dt, val)
            shapes.append(cv.Circle(x, y, 3.5, paint=Paint(color=color, style=PaintingStyle.FILL)))
    legend_x = pad_l
    for name, color, _pts in series:
        shapes.append(cv.Rect(legend_x, height - 18, 10, 10, paint=Paint(color=color, style=PaintingStyle.FILL)))
        shapes.append(
            cv.Text(legend_x + 14, height - 13, value=name, style=ft.TextStyle(size=10, color=MUTED), alignment=ft.Alignment.CENTER_LEFT)
        )
        legend_x += max(70, 8 * len(name) + 28)
    return shapes


def time_chart(
    series: list[tuple[str, str, list[tuple[datetime, float]]]],
    height: int = 240,
    y_formatter: Callable[[float], str] | None = None,
) -> ft.Control:
    canvas = cv.Canvas(expand=True, height=height, shapes=chart_shapes(640, height, series, y_formatter))

    def on_resize(e: Any) -> None:
        canvas.shapes = chart_shapes(e.width, e.height, series, y_formatter)
        canvas.update()

    canvas.on_resize = on_resize
    return ft.Container(content=canvas, height=height, bgcolor=SURFACE, border_radius=12, padding=8)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
class Store:
    def __init__(self) -> None:
        self.path = data_path()
        self.data = self._load()

    def _default(self) -> dict[str, Any]:
        return {
            "version": DATA_VERSION,
            "unit": "lb",
            "wave": 1,
            "next_day": 1,
            "block": 1,
            "program": clone_program(),
            "goals": dict(SEED_GOALS),
            "one_rms": {},
            "sessions": [],
            "measurements": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            data = self._default()
            self._write(data)
            return data
        try:
            with self.path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError):
            loaded = {}
        data = self._default()
        data.update(loaded)
        for key, val in (
            ("goals", {}),
            ("one_rms", {}),
            ("sessions", []),
            ("measurements", []),
            ("next_day", 1),
            ("wave", 1),
            ("block", 1),
            ("unit", "lb"),
        ):
            data.setdefault(key, val)
        migrated = False
        if not program_is_current(data.get("program")):
            data["program"] = clone_program()
            migrated = True
        if int(data.get("version") or 0) < DATA_VERSION:
            data["version"] = DATA_VERSION
            migrated = True
            rms = data.setdefault("one_rms", {})
            goals = data.setdefault("goals", {})
            for name, val in list(rms.items()):
                goal = float(goals.get(name) or 0)
                seeded = float(SEED_GOALS.get(name) or 0)
                if (goal and abs(float(val) - goal) < 0.05) or (seeded and abs(float(val) - seeded) < 0.05):
                    del rms[name]
        goals = data.setdefault("goals", {})
        for name, val in SEED_GOALS.items():
            goals.setdefault(name, val)
        data.setdefault("one_rms", {})
        data["wave"] = max(1, min(4, int(data.get("wave") or 1)))
        data["next_day"] = max(1, min(9, int(data.get("next_day") or 1)))
        if migrated:
            self._write(data)
        return data

    def _write(self, data: dict[str, Any] | None = None) -> None:
        payload = data if data is not None else self.data
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def save(self) -> None:
        self._write()

    def clock(self) -> dict[str, Any]:
        wave = int(self.data.get("wave", 1))
        day = int(self.data.get("next_day", 1))
        program_day = (wave - 1) * 9 + day
        return {
            "wave": wave,
            "day": day,
            "program_day": program_day,
            "block": int(self.data.get("block", 1)),
            "is_1rm_wave": wave == 4,
            "headline": f"Wave {wave} - Day {day} - Program Day: {program_day}",
            "days_left": 36 - program_day + 1,
        }

    def program_day(self, day: int) -> dict[str, Any]:
        for item in self.data["program"]:
            if item["day"] == day:
                return item
        return self.data["program"][0]

    def next_program_day(self) -> dict[str, Any]:
        return self.program_day(int(self.data["next_day"]))

    def all_focus_exercises(self) -> list[dict[str, Any]]:
        seen: list[str] = []
        out: list[dict[str, Any]] = []
        for day in self.data["program"]:
            for ex in day.get("exercises") or []:
                if (ex.get("highlight") or ex.get("focus")) and ex["name"] not in seen:
                    seen.append(ex["name"])
                    out.append(ex)
        return out

    def sessions_for_names(self, names: list[str]) -> list[dict[str, Any]]:
        wanted = set(names)
        rows = []
        for session in self.data["sessions"]:
            try:
                dt = datetime.fromisoformat(session["date"])
            except ValueError:
                dt = None
            for entry in session.get("lifts", []):
                if entry.get("name") in wanted:
                    rows.append(
                        {
                            **entry,
                            "date": session["date"],
                            "dt": dt,
                            "session_wave": session.get("wave"),
                        }
                    )
        return rows

    def sessions_for_name(self, name: str) -> list[dict[str, Any]]:
        aliases = PB_ALIASES.get(name, [name])
        extra = [name]
        return self.sessions_for_names(list(dict.fromkeys(aliases + extra)))

    def last_for_name(self, name: str) -> dict[str, Any] | None:
        rows = self.sessions_for_name(name)
        return rows[-1] if rows else None

    def one_rm(self, key: str) -> float:
        stored = float((self.data.get("one_rms") or {}).get(key) or 0)
        if stored:
            return stored
        return self.logged_best(key)

    def pb_current(self, name: str) -> float:
        stored = float((self.data.get("one_rms") or {}).get(name) or 0)
        if stored:
            return stored
        return self.logged_best(name)

    def logged_best(self, name: str) -> float:
        spec = pb_spec(name) or {"metric": "weight"}
        metric = spec["metric"]
        rows = self.sessions_for_name(name)
        best = 0.0
        paces: list[float] = []
        for row in rows:
            if row.get("name") in SPEED_NAMES:
                continue
            if name in ("Chin-Ups (Max reps)", "Pull-Ups (reps)") and row.get("max_reps"):
                best = max(best, float(row["max_reps"]))
            if metric == "weight":
                for w, r in row_weight_reps(row):
                    if w and r <= 1:
                        best = max(best, w)
                    elif w and r > 1:
                        best = max(best, epley_1rm(w, r))
                    elif w:
                        best = max(best, w)
            elif metric == "reps":
                if row.get("kind") == "power_wave":
                    best = max(best, float(row.get("max_reps") or 0))
                else:
                    best = max(best, float(row.get("reps") or 0), float(row.get("max_reps") or 0))
            elif metric == "seconds":
                best = max(best, float(row.get("seconds") or 0))
            elif metric == "distance":
                best = max(best, float(row.get("distance") or 0))
            elif metric == "pace" and row.get("pace"):
                paces.append(float(row["pace"]))
        if metric == "pace":
            return min(paces) if paces else 0.0
        return best

    def pb_history(self, name: str) -> list[tuple[datetime, float]]:
        spec = pb_spec(name) or {"metric": "weight"}
        metric = spec["metric"]
        points: list[tuple[datetime, float]] = []
        for row in self.sessions_for_name(name):
            dt = row.get("dt")
            if not dt:
                try:
                    dt = datetime.fromisoformat(row["date"])
                except (KeyError, ValueError):
                    continue
            val = 0.0
            if name in ("Chin-Ups (Max reps)", "Pull-Ups (reps)") and row.get("max_reps") and not (
                row.get("kind") == "max_reps" and row.get("reps")
            ):
                val = float(row["max_reps"])
            elif metric == "weight":
                w, r = primary_wave_load(row) if (
                    row.get("kind") in ("power_wave", "strength") or row.get("wave_sets") or row.get("work_sets")
                ) else (
                    float(row.get("weight") or 0),
                    int(row.get("reps") or 1),
                )
                if w:
                    val = epley_1rm(w, r) if r > 1 else w
            elif metric == "reps":
                if row.get("kind") == "power_wave":
                    val = float(row.get("max_reps") or 0)
                else:
                    val = float(row.get("reps") or row.get("max_reps") or 0)
            elif metric == "seconds":
                val = float(row.get("seconds") or 0)
            elif metric == "distance":
                val = float(row.get("distance") or 0)
            elif metric == "pace":
                val = float(row.get("pace") or 0)
            if val:
                points.append((dt, val))
        return points

    def starred_chart_specs(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for ex in self.all_focus_exercises():
            by_key[chart_lift_key(ex)] = ex
            max_key = ex.get("max_pb_key")
            if ex.get("has_max") and max_key:
                by_key.setdefault(str(max_key), ex)

        specs: list[dict[str, Any]] = []
        for pb in PB_LIFTS:
            key = pb["name"]
            ex = by_key.get(key)
            kind = "strength"
            if ex:
                if ex.get("max_pb_key") == key and chart_lift_key(ex) != key:
                    kind = "max_reps"
                else:
                    kind = str(ex.get("kind") or "strength")
            specs.append(
                {
                    "key": key,
                    "title": key,
                    "kind": kind,
                    "ex": ex or {"name": key, "kind": kind},
                    "metric": pb["metric"],
                    "unit": pb["unit"],
                }
            )
        return specs

    def strength_chart_series(
        self, spec: dict[str, Any]
    ) -> list[tuple[str, str, list[tuple[datetime, float]]]]:
        key = spec["key"]
        kind = spec["kind"]
        if kind == "power_wave":
            estimated: list[tuple[datetime, float]] = []
            tested: list[tuple[datetime, float]] = []
            for row in self.sessions_for_name(key):
                if row.get("name") in SPEED_NAMES:
                    continue
                dt = row.get("dt")
                if not dt:
                    try:
                        dt = datetime.fromisoformat(row["date"])
                    except (KeyError, ValueError):
                        continue
                w, r = primary_wave_load(row)
                if not w:
                    continue
                wave = int(row.get("session_wave") or 0)
                if wave == 4:
                    singles = [sw for sw, sr in row_weight_reps(row) if sw and sr <= 1]
                    val = max(singles) if singles else (epley_1rm(w, r) if r > 1 else w)
                    tested.append((dt, val))
                else:
                    estimated.append((dt, epley_1rm(w, r) if r > 1 else w))
            series: list[tuple[str, str, list[tuple[datetime, float]]]] = []
            if estimated:
                series.append(("Estimated 1RM", GOLD, estimated))
            if tested:
                series.append(("Tested 1RM", BLUE, tested))
            return series
        if kind == "max_reps":
            pts = list(self.pb_history(key))
            parent = (spec.get("ex") or {}).get("name")
            if parent and parent != key:
                seen = {(d.isoformat(), v) for d, v in pts}
                for row in self.sessions_for_name(parent):
                    dt = row.get("dt")
                    if not dt:
                        try:
                            dt = datetime.fromisoformat(row["date"])
                        except (KeyError, ValueError):
                            continue
                    val = float(row.get("max_reps") or 0)
                    if val and (dt.isoformat(), val) not in seen:
                        pts.append((dt, val))
                        seen.add((dt.isoformat(), val))
            pts.sort(key=lambda p: p[0])
            return [(spec["title"], GOLD, pts)] if pts else []
        pts = self.pb_history(key)
        if not pts:
            return []
        return [(spec["title"], GOLD, pts)]

    def last_marathon(self) -> dict[str, Any] | None:
        return self.last_for_name("Marathon Builder")

    def target_for_exercise(self, ex: dict[str, Any]) -> dict[str, Any]:
        wave = int(self.data.get("wave", 1))
        unit = self.data.get("unit", "lb")
        kind = ex.get("kind")
        last = self.last_for_name(ex["name"])
        if kind == "run" and ex["name"] == "Marathon Builder":
            last_d = float(last["distance"]) if last and last.get("distance") else 0
            target_d = last_d + 1 if last_d else 0
            detail = f"{fmt_num(target_d)} mi  (last + 1)" if last_d else "First long run — go as far as you can"
            return {"label": detail, "weight": 0, "kind": "marathon"}
        if kind == "run" and ex["name"] == "Tempo Run":
            marathon = self.last_marathon()
            if marathon and marathon.get("pace"):
                return {
                    "label": f"Beat last Marathon Builder pace  {format_pace(float(marathon['pace']))} /mi",
                    "kind": "tempo",
                }
            return {"label": "No Marathon Builder pace yet — run a controlled tempo", "kind": "tempo"}
        if kind == "power_wave" or (ex.get("one_rm_key") and not ex.get("speed")):
            key = ex.get("one_rm_key") or ex["name"]
            rm = self.one_rm(key)
            if not rm:
                fallback = format_bits(last, unit) if last else "Set a current max on PB Goals"
                return {"label": f"Last time  {fallback}" if last else fallback, "kind": "power_wave"}
            pct = WAVE_LOAD_PCT.get(wave, 0.8)
            load = round_load(rm * pct)
            if wave == 4:
                goal = round_load(rm * WAVE_4_GOAL_PCT)
                return {
                    "label": f"Target  {fmt_num(load)} {unit} (1RM)   ·   Goal  {fmt_num(goal)} {unit} (105%)",
                    "weight": load,
                    "kind": "power_wave",
                }
            return {
                "label": f"Target  {fmt_num(load)} {unit}  ({int(pct * 100)}% of {fmt_num(rm)} 1RM)",
                "weight": load,
                "kind": "power_wave",
            }
        if ex.get("speed"):
            key = ex.get("one_rm_key")
            rm = self.one_rm(key) if key else 0
            if rm:
                load = round_load(rm * 0.5)
                return {
                    "label": f"Target  {fmt_num(load)} {unit}  (50% of {key} {fmt_num(rm)})",
                    "weight": load,
                    "kind": "speed",
                }
            if last:
                return {"label": f"Last time  {format_bits(last, unit)}", "kind": "speed"}
            return {"label": "No 1RM yet — use last time once logged", "kind": "speed"}
        if last:
            return {"label": f"Last time  {format_bits(last, unit)}", "kind": "repeat"}
        return {"label": "No previous log — establish a baseline", "kind": "repeat"}

    def reset_clock(self) -> None:
        self.data["wave"] = 1
        self.data["next_day"] = 1
        self.save()

    def best_for_exercise(self, ex: dict[str, Any]) -> dict[str, float]:
        rows = self.sessions_for_name(ex["name"])
        best_weight = best_e1rm = best_reps = best_seconds = best_distance = best_minutes = 0.0
        paces: list[float] = []
        for row in rows:
            mx = int(row.get("max_reps") or 0)
            pairs = row_weight_reps(row)
            if not pairs:
                pairs = [(0.0, 0)]
            for w, r in pairs:
                best_weight = max(best_weight, w)
                if w > 0 and r > 0:
                    best_e1rm = max(best_e1rm, epley_1rm(w, r))
                best_reps = max(best_reps, float(r), float(mx))
            best_seconds = max(best_seconds, float(row.get("seconds") or 0))
            best_distance = max(best_distance, float(row.get("distance") or 0))
            best_minutes = max(best_minutes, float(row.get("minutes") or 0))
            if row.get("pace"):
                paces.append(float(row["pace"]))
        best_pace = min(paces) if paces else 0.0
        metric, _unit, _hib = goal_spec(ex)
        primary = {
            "e1rm": best_e1rm,
            "weight": best_weight,
            "reps": best_reps,
            "seconds": best_seconds,
            "distance": best_distance,
            "minutes": best_minutes,
            "pace": best_pace,
        }.get(metric, best_e1rm)
        return {
            "weight": best_weight,
            "e1rm": best_e1rm,
            "reps": best_reps,
            "seconds": best_seconds,
            "distance": best_distance,
            "minutes": best_minutes,
            "pace": best_pace,
            "primary": primary,
        }

    def log_session(self, lifts: list[dict[str, Any]], notes: str) -> dict[str, Any]:
        clock = self.clock()
        day_meta = self.next_program_day()
        mesocycle_completed = clock["wave"] == 4 and clock["day"] == 9
        self.data["sessions"].append(
            {
                "id": str(uuid.uuid4()),
                "date": datetime.now().isoformat(timespec="seconds"),
                "cycle_day": clock["day"],
                "wave": clock["wave"],
                "program_day": clock["program_day"],
                "day_name": day_meta.get("name", f"Day {clock['day']}"),
                "mesocycle_completed": mesocycle_completed,
                "lifts": lifts,
                "notes": notes.strip(),
            }
        )
        if clock["day"] < 9:
            self.data["next_day"] = clock["day"] + 1
        else:
            self.data["next_day"] = 1
            if clock["wave"] < 4:
                self.data["wave"] = clock["wave"] + 1
            else:
                self.data["wave"] = 1
                self.data["block"] = int(self.data.get("block", 1)) + 1
        self.save()
        return {"mesocycle_completed": mesocycle_completed, **self.clock()}

    def undo_last(self) -> bool:
        if not self.data["sessions"]:
            return False
        last = self.data["sessions"].pop()
        self.data["next_day"] = int(last.get("cycle_day", 1))
        self.data["wave"] = max(1, min(4, int(last.get("wave", 1))))
        if last.get("mesocycle_completed"):
            self.data["block"] = max(1, int(self.data.get("block", 1)) - 1)
        self.save()
        return True

    def log_measurements(self, values: dict[str, float], notes: str) -> None:
        clock = self.clock()
        self.data["measurements"].append(
            {
                "id": str(uuid.uuid4()),
                "date": datetime.now().isoformat(timespec="seconds"),
                "block": clock["block"],
                "wave": clock["wave"],
                "program_day": clock["program_day"],
                **{k: values[k] for k, _l, _u in MEASUREMENT_FIELDS if k in values},
                "notes": notes.strip(),
            }
        )
        self.save()

    def latest_measurements(self) -> dict[str, Any] | None:
        rows = self.data.get("measurements") or []
        return rows[-1] if rows else None


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def txt(value: str, size: int = 14, color: str = TEXT, weight=None, **kw: Any) -> ft.Text:
    return ft.Text(value, size=size, color=color, weight=weight or ft.FontWeight.NORMAL, **kw)


def muted(value: str, size: int = 12) -> ft.Text:
    return txt(value, size=size, color=MUTED)


def gold_btn(label: str, on_click: Callable, **kw: Any) -> ft.FilledButton:
    return ft.FilledButton(
        label,
        on_click=on_click,
        bgcolor=GOLD,
        color=BG,
        **kw,
    )


def ghost_btn(label: str, on_click: Callable) -> ft.OutlinedButton:
    return ft.OutlinedButton(label, on_click=on_click, style=ft.ButtonStyle(color=TEXT))


def panel(content: ft.Control, **kw: Any) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=16,
        padding=20,
        **kw,
    )


def field(label: str, value: str = "", width: int = 140, hint: str = "") -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        width=width,
        hint_text=hint,
        color=TEXT,
        border_color=BORDER,
        focused_border_color=GOLD,
        bgcolor=SURFACE2,
        label_style=ft.TextStyle(color=MUTED, size=12),
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class Achilles:
    def __init__(self, page: ft.Page, store: Store) -> None:
        self.page = page
        self.store = store
        self.nav = 0
        self._log_rows: list[dict[str, Any]] = []
        self._goal_fields: dict[str, ft.TextField] = {}
        self._max_fields: dict[str, ft.TextField] = {}
        self._measure_fields: dict[str, ft.TextField] = {}
        self._notes: ft.TextField | None = None
        self._measure_notes: ft.TextField | None = None
        self._wave_dd: ft.Dropdown | None = None
        self._day_dd: ft.Dropdown | None = None
        self.headline = txt("", size=15, color=GOLD, weight=ft.FontWeight.W_600)
        self.body = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=16)
        self.rail = ft.NavigationRail(
            selected_index=0,
            extended=True,
            min_extended_width=188,
            bgcolor=SIDEBAR,
            indicator_color=SURFACE2,
            selected_label_text_style=ft.TextStyle(color=GOLD, weight=ft.FontWeight.W_600),
            unselected_label_text_style=ft.TextStyle(color=MUTED),
            on_change=self._on_nav,
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.DASHBOARD_OUTLINED, selected_icon=ft.Icons.DASHBOARD, label="Dashboard"),
                ft.NavigationRailDestination(icon=ft.Icons.FITNESS_CENTER_OUTLINED, selected_icon=ft.Icons.FITNESS_CENTER, label="Log workout"),
                ft.NavigationRailDestination(icon=ft.Icons.BAR_CHART_OUTLINED, selected_icon=ft.Icons.BAR_CHART, label="Strength"),
                ft.NavigationRailDestination(icon=ft.Icons.FLAG_OUTLINED, selected_icon=ft.Icons.FLAG, label="PB goals"),
                ft.NavigationRailDestination(icon=ft.Icons.CALENDAR_VIEW_WEEK_OUTLINED, selected_icon=ft.Icons.CALENDAR_VIEW_WEEK, label="Program"),
                ft.NavigationRailDestination(icon=ft.Icons.HISTORY, selected_icon=ft.Icons.HISTORY, label="History"),
                ft.NavigationRailDestination(icon=ft.Icons.MONITOR_WEIGHT_OUTLINED, selected_icon=ft.Icons.MONITOR_WEIGHT, label="Measurements"),
            ],
        )

    def mount(self) -> None:
        self.rail.expand = True
        shell = ft.Row(
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Container(
                    width=200,
                    bgcolor=SIDEBAR,
                    content=ft.Column(
                        expand=True,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                expand=True,
                                spacing=0,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.only(left=20, top=28, right=12, bottom=8),
                                        content=ft.Column(
                                            spacing=2,
                                            controls=[
                                                txt("ACHILLES", size=20, color=GOLD, weight=ft.FontWeight.BOLD),
                                                muted("4-wave training cycle"),
                                            ],
                                        ),
                                    ),
                                    self.rail,
                                ],
                            ),
                            ft.Container(
                                padding=ft.Padding.only(left=12, right=12, bottom=18, top=8),
                                content=ft.TextButton(
                                    content="Reset wave / day",
                                    style=ft.ButtonStyle(color=CRIMSON),
                                    on_click=self._reset_clock,
                                ),
                            ),
                        ],
                    ),
                ),
                ft.VerticalDivider(width=1, color=BORDER),
                ft.Container(
                    expand=True,
                    bgcolor=BG,
                    padding=24,
                    content=ft.Column(
                        expand=True,
                        spacing=16,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    self.headline,
                                    txt(datetime.now().strftime("%A, %b %d"), size=13, color=MUTED),
                                ],
                            ),
                            self.body,
                        ],
                    ),
                ),
            ],
        )
        self.page.add(shell)
        self.refresh()

    def snack(self, message: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(message), bgcolor=SURFACE2))

    def confirm(self, title: str, message: str, on_yes: Callable[[], None], yes_label: str = "OK") -> None:
        def yes(_e: Any) -> None:
            self.page.pop_dialog()
            on_yes()

        self.page.show_dialog(
            ft.AlertDialog(
                title=txt(title, size=18, weight=ft.FontWeight.W_600),
                content=txt(message, size=14, color=MUTED),
                bgcolor=SURFACE,
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: self.page.pop_dialog()),
                    gold_btn(yes_label, yes),
                ],
            )
        )

    def _on_nav(self, e: Any) -> None:
        idx = e.control.selected_index
        if idx is None:
            return
        self.nav = idx
        self.refresh()

    def go(self, index: int) -> None:
        self.nav = index
        self.rail.selected_index = index
        self.refresh()

    def refresh(self) -> None:
        clock = self.store.clock()
        extra = "  ·  1RM test wave" if clock["is_1rm_wave"] else ""
        self.headline.value = clock["headline"] + extra
        builders = [
            self._dashboard,
            self._log,
            self._strength,
            self._goals,
            self._program,
            self._history,
            self._measurements,
        ]
        self.body.controls = builders[self.nav]()
        self.page.update()

    # ----- Dashboard -----
    def _dashboard(self) -> list[ft.Control]:
        clock = self.store.clock()
        nxt = self.store.next_program_day()
        wave = clock["wave"]
        pct = int(WAVE_LOAD_PCT.get(wave, 0.8) * 100)
        lines: list[ft.Control] = [
            muted("TODAY"),
            txt(f"Day {nxt['day']} of 9  —  {nxt['name']}", size=22, weight=ft.FontWeight.BOLD),
            muted(
                f"Wave {wave} power-wave loads are {pct}% of 1RM"
                if wave < 4
                else "Wave 4: hit the 1RM. Stretch goal is 105%."
            ),
        ]
        if clock["is_1rm_wave"]:
            lines.append(txt("Wave 4 is a 1-rep max test wave.", size=13, color=GOLD))
        lines.append(ft.Row(controls=[gold_btn("Log this workout", lambda _e: self.go(NAV["log"]))]))

        workout_rows: list[ft.Control] = []
        for block, exercises in grouped_exercises(nxt):
            workout_rows.append(muted(BLOCK_TITLES.get(block, block)))
            for ex in exercises:
                target = self.store.target_for_exercise(ex)
                star = is_highlighted(ex)
                workout_rows.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=8),
                        content=ft.Column(
                            spacing=2,
                            controls=[
                                txt(
                                    ("★ " if star else "") + ex["name"],
                                    size=15,
                                    color=GOLD if star else TEXT,
                                    weight=ft.FontWeight.W_600,
                                ),
                                muted(ex.get("scheme", "")),
                                txt(target["label"], size=13, color=GREEN if star else TEXT),
                            ],
                        ),
                    )
                )

        wave_chips = ft.Row(spacing=8, controls=[self._wave_chip(i, clock["wave"]) for i in range(1, 5)])
        day_chips = ft.Row(
            spacing=6,
            wrap=True,
            controls=[self._day_chip(day, clock["day"]) for day in self.store.data["program"]],
        )
        return [
            panel(ft.Column(lines, spacing=6)),
            muted("POWER WAVE CLOCK"),
            panel(
                ft.Column(
                    [
                        wave_chips,
                        muted(f"Block {clock['block']}  ·  {clock['days_left']} days left in this 4-wave cycle"),
                        day_chips,
                    ],
                    spacing=12,
                )
            ),
            muted("TODAY'S WORKOUT  ·  TARGETS"),
            panel(ft.Column(workout_rows, spacing=4)),
        ]

    def _wave_chip(self, wave: int, current: int) -> ft.Container:
        active = wave == current
        label = f"Wave {wave}" + (" · 1RM" if wave == 4 else "")
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=12,
            bgcolor=GOLD if active else SURFACE2,
            content=txt(label if not active else f"{label}  ·  NOW", size=12, color=BG if active else MUTED, weight=ft.FontWeight.W_600),
        )

    def _day_chip(self, day: dict[str, Any], current: int) -> ft.Container:
        active = day["day"] == current
        return ft.Container(
            width=84,
            padding=10,
            border_radius=12,
            bgcolor=GOLD if active else SURFACE2,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
                controls=[
                    txt(str(day["day"]), size=14, color=BG if active else TEXT, weight=ft.FontWeight.BOLD),
                    txt("NEXT" if active else day.get("short", "")[:9], size=10, color=BG if active else MUTED),
                ],
            ),
        )

    def _focus_card(self, ex: dict[str, Any]) -> ft.Container:
        stats = self.store.best_for_exercise(ex)
        metric, unit, higher = goal_spec(ex)
        goal = float(self.store.data["goals"].get(ex["name"]) or 0)
        primary = stats["primary"]
        pct = 0.0
        if goal > 0 and primary > 0:
            pct = min(1.0, (primary / goal) if higher else (goal / primary))
        extra = ""
        if ex.get("kind") == "run" and ex.get("focus_metric") == "pace" and stats["distance"]:
            extra = f"Longest  {fmt_num(stats['distance'])} mi"
        elif ex.get("kind") == "run" and stats["pace"]:
            extra = f"Best pace  {format_pace(stats['pace'])} /mi"
        elif stats["weight"]:
            extra = f"Heaviest  {fmt_num(stats['weight'])} {self.store.data.get('unit', 'lb')}"
        return ft.Container(
            col={"xs": 12, "md": 6, "lg": 4},
            content=panel(
                ft.Column(
                    [
                        txt(ex["name"], size=15, weight=ft.FontWeight.W_600),
                        txt(
                            metric_text(metric, primary, unit) if primary else "No sessions yet",
                            size=18,
                            color=GOLD if primary else MUTED,
                            weight=ft.FontWeight.BOLD,
                        ),
                        muted(extra or " "),
                        ft.ProgressBar(value=pct, color=GREEN if pct >= 1 else GOLD, bgcolor=SURFACE2, bar_height=8, border_radius=8),
                        muted(f"Goal  {metric_text(metric, goal, unit)}" if goal else "No PB goal set"),
                    ],
                    spacing=6,
                )
            ),
        )

    # ----- Log -----
    def _log(self) -> list[ft.Control]:
        nxt = self.store.next_program_day()
        clock = self.store.clock()
        self._log_rows = []
        blocks: list[ft.Control] = [
            txt("Log workout", size=22, weight=ft.FontWeight.BOLD),
            muted(f"{clock['headline']}  ·  {nxt['name']}"),
            muted("Fill in what you did. Focus lines matter most; accessories can be left blank."),
        ]
        for block, exercises in grouped_exercises(nxt):
            blocks.append(muted(BLOCK_TITLES.get(block, block)))
            rows = [self._log_row(ex) for ex in exercises]
            blocks.append(panel(ft.Column(rows, spacing=14)))
        self._notes = ft.TextField(
            label="Session notes",
            multiline=True,
            min_lines=3,
            max_lines=5,
            color=TEXT,
            border_color=BORDER,
            focused_border_color=GOLD,
            bgcolor=SURFACE,
        )
        blocks.extend(
            [
                self._notes,
                ft.Row(
                    controls=[
                        gold_btn("Save workout & advance cycle", self._save_workout),
                        ghost_btn("Skip this day", self._skip_day),
                    ]
                ),
            ]
        )
        return blocks

    def _log_row(self, ex: dict[str, Any]) -> ft.Column:
        last = self.store.last_for_name(ex["name"])
        kind = ex.get("kind")
        widgets: dict[str, ft.Control] = {}

        def add(label: str, key: str, prefill: str = "", width: int = 130, hint: str = "") -> None:
            widgets[key] = field(label, prefill, width, hint)

        if kind == "run":
            dist = str(ex["fixed_distance"]) if ex.get("fixed_distance") else (fmt_num(float(last["distance"])) if last and last.get("distance") else "")
            pace = format_pace(float(last["pace"])) if last and last.get("pace") else ""
            add("Distance (mi)", "distance", "" if dist == "—" else dist)
            add("Pace (min/mi)", "pace", "" if pace == "—" else pace, hint="7:45")
        elif kind == "bike":
            add("Minutes", "minutes", fmt_num(float(last["minutes"])) if last and last.get("minutes") else "")
            add("Distance (mi)", "distance", fmt_num(float(last["distance"])) if last and last.get("distance") else "")
        elif kind == "cardio_choice":
            widgets["mode"] = ft.Dropdown(
                label="Mode",
                width=160,
                value=(last.get("mode") if last and last.get("mode") else "Bike"),
                options=[ft.DropdownOption(key="Bike", text="Bike"), ft.DropdownOption(key="Light run", text="Light run")],
            )
            add("Minutes", "minutes", fmt_num(float(last["minutes"])) if last and last.get("minutes") else "")
            add("Distance (mi)", "distance", fmt_num(float(last["distance"])) if last and last.get("distance") else "")
        elif kind == "timed":
            pre = format_seconds(float(last["seconds"])) if last and last.get("seconds") else ""
            add("Time (sec or m:ss)", "seconds", "" if pre == "—" else pre, width=160)
        elif kind == "max_reps":
            add("Max reps", "reps", str(int(last["reps"])) if last and last.get("reps") else "")
            add("Weight (optional)", "weight", fmt_num(float(last["weight"])) if last and last.get("weight") else "")
        elif kind == "reps":
            add("Sets", "sets", str(int(last["sets"])) if last and last.get("sets") else "", width=90)
            add("Reps", "reps", str(int(last["reps"])) if last and last.get("reps") else "", width=90)
        elif kind == "power_wave":
            meta = power_wave_meta(ex)
            last_cd = last.get("cooldown") if last and isinstance(last.get("cooldown"), dict) else {}
            for i in range(meta["count"]):
                prev = last_set_prefill(last, i)
                pre_w = fmt_num(float(prev["weight"])) if prev and prev.get("weight") else ""
                pre_r = str(int(prev["reps"])) if prev and prev.get("reps") else ""
                add(f"Wave {i + 1} weight", f"pw_w_{i}", "" if pre_w == "—" else pre_w)
                add(f"Wave {i + 1} reps", f"pw_r_{i}", pre_r, width=110)
            if meta["cooldown"]:
                cd_w = fmt_num(float(last_cd["weight"])) if last_cd.get("weight") else ""
                cd_r = str(int(last_cd["reps"])) if last_cd.get("reps") else ""
                add("Cool-down weight", "cd_w", "" if cd_w == "—" else cd_w)
                add("Cool-down reps", "cd_r", cd_r, width=130)
            if ex.get("has_max"):
                add("Max-set reps", "max_reps", str(int(last["max_reps"])) if last and last.get("max_reps") else "")
        elif kind == "strength":
            count = scheme_work_count(ex, last)
            for i in range(count):
                prev = last_set_prefill(last, i)
                pre_w = fmt_num(float(prev["weight"])) if prev and prev.get("weight") else ""
                pre_r = str(int(prev["reps"])) if prev and prev.get("reps") else ""
                add(f"Set {i + 1} weight", f"sw_w_{i}", "" if pre_w == "—" else pre_w)
                add(f"Set {i + 1} reps", f"sw_r_{i}", pre_r, width=110)
        else:
            add("Weight", "weight", fmt_num(float(last["weight"])) if last and last.get("weight") else "")
            add("Sets", "sets", str(int(last["sets"])) if last and last.get("sets") else "", width=90)
            add("Reps", "reps", str(int(last["reps"])) if last and last.get("reps") else "", width=90)

        self._log_rows.append({"ex": ex, "widgets": widgets})
        title = ("★ " if is_highlighted(ex) else "") + ex["name"]
        target = self.store.target_for_exercise(ex)
        if target.get("weight") and kind in ("power_wave", "strength"):
            prefix = "pw_w_" if kind == "power_wave" else "sw_w_"
            count = power_wave_meta(ex)["count"] if kind == "power_wave" else scheme_work_count(ex, last)
            if kind == "power_wave" or ex.get("speed"):
                for i in range(count):
                    wfield = widgets.get(f"{prefix}{i}")
                    if wfield is not None:
                        wfield.value = fmt_num(float(target["weight"]))
        inputs: list[ft.Control]
        if kind == "power_wave":
            meta = power_wave_meta(ex)
            inputs = []
            for i in range(meta["count"]):
                inputs.append(ft.Row(spacing=10, wrap=True, controls=[widgets[f"pw_w_{i}"], widgets[f"pw_r_{i}"]]))
            extra: list[ft.Control] = []
            if meta["cooldown"]:
                extra.extend([widgets["cd_w"], widgets["cd_r"]])
            if ex.get("has_max"):
                extra.append(widgets["max_reps"])
            if extra:
                inputs.append(ft.Row(spacing=10, wrap=True, controls=extra))
        elif kind == "strength":
            count = scheme_work_count(ex, last)
            inputs = [
                ft.Row(spacing=10, wrap=True, controls=[widgets[f"sw_w_{i}"], widgets[f"sw_r_{i}"]])
                for i in range(count)
            ]
        else:
            inputs = [ft.Row(wrap=True, spacing=10, controls=list(widgets.values()))]
        return ft.Column(
            spacing=6,
            controls=[
                txt(title, size=15, color=GOLD if is_highlighted(ex) else TEXT, weight=ft.FontWeight.W_600),
                muted(ex.get("scheme", "")),
                txt(target["label"], size=12, color=GREEN),
                *inputs,
            ],
        )

    def _read_entry(self, row: dict[str, Any]) -> dict[str, Any] | None:
        ex, widgets = row["ex"], row["widgets"]
        kind = ex.get("kind")

        def val(key: str) -> str:
            w = widgets.get(key)
            if w is None:
                return ""
            return (w.value or "").strip()

        payload: dict[str, Any] = {"name": ex["name"], "kind": kind, "focus": bool(ex.get("focus"))}
        if kind == "run":
            distance, pace = parse_float(val("distance")), parse_pace(val("pace"))
            if distance is None and pace is None:
                return None
            if distance is not None:
                payload["distance"] = distance
            if pace is not None:
                payload["pace"] = pace
            return payload
        if kind == "bike":
            minutes, distance = parse_float(val("minutes")), parse_float(val("distance"))
            if minutes is None and distance is None:
                return None
            if minutes is not None:
                payload["minutes"] = minutes
            if distance is not None:
                payload["distance"] = distance
            return payload
        if kind == "cardio_choice":
            minutes, distance = parse_float(val("minutes")), parse_float(val("distance"))
            if minutes is None and distance is None:
                return None
            payload["mode"] = val("mode") or "Bike"
            if minutes is not None:
                payload["minutes"] = minutes
            if distance is not None:
                payload["distance"] = distance
            return payload
        if kind == "timed":
            seconds = parse_duration_seconds(val("seconds"))
            if seconds is None:
                return None
            payload["seconds"] = seconds
            return payload
        if kind == "max_reps":
            reps, weight = parse_int(val("reps")), parse_float(val("weight"))
            if reps is None:
                return None
            payload["reps"] = reps
            if weight is not None:
                payload["weight"] = weight
            return payload
        if kind == "reps":
            sets, reps = parse_int(val("sets")), parse_int(val("reps"))
            if sets is None and reps is None:
                return None
            if sets is not None:
                payload["sets"] = sets
            if reps is not None:
                payload["reps"] = reps
            return payload
        if kind == "power_wave":
            meta = power_wave_meta(ex)
            wave_sets: list[dict[str, Any]] = []
            for i in range(meta["count"]):
                w, r = parse_float(val(f"pw_w_{i}")), parse_int(val(f"pw_r_{i}"))
                if w is None and r is None:
                    continue
                item: dict[str, Any] = {"n": i + 1}
                if w is not None:
                    item["weight"] = w
                if r is not None:
                    item["reps"] = r
                wave_sets.append(item)
            cooldown: dict[str, Any] = {}
            if meta["cooldown"]:
                cw, cr = parse_float(val("cd_w")), parse_int(val("cd_r"))
                if cw is not None:
                    cooldown["weight"] = cw
                if cr is not None:
                    cooldown["reps"] = cr
            max_reps = parse_int(val("max_reps")) if "max_reps" in widgets else None
            if not wave_sets and not cooldown and not max_reps:
                return None
            payload["wave_sets"] = wave_sets
            if cooldown:
                payload["cooldown"] = cooldown
            if max_reps is not None:
                payload["max_reps"] = max_reps
            pw, pr = primary_wave_load(payload)
            if pw:
                payload["weight"] = pw
            if pr:
                payload["reps"] = pr
            return payload
        if kind == "strength":
            count = scheme_work_count(ex)
            work_sets: list[dict[str, Any]] = []
            for i in range(count):
                w, r = parse_float(val(f"sw_w_{i}")), parse_int(val(f"sw_r_{i}"))
                if w is None and r is None:
                    continue
                item = {"n": i + 1}
                if w is not None:
                    item["weight"] = w
                if r is not None:
                    item["reps"] = r
                work_sets.append(item)
            if not work_sets:
                return None
            payload["work_sets"] = work_sets
            payload["sets"] = len(work_sets)
            pw, pr = primary_wave_load(payload)
            if pw:
                payload["weight"] = pw
            if pr:
                payload["reps"] = pr
            return payload
        weight, reps = parse_float(val("weight")), parse_int(val("reps"))
        sets = parse_int(val("sets")) if "sets" in widgets else None
        max_reps = parse_int(val("max_reps")) if "max_reps" in widgets else None
        if weight is None and reps is None and not max_reps:
            return None
        if weight is not None:
            payload["weight"] = weight
        if reps is not None:
            payload["reps"] = reps
        if sets is not None:
            payload["sets"] = sets
        if max_reps is not None:
            payload["max_reps"] = max_reps
        return payload

    def _entry_primary(self, ex: dict[str, Any], entry: dict[str, Any]) -> float:
        metric, _u, _h = goal_spec(ex)
        if metric == "e1rm":
            if entry.get("kind") in ("power_wave", "strength") or entry.get("wave_sets") or entry.get("work_sets"):
                w, r = primary_wave_load(entry)
            else:
                w, r = float(entry.get("weight") or 0), int(entry.get("reps") or 0)
            return epley_1rm(w, r) if w and r else 0
        return float(entry.get(metric) or entry.get("reps") or entry.get("max_reps") or 0)

    def _save_workout(self, _e: Any = None) -> None:
        nxt = self.store.next_program_day()
        lifts: list[dict[str, Any]] = []
        missing: list[str] = []
        for row in self._log_rows:
            parsed = self._read_entry(row)
            if parsed:
                lifts.append(parsed)
            elif is_highlighted(row["ex"]):
                missing.append(row["ex"]["name"])
        if not lifts:
            self.snack("Enter at least one exercise, or skip the day.")
            return

        def commit() -> None:
            prs = []
            for entry in lifts:
                if not entry.get("focus"):
                    continue
                ex = next((e for e in nxt.get("exercises", []) if e["name"] == entry["name"]), None)
                if not ex:
                    continue
                before = self.store.best_for_exercise(ex)
                after = self._entry_primary(ex, entry)
                metric, _u, higher = goal_spec(ex)
                if after and (
                    (higher and after > before["primary"] + 0.05)
                    or (not higher and before["primary"] and after < before["primary"] - 0.01)
                    or (not higher and not before["primary"])
                ):
                    prs.append(entry["name"])
            notes = self._notes.value if self._notes else ""
            result = self.store.log_session(lifts, notes or "")
            msg = f"Logged {nxt['name']}. Next: {result['headline']}"
            if prs:
                msg += f"  ·  New best: {', '.join(prs)}"
            self.snack(msg)
            if result.get("mesocycle_completed"):
                self.confirm(
                    "4-wave cycle complete",
                    "That's about 5 weeks. Log body weight, body fat, muscle mass, and measurements?",
                    lambda: self.go(NAV["measurements"]),
                    "Log measurements",
                )
            else:
                self.go(NAV["dashboard"])

        if missing:
            self.confirm("Focus work blank", f"No numbers for: {', '.join(missing)}. Save the rest and advance?", commit, "Save anyway")
            return
        commit()

    def _skip_day(self, _e: Any = None) -> None:
        nxt = self.store.next_program_day()
        self.confirm(
            "Skip day",
            f"Skip Day {nxt['day']} ({nxt['name']}) and advance the cycle?",
            lambda: (self.store.log_session([], "Skipped"), self.go(NAV["dashboard"])),
            "Skip",
        )

    # ----- Strength -----
    def _strength(self) -> list[ft.Control]:
        unit = self.store.data.get("unit", "lb")
        total = sum(self.store.one_rm(name) for name in TOTAL_LIFTS)
        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                txt("Strength", size=22, weight=ft.FontWeight.BOLD),
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    spacing=2,
                    controls=[
                        muted("Bench + squat + trap-bar"),
                        txt(f"{fmt_num(total)} {unit}", size=28, color=GOLD, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ],
        )
        cards = []
        for spec in PB_LIFTS:
            now = self.store.pb_current(spec["name"])
            goal = float(self.store.data.get("goals", {}).get(spec["name"]) or 0)
            higher = spec["higher"]
            pct = 0.0
            if goal and now:
                pct = min(1.0, (now / goal) if higher else (goal / now))
            extra = ""
            if spec["metric"] == "weight" and spec["name"] in TOTAL_LIFTS:
                extra = f"1RM used for waves  {fmt_num(self.store.one_rm(spec['name']))} {unit}"
            cards.append(
                ft.Container(
                    col={"xs": 12, "md": 6, "lg": 4},
                    content=panel(
                        ft.Column(
                            [
                                txt(spec["name"], size=15, weight=ft.FontWeight.W_600),
                                txt(
                                    metric_text(spec["metric"], now, spec["unit"]) if now else "No mark yet",
                                    size=20,
                                    color=GOLD if now else MUTED,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                muted(extra or (f"Goal  {metric_text(spec['metric'], goal, spec['unit'])}" if goal else " ")),
                                ft.ProgressBar(value=pct, color=GREEN if pct >= 1 else GOLD, bgcolor=SURFACE2, bar_height=8, border_radius=8),
                            ],
                            spacing=6,
                        )
                    ),
                )
            )
        plots: list[ft.Control] = []
        for spec in self.store.starred_chart_specs():
            series = self.store.strength_chart_series(spec)
            unit = spec.get("unit") or ""
            if spec["kind"] == "power_wave":
                caption = "Gold = estimated 1RM from power waves  ·  Blue = tested 1RM on wave 4"
                if unit:
                    caption = f"{unit}  ·  {caption}"
            else:
                caption = unit or spec["metric"]
            plots.append(
                panel(
                    ft.Column(
                        [
                            txt(spec["title"], size=14, weight=ft.FontWeight.W_600),
                            muted(caption),
                            time_chart(series, 200, y_formatter=y_format_for_metric(spec["metric"])),
                        ],
                        spacing=6,
                    )
                )
            )
        return [
            header,
            muted("Current bests for the lifts on your PB list. Wave loads use these 1RMs."),
            ft.ResponsiveRow(controls=cards, spacing=12, run_spacing=12),
            muted("PB GOALS OVER TIME"),
            muted("One chart per PB Goals lift. Power-wave lifts split estimated 1RM (waves 1–3) from a tested 1RM on wave 4."),
            *plots,
        ]

    # ----- Goals -----
    def _goals(self) -> list[ft.Control]:
        self._goal_fields = {}
        self._max_fields = {}
        rows: list[ft.Control] = [
            ft.Row(
                controls=[
                    txt("Lift", size=11, color=MUTED, width=260),
                    txt("Current max", size=11, color=MUTED, width=130),
                    txt("Goal (lifetime)", size=11, color=MUTED, width=130),
                    txt("Unit", size=11, color=MUTED, width=70),
                ]
            )
        ]
        for spec in PB_LIFTS:
            name, metric, unit = spec["name"], spec["metric"], spec["unit"]
            now = self.store.pb_current(name)
            logged = self.store.logged_best(name)
            if spec.get("auto") == "plus_one_mile":
                last = self.store.last_marathon()
                last_d = float(last["distance"]) if last and last.get("distance") else 0
                nxt = f"{fmt_num(last_d + 1)} mi" if last_d else "First long run"
                rows.append(
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            txt(name, size=14, weight=ft.FontWeight.W_600, width=260),
                            txt(metric_text(metric, now, unit), size=13, width=130),
                            txt(nxt, size=13, color=GOLD, width=130),
                            muted(unit),
                        ],
                    )
                )
                continue

            def prefill(val: float, m: str = metric) -> str:
                if not val:
                    return ""
                if m == "pace":
                    text = format_pace(val)
                    return "" if text == "—" else text
                text = fmt_num(val)
                return "" if text == "—" else text

            stored_max = float((self.store.data.get("one_rms") or {}).get(name) or 0)
            goal_val = float(self.store.data.get("goals", {}).get(name) or 0)
            if not goal_val and name in SEED_GOALS and metric == "weight":
                goal_val = SEED_GOALS[name]
            max_entry = field("Current max", prefill(stored_max or logged), 120, "7:30" if metric == "pace" else "")
            goal_entry = field("Goal", prefill(goal_val), 120, "7:30" if metric == "pace" else "")
            self._max_fields[name] = max_entry
            self._goal_fields[name] = goal_entry
            rows.append(
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        txt(name, size=14, weight=ft.FontWeight.W_600, width=260),
                        max_entry,
                        goal_entry,
                        muted(unit),
                    ],
                )
            )
        return [
            txt("Personal best goals", size=22, weight=ft.FontWeight.BOLD),
            muted(
                "Current max is what you can hit now — wave loads use this. "
                "Goal is the lifetime mark you are chasing. Marathon Builder is always last distance + 1 mile."
            ),
            panel(ft.Column(rows, spacing=10)),
            gold_btn("Save goals", self._save_goals),
        ]

    def _save_goals(self, _e: Any = None) -> None:
        goals: dict[str, float] = dict(self.store.data.get("goals") or {})
        rms: dict[str, float] = dict(self.store.data.get("one_rms") or {})
        by_name = {spec["name"]: spec for spec in PB_LIFTS}

        def parse_field(name: str, entry: ft.TextField) -> float | None:
            raw = (entry.value or "").strip()
            spec = by_name[name]
            if not raw:
                return None
            val = parse_pace(raw) if spec["metric"] == "pace" else parse_float(raw)
            if val is None or val <= 0:
                self.snack(f"Enter a positive number for {name}, or leave it blank.")
                raise ValueError("invalid")
            return val

        try:
            for name, entry in self._goal_fields.items():
                val = parse_field(name, entry)
                if val is None:
                    goals.pop(name, None)
                else:
                    goals[name] = val
            for name, entry in self._max_fields.items():
                val = parse_field(name, entry)
                if val is None:
                    rms.pop(name, None)
                else:
                    rms[name] = val
        except ValueError:
            return
        self.store.data["goals"] = goals
        self.store.data["one_rms"] = rms
        self.store.save()
        self.snack("Current maxes and goals saved.")
        self.go(NAV["dashboard"])

    # ----- Program -----
    def _program(self) -> list[ft.Control]:
        clock = self.store.clock()
        self._wave_dd = ft.Dropdown(
            label="Wave",
            width=180,
            value=str(clock["wave"]),
            options=[
                ft.DropdownOption(key=str(i), text=f"Wave {i}" + (" (1RM test)" if i == 4 else ""))
                for i in range(1, 5)
            ],
        )
        self._day_dd = ft.Dropdown(
            label="Program day",
            width=220,
            value=str(clock["day"]),
            options=[
                ft.DropdownOption(key=str(d["day"]), text=f"Day {d['day']} — {d['name']}")
                for d in self.store.data["program"]
            ],
        )
        cards = []
        for day in self.store.data["program"]:
            lines: list[ft.Control] = [
                txt(
                    f"Day {day['day']}  —  {day['name']}" + ("  ·  NEXT" if day["day"] == clock["day"] else ""),
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=GOLD if day["day"] == clock["day"] else TEXT,
                ),
                muted(day.get("tag", "")),
            ]
            for block, exercises in grouped_exercises(day):
                lines.append(muted(BLOCK_TITLES.get(block, block), 11))
                for ex in exercises:
                    star = "★ " if is_highlighted(ex) else "    "
                    lines.append(
                        ft.Row(
                            controls=[
                                txt(f"{star}{ex['name']}", size=13, color=GOLD if is_highlighted(ex) else TEXT, width=260),
                                muted(ex.get("scheme", "")),
                            ]
                        )
                    )
            cards.append(panel(ft.Column(lines, spacing=4)))
        return [
            txt("9-day program", size=22, weight=ft.FontWeight.BOLD),
            muted("Four waves of this 9-day cycle. Wave 4 is a 1-rep max test. ★ marks the lifts and tests you care about."),
            ft.Row(
                controls=[
                    self._wave_dd,
                    self._day_dd,
                    gold_btn("Set clock", self._set_clock),
                    ghost_btn("Restore program", self._reset_program),
                ]
            ),
            *cards,
        ]

    def _set_clock(self, _e: Any = None) -> None:
        try:
            wave = int(self._wave_dd.value) if self._wave_dd and self._wave_dd.value else 1
            day = int(self._day_dd.value) if self._day_dd and self._day_dd.value else 1
        except (TypeError, ValueError):
            self.snack("Pick a wave and day.")
            return
        self.store.data["wave"] = max(1, min(4, wave))
        self.store.data["next_day"] = max(1, min(9, day))
        self.store.save()
        self.snack(self.store.clock()["headline"])
        self.go(NAV["dashboard"])

    def _reset_clock(self, _e: Any = None) -> None:
        self.confirm(
            "Reset wave and day",
            "Set the clock to Wave 1 - Day 1. Workouts, goals, and measurements stay. Use this when you want the next logged session to be Day 1.",
            lambda: (self.store.reset_clock(), self.go(NAV["dashboard"])),
            "Reset to Day 1",
        )

    def _reset_program(self, _e: Any = None) -> None:
        def restore() -> None:
            self.store.data["program"] = clone_program()
            self.store.save()
            self.refresh()

        self.confirm(
            "Restore program",
            "Reload the built-in 9-day layout? Sessions, waves, goals, and measurements are kept.",
            restore,
            "Restore",
        )

    # ----- History -----
    def _history(self) -> list[ft.Control]:
        unit = self.store.data.get("unit", "lb")
        sessions = list(reversed(self.store.data["sessions"]))
        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                txt("History", size=22, weight=ft.FontWeight.BOLD),
                ghost_btn("Undo last session", self._undo) if sessions else txt(""),
            ],
        )
        if not sessions:
            return [header, muted("No sessions yet. Log a workout to start the cycle.")]
        cards = []
        for session in sessions:
            try:
                dt = datetime.fromisoformat(session["date"]).strftime("%b %d, %Y  %I:%M %p")
            except ValueError:
                dt = session.get("date", "")
            wave = session.get("wave")
            pd = session.get("program_day")
            stamp = f"Wave {wave}  ·  Program Day {pd}  ·  {dt}" if wave else dt
            lifts = session.get("lifts") or []
            lines: list[ft.Control] = [
                txt(f"Day {session.get('cycle_day')}  —  {session.get('day_name', '')}", size=15, weight=ft.FontWeight.W_600),
                muted(stamp),
            ]
            if not lifts:
                lines.append(muted("Skipped"))
            for lift in lifts:
                lines.append(txt(format_logged(lift, unit), size=13))
            if session.get("notes"):
                lines.append(muted(session["notes"]))
            if session.get("mesocycle_completed"):
                lines.append(txt("Closed a 4-wave cycle", size=12, color=GOLD))
            cards.append(panel(ft.Column(lines, spacing=4)))
        return [header, *cards]

    def _undo(self, _e: Any = None) -> None:
        self.confirm(
            "Undo",
            "Remove the most recent session and roll the wave clock back?",
            lambda: (self.store.undo_last(), self.refresh()),
            "Undo",
        )

    # ----- Measurements -----
    def _measurements(self) -> list[ft.Control]:
        self._measure_fields = {}
        last = self.store.latest_measurements()
        fields_row: list[ft.Control] = []
        for key, label, unit in MEASUREMENT_FIELDS:
            pre = fmt_num(float(last[key])) if last and last.get(key) else ""
            if pre == "—":
                pre = ""
            box = field(f"{label} ({unit})", pre, 160)
            self._measure_fields[key] = box
            fields_row.append(box)
        self._measure_notes = ft.TextField(
            label="Notes",
            multiline=True,
            min_lines=2,
            color=TEXT,
            border_color=BORDER,
            focused_border_color=GOLD,
            bgcolor=SURFACE,
        )
        history: list[ft.Control] = []
        measure_series: list[tuple[str, str, list[tuple[datetime, float]]]] = []
        rows = self.store.data.get("measurements") or []
        for i, (key, label, _unit) in enumerate(MEASUREMENT_FIELDS):
            pts: list[tuple[datetime, float]] = []
            for row in rows:
                if not row.get(key):
                    continue
                try:
                    dt = datetime.fromisoformat(row["date"])
                except ValueError:
                    continue
                pts.append((dt, float(row[key])))
            if pts:
                measure_series.append((label, CHART_COLORS[i % len(CHART_COLORS)], pts))
        for row in reversed(rows):
            try:
                dt = datetime.fromisoformat(row["date"]).strftime("%b %d, %Y")
            except ValueError:
                dt = row.get("date", "")
            bits = "   ·   ".join(
                f"{label} {fmt_num(float(row.get(key) or 0))}{unit}"
                for key, label, unit in MEASUREMENT_FIELDS
                if row.get(key)
            )
            history.append(
                panel(
                    ft.Column(
                        [
                            txt(
                            f"{dt}  ·  Block {row.get('block', '—')}  ·  Wave {row.get('wave', '—')}",
                            size=14,
                            weight=ft.FontWeight.W_600,
                        ),
                            muted(bits or "No numbers"),
                            muted(row["notes"]) if row.get("notes") else txt(""),
                        ],
                        spacing=4,
                    )
                )
            )
        clock = self.store.clock()
        return [
            txt("Body measurements", size=22, weight=ft.FontWeight.BOLD),
            muted(
                "Update after a 4-wave cycle (~5 weeks). "
                f"Current clock: {clock['headline']}. {clock['days_left']} days until the next planned check-in."
            ),
            panel(ft.Column([ft.Row(wrap=True, spacing=12, run_spacing=12, controls=fields_row), self._measure_notes], spacing=16)),
            gold_btn("Save measurements", self._save_measurements),
            muted("OVER TIME"),
            *(
                [
                    panel(
                        ft.Column(
                            [muted(label), time_chart([(label, color, pts)], 200)],
                            spacing=6,
                        )
                    )
                    for label, color, pts in measure_series
                ]
                or [panel(time_chart([], 200))]
            ),
            muted("HISTORY") if history else muted("No measurement logs yet."),
            *history,
        ]

    def _save_measurements(self, _e: Any = None) -> None:
        values: dict[str, float] = {}
        for key, label, _unit in MEASUREMENT_FIELDS:
            raw = (self._measure_fields[key].value or "").strip()
            if not raw:
                continue
            val = parse_float(raw)
            if val is None or val <= 0:
                self.snack(f"Enter a positive number for {label}, or leave it blank.")
                return
            values[key] = val
        if not values:
            self.snack("Enter at least one measurement.")
            return
        notes = self._measure_notes.value if self._measure_notes else ""
        self.store.log_measurements(values, notes or "")
        self.snack("Measurements saved.")
        self.refresh()


def splash(clock: dict[str, Any]) -> ft.Container:
    return ft.Container(
        expand=True,
        bgcolor=BG,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
            controls=[
                txt("ACHILLES", size=42, color=GOLD, weight=ft.FontWeight.BOLD),
                muted("Power wave cycle"),
                txt(clock["headline"], size=22, color=TEXT, weight=ft.FontWeight.W_600),
                muted("Wave 4 is a 1-rep max test  ·  measurements after 4 waves"),
            ],
        ),
    )


async def main(page: ft.Page) -> None:
    page.title = "Achilles"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.theme = ft.Theme(color_scheme_seed=GOLD)
    page.window.width = 1280
    page.window.height = 820
    page.window.min_width = 980
    page.window.min_height = 680
    store = Store()
    page.add(splash(store.clock()))
    await asyncio.sleep(1.4)
    page.clean()
    Achilles(page, store).mount()


if __name__ == "__main__":
    ft.run(main)
