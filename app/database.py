"""SQLite 本地缓存 + JSON 文件凭证存储

- 缓存课表、成绩等数据，减少重复请求。
- credentials.json 保存记住的账号密码，用于免登录。
"""

import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from .config import DB_PATH


def _get_connection() -> sqlite3.Connection:
    """获取数据库连接（自动创建目录和表）"""
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    """初始化表结构"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cache (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS credentials (
            username   TEXT PRIMARY KEY,
            password   TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()


# ── 通用缓存 ──────────────────────────────────────────────

def cache_get(key: str) -> Optional[str]:
    """读取缓存，过期返回 None"""
    conn = _get_connection()
    row = conn.execute(
        "SELECT value, expires_at FROM cache WHERE key=?",
        (key,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    # 检查过期
    if row["expires_at"] and datetime.now() > datetime.fromisoformat(row["expires_at"]):
        return None
    return row["value"]


def cache_set(key: str, value: str, expire_hours: int = 0):
    """写入缓存，expire_hours=0 表示不过期"""
    expires = ""
    if expire_hours > 0:
        from datetime import timedelta
        expires = (datetime.now() + timedelta(hours=expire_hours)).isoformat()
    conn = _get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
        (key, value, expires)
    )
    conn.commit()
    conn.close()


# ── 课表缓存 ──────────────────────────────────────────────

DATA_DIR = Path("data")


def _safe_cache_name(value: str) -> str:
    value = str(value or "current").strip()
    value = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("_")
    return value or "current"


def _account_data_dir(account: str = "") -> Path:
    account_key = _safe_cache_name(account)
    if not account or account_key == "current":
        return DATA_DIR
    return DATA_DIR / "accounts" / account_key


def _cache_key(scope: str, key: str, account: str = "") -> str:
    account_key = _safe_cache_name(account)
    if account and account_key != "current":
        return f"{scope}:{account_key}:{key}"
    return f"{scope}:{key}"


def _read_json_file(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "data": data,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_updated_at(path: Path) -> str:
    payload = _read_json_file(path)
    if isinstance(payload, dict):
        return str(payload.get("updated_at") or "")
    return ""


def _semester_year_start(item: dict) -> int | None:
    name = str(item.get("name") or "")
    match = re.search(r"(20\d{2})\s*-\s*(20\d{2})", name)
    if match:
        return int(match.group(1))
    return None


def filter_recent_semesters(data: list[dict]) -> list[dict]:
    """Keep semesters from 2022-2023 onward; unknown labels are kept."""
    recent = []
    for item in data or []:
        year_start = _semester_year_start(item)
        if year_start is None or year_start >= 2022:
            recent.append(item)
    return recent


def _semester_id_is_recent(value: str) -> bool | None:
    text = str(value or "").strip()
    if text.isdigit():
        return int(text) >= 244
    return None


def _cache_key_is_recent(value: str) -> bool | None:
    text = str(value or "").strip()
    if text in ("", "all", "current"):
        return True
    if text.isdigit():
        return int(text) >= 244
    return None


def filter_recent_academic_records(data: list[dict], default_semester: str = "") -> list[dict]:
    """Drop cached schedule/grade records that clearly belong before 2022-2023."""
    recent = []
    for item in data or []:
        if not isinstance(item, dict):
            recent.append(item)
            continue

        year_start = None
        for key in ("semester_name", "semester", "term", "name"):
            year_start = _semester_year_start({"name": item.get(key)})
            if year_start is not None:
                break
        if year_start is not None:
            if year_start >= 2022:
                recent.append(item)
            continue

        id_recent = _semester_id_is_recent(item.get("semester"))
        if id_recent:
            recent.append(item)
            continue

        default_recent = _semester_id_is_recent(default_semester)
        if id_recent is None and default_recent:
            with_semester = dict(item)
            with_semester.setdefault("semester", str(default_semester))
            recent.append(with_semester)
    return recent


def save_schedule(semester: str, data: list[dict], account: str = ""):
    """缓存某一学期的课表"""
    key = _safe_cache_name(semester)
    if _cache_key_is_recent(key) is False:
        return
    cache_set(_cache_key("schedule", key, account), json.dumps(data, ensure_ascii=False), expire_hours=0)
    _write_json_file(_account_data_dir(account) / f"schedule_{key}.json", data)


def load_schedule(semester: str, account: str = "") -> Optional[list[dict]]:
    """读取缓存的课表"""
    key = _safe_cache_name(semester)
    if _cache_key_is_recent(key) is False:
        return None
    payload = _read_json_file(_account_data_dir(account) / f"schedule_{key}.json")
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raw = cache_get(_cache_key("schedule", key, account))
    return json.loads(raw) if raw else None


def load_schedule_updated_at(semester: str, account: str = "") -> str:
    key = _safe_cache_name(semester)
    return _read_updated_at(_account_data_dir(account) / f"schedule_{key}.json")


def save_today_schedule(data: list[dict], account: str = ""):
    """Cache today's schedule for one account."""
    cache_set(_cache_key("schedule", "today", account), json.dumps(data, ensure_ascii=False), expire_hours=0)
    _write_json_file(_account_data_dir(account) / "schedule_today.json", data)


def load_today_schedule(account: str = "") -> Optional[list[dict]]:
    """Load cached today's schedule for one account."""
    payload = _read_json_file(_account_data_dir(account) / "schedule_today.json")
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raw = cache_get(_cache_key("schedule", "today", account))
    return json.loads(raw) if raw else None


def load_today_schedule_updated_at(account: str = "") -> str:
    return _read_updated_at(_account_data_dir(account) / "schedule_today.json")


# ── 成绩缓存 ──────────────────────────────────────────────

def save_grades(data: list[dict], semester: str = "all", account: str = ""):
    """缓存成绩"""
    key = _safe_cache_name(semester or "all")
    if _cache_key_is_recent(key) is False:
        return
    data = filter_recent_academic_records(data, "" if key == "all" else key)
    cache_set(_cache_key("grades", key, account), json.dumps(data, ensure_ascii=False), expire_hours=0)
    _write_json_file(_account_data_dir(account) / f"grades_{key}.json", data)
    if key == "all":
        cache_set(_cache_key("grades", "legacy", account), json.dumps(data, ensure_ascii=False), expire_hours=0)
        _write_json_file(_account_data_dir(account) / "grades.json", data)


def load_grades(semester: str = "all", account: str = "") -> Optional[list[dict]]:
    """读取缓存的成绩"""
    key = _safe_cache_name(semester or "all")
    if _cache_key_is_recent(key) is False:
        return None
    payload = _read_json_file(_account_data_dir(account) / f"grades_{key}.json")
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return filter_recent_academic_records(payload["data"], "" if key == "all" else key)
    if key == "all":
        payload = _read_json_file(_account_data_dir(account) / "grades.json")
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return filter_recent_academic_records(payload["data"])
    raw = cache_get(_cache_key("grades", key, account)) or (
        cache_get(_cache_key("grades", "legacy", account)) if key == "all" else None
    )
    return filter_recent_academic_records(json.loads(raw), "" if key == "all" else key) if raw else None


def load_grades_updated_at(semester: str = "all", account: str = "") -> str:
    key = _safe_cache_name(semester or "all")
    updated = _read_updated_at(_account_data_dir(account) / f"grades_{key}.json")
    if not updated and key == "all":
        updated = _read_updated_at(_account_data_dir(account) / "grades.json")
    return updated


def save_exams(data: list[dict], account: str = "", semester: str = "current"):
    """Cache exam data for one account and semester."""
    key = _safe_cache_name(semester or "current")
    cache_set(_cache_key("exams", key, account), json.dumps(data, ensure_ascii=False), expire_hours=0)
    _write_json_file(_account_data_dir(account) / f"exams_{key}.json", data)
    if key == "current":
        _write_json_file(_account_data_dir(account) / "exams.json", data)


def load_exams(account: str = "", semester: str = "current") -> Optional[list[dict]]:
    """Load cached exam data for one account and semester."""
    key = _safe_cache_name(semester or "current")
    payload = _read_json_file(_account_data_dir(account) / f"exams_{key}.json")
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if key == "current":
        payload = _read_json_file(_account_data_dir(account) / "exams.json")
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
    raw = cache_get(_cache_key("exams", key, account))
    return json.loads(raw) if raw else None


def load_exams_updated_at(account: str = "", semester: str = "current") -> str:
    key = _safe_cache_name(semester or "current")
    updated = _read_updated_at(_account_data_dir(account) / f"exams_{key}.json")
    if not updated and key == "current":
        updated = _read_updated_at(_account_data_dir(account) / "exams.json")
    return updated


def save_plan_completion(data: dict, account: str = ""):
    """Cache plan-completion data for one account."""
    cache_set(_cache_key("plan_completion", "current", account), json.dumps(data, ensure_ascii=False), expire_hours=0)
    _write_json_file(_account_data_dir(account) / "plan_completion.json", data)


def load_plan_completion(account: str = "") -> Optional[dict]:
    """Load cached plan-completion data for one account."""
    payload = _read_json_file(_account_data_dir(account) / "plan_completion.json")
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    raw = cache_get(_cache_key("plan_completion", "current", account))
    return json.loads(raw) if raw else None


def load_plan_completion_updated_at(account: str = "") -> str:
    return _read_updated_at(_account_data_dir(account) / "plan_completion.json")


def save_second_credits(data: list[dict], account: str = "", semester: str = "current"):
    """Cache second-credit data for one account and semester."""
    key = _safe_cache_name(semester or "current")
    cache_set(_cache_key("second_credits", key, account), json.dumps(data, ensure_ascii=False), expire_hours=0)
    _write_json_file(_account_data_dir(account) / f"second_credits_{key}.json", data)
    if key == "current":
        _write_json_file(_account_data_dir(account) / "second_credits.json", data)


def load_second_credits(account: str = "", semester: str = "current") -> Optional[list[dict]]:
    """Load cached second-credit data for one account and semester."""
    key = _safe_cache_name(semester or "current")
    payload = _read_json_file(_account_data_dir(account) / f"second_credits_{key}.json")
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if key == "current":
        payload = _read_json_file(_account_data_dir(account) / "second_credits.json")
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
    raw = cache_get(_cache_key("second_credits", key, account))
    return json.loads(raw) if raw else None


def load_second_credits_updated_at(account: str = "", semester: str = "current") -> str:
    key = _safe_cache_name(semester or "current")
    updated = _read_updated_at(_account_data_dir(account) / f"second_credits_{key}.json")
    if not updated and key == "current":
        updated = _read_updated_at(_account_data_dir(account) / "second_credits.json")
    return updated


def save_semesters(data: list[dict], account: str = ""):
    """缓存学期列表"""
    data = filter_recent_semesters(data)
    cache_set(_cache_key("semesters", "list", account), json.dumps(data, ensure_ascii=False), expire_hours=0)
    _write_json_file(_account_data_dir(account) / "semesters.json", data)


def load_semesters(account: str = "") -> Optional[list[dict]]:
    """读取缓存的学期列表"""
    payload = _read_json_file(_account_data_dir(account) / "semesters.json")
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return filter_recent_semesters(payload["data"])
    raw = cache_get(_cache_key("semesters", "list", account))
    return filter_recent_semesters(json.loads(raw)) if raw else None


def load_semesters_updated_at(account: str = "") -> str:
    return _read_updated_at(_account_data_dir(account) / "semesters.json")


DEFAULT_SETTINGS = {
    "semester_start_date": "",
    "theme_mode": "light",
    "vpn_mode": "startup",
    "startup_view": "plan",
}


def save_settings(settings: dict, account: str = ""):
    """Save per-account UI settings."""
    data = dict(DEFAULT_SETTINGS)
    data.update(settings or {})
    _write_json_file(_account_data_dir(account) / "settings.json", data)


def load_settings(account: str = "") -> dict:
    """Load per-account UI settings."""
    payload = _read_json_file(_account_data_dir(account) / "settings.json")
    data = {}
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        data = payload["data"]
    result = dict(DEFAULT_SETTINGS)
    result.update(data)
    return result


def clear_account_cache(account: str = ""):
    """Clear cached academic data for one account, keeping credentials and settings."""
    account_dir = _account_data_dir(account)
    if account_dir.exists():
        for path in account_dir.glob("*.json"):
            if path.name in ("settings.json",):
                continue
            path.unlink(missing_ok=True)

    account_key = _safe_cache_name(account)
    prefixes = [
        _cache_key("schedule", "", account).rstrip(":"),
        _cache_key("grades", "", account).rstrip(":"),
        _cache_key("exams", "", account).rstrip(":"),
        _cache_key("plan_completion", "", account).rstrip(":"),
        _cache_key("second_credits", "", account).rstrip(":"),
        _cache_key("semesters", "", account).rstrip(":"),
    ]
    conn = _get_connection()
    for prefix in prefixes:
        conn.execute("DELETE FROM cache WHERE key=? OR key LIKE ?", (prefix, f"{prefix}:%"))
    if account and account_key != "current":
        legacy_prefixes = ("schedule:", "grades:", "exams:", "plan_completion:", "second_credits:", "semesters:")
        for prefix in legacy_prefixes:
            conn.execute("DELETE FROM cache WHERE key LIKE ?", (f"{prefix}{account_key}:%",))
    conn.commit()
    conn.close()


# ── 凭证存储（JSON 文件）─────────────────────────────────

CREDENTIALS_FILE = "data/credentials.json"


def save_credentials(username: str, cas_password: str, vpn_password: str = "", remember: bool = True):
    """保存记住的账号密码到 JSON 文件"""
    path = Path(CREDENTIALS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "username": username,
        "cas_password": cas_password,
        "vpn_password": vpn_password,
        "remember": remember,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_credentials() -> Optional[dict]:
    """读取保存的凭证，返回 {username, cas_password, vpn_password, remember} 或 None"""
    path = Path(CREDENTIALS_FILE)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_credentials():
    """删除凭证文件"""
    path = Path(CREDENTIALS_FILE)
    if path.exists():
        path.unlink()
