"""SUEP student information system Flet entry."""

import atexit
import hashlib
import re
import webbrowser
from datetime import date, datetime
from pathlib import Path

import flet as ft

from app.auth import AuthSession
from app.config import CAS_SERVICE_URL, PROXY_URL, VPN_SERVER
from app.database import (
    clear_credentials,
    clear_account_cache,
    filter_recent_semesters,
    load_credentials,
    load_exams,
    load_exams_updated_at,
    load_grades,
    load_grades_updated_at,
    load_plan_completion,
    load_plan_completion_updated_at,
    load_schedule,
    load_schedule_updated_at,
    load_semesters,
    load_semesters_updated_at,
    load_second_credits,
    load_second_credits_updated_at,
    load_today_schedule,
    load_today_schedule_updated_at,
    load_settings,
    save_credentials,
    save_exams,
    save_grades,
    save_plan_completion,
    save_schedule,
    save_semesters,
    save_second_credits,
    save_settings,
    save_today_schedule,
)
from app.vpn import VpnManager


COURSE_COLORS = [
    "#B9E4D6",
    "#C9DFF3",
    "#F5D6A8",
    "#F0B9B4",
    "#D7C6EE",
    "#BFE1C4",
    "#F4C7D8",
    "#C9E5EA",
    "#E6D4A7",
    "#C8D8B9",
    "#D8E8A8",
    "#B7D6F2",
    "#E7C8AE",
    "#BFD4C8",
    "#EAD0F2",
    "#F2C6C2",
    "#CADBB3",
    "#B6E0D8",
    "#E9D8B7",
    "#D4C7F0",
]

DARK_COURSE_COLORS = [
    "#21F5C7",
    "#42D9FF",
    "#FFE45E",
    "#FF5C8A",
    "#A77CFF",
    "#51FF7A",
    "#FF7AE6",
    "#2EE6A6",
    "#FFB84A",
    "#6DFFEA",
    "#D8FF4F",
    "#58A6FF",
    "#FF8D5A",
    "#8DFF9A",
    "#E56BFF",
    "#FF6B6B",
    "#B5FF5A",
    "#5CFFF1",
    "#FFD166",
    "#B388FF",
]

DAYS = ["\u5468\u4e00", "\u5468\u4e8c", "\u5468\u4e09", "\u5468\u56db", "\u5468\u4e94", "\u5468\u516d", "\u5468\u65e5"]
SECOND_CREDIT_QUALITY = "quality"
SECOND_CREDIT_REQUIRED = 4.0
SLOT_TIMES = [
    "8:20-9:05",
    "9:10-9:55",
    "10:10-10:55",
    "11:00-11:45",
    "11:50-12:30",
    "13:20-14:05",
    "14:10-14:55",
    "15:10-15:55",
    "16:00-16:45",
    "16:50-17:30",
    "18:15-19:00",
    "19:05-19:50",
    "19:55-20:35",
]
SLOTS = list(range(1, len(SLOT_TIMES) + 1))
MAX_SLOT = len(SLOTS)
CURRENT_SEMESTER = "current"
ALL_SEMESTERS = "all"

LIGHT_THEME = {
    "page": "#FFFFFF",
    "sidebar": "#EAF8F3",
    "sidebar_border": "#DDEAE6",
    "content": "#FFFFFF",
    "text": "#1F2D2A",
    "muted": "#7A8682",
    "muted2": "#8A9692",
    "active": "#DCEFEA",
    "active_border": "#CFE0DB",
    "button_bg": "#FFFFFF",
    "button_text": "#35534C",
    "card": "#FFFFFF",
    "soft": "#F7FAF9",
    "border": "#ECEFED",
    "grid_border": "#EEF2F0",
    "shadow": "#0808080A",
    "danger": "#C33B3B",
    "success": "#2F8F6B",
    "warning": "#B98600",
}

DARK_THEME = {
    "page": "#05070F",
    "sidebar": "#071118",
    "sidebar_border": "#143240",
    "content": "#05070F",
    "text": "#EAFDFF",
    "muted": "#8CB4C1",
    "muted2": "#6F93A0",
    "active": "#102A34",
    "active_border": "#18F2D2",
    "button_bg": "#0B1620",
    "button_text": "#C9FBFF",
    "card": "#09121B",
    "soft": "#0D1B25",
    "border": "#193544",
    "grid_border": "#132B38",
    "shadow": "#00F0FF16",
    "danger": "#FF4D6D",
    "success": "#39FFB6",
    "warning": "#FFE66D",
}


def stable_color_from_palette(key: str, palette: list[str]) -> str:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return palette[int(digest[:8], 16) % len(palette)]


def stable_color(key: str) -> str:
    return stable_color_from_palette(key, COURSE_COLORS)


def all_border(width: int, color: str):
    side = ft.BorderSide(width, color)
    return ft.Border(left=side, top=side, right=side, bottom=side)


def right_border(width: int, color: str):
    return ft.Border(right=ft.BorderSide(width, color))


def pad(left: int = 0, top: int = 0, right: int = 0, bottom: int = 0):
    return ft.Padding(left, top, right, bottom)


def pad_xy(horizontal: int = 0, vertical: int = 0):
    return ft.Padding(horizontal, vertical, horizontal, vertical)


def main(page: ft.Page):
    page.title = "SUEP Student System"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1320
    page.window.height = 860
    page.window.min_width = 1240
    page.window.min_height = 780
    page.window.resizable = True
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#FFFFFF"

    auth: AuthSession | None = None
    vpn: VpnManager | None = None
    current_view = "plan"
    plan_data: dict = {}
    schedule_items: list[dict] = []
    today_schedule_items: list[dict] = []
    grade_items: list[dict] = []
    exam_items: list[dict] = []
    second_credit_items: list[dict] = []
    schedule_loading = False
    today_schedule_loading = False
    grades_loading = False
    exams_loading = False
    plan_loading = False
    second_credits_loading = False
    vpn_manual_loading = False
    schedule_error = ""
    today_schedule_error = ""
    grades_error = ""
    exams_error = ""
    plan_error = ""
    second_credits_error = ""
    active_account = ""
    offline_mode = False

    semester_items: list[dict] = []
    semesters_updated_at = ""
    schedule_updated_at = ""
    today_schedule_updated_at = ""
    grades_updated_at = ""
    exams_updated_at = ""
    plan_updated_at = ""
    second_credits_updated_at = ""
    selected_week = "1"
    selected_semester = CURRENT_SEMESTER
    schedule_mode = "all"
    selected_grade_semester = ALL_SEMESTERS
    selected_exam_semester = CURRENT_SEMESTER
    selected_second_credit_kind = SECOND_CREDIT_QUALITY
    app_settings = load_settings()
    semester_start_date = str(app_settings.get("semester_start_date") or "")
    selected_theme_mode = str(app_settings.get("theme_mode") or "light")
    selected_vpn_mode = str(app_settings.get("vpn_mode") or "startup")
    selected_startup_view = str(app_settings.get("startup_view") or "plan")

    def cleanup():
        if vpn:
            vpn.stop()

    atexit.register(cleanup)

    def theme_is_dark() -> bool:
        mode = selected_theme_mode
        if mode == "auto":
            hour = datetime.now().hour
            return hour >= 18 or hour < 7
        return mode == "dark"

    def colors() -> dict:
        return DARK_THEME if theme_is_dark() else LIGHT_THEME

    def course_color(key: str) -> str:
        return stable_color_from_palette(key, DARK_COURSE_COLORS if theme_is_dark() else COURSE_COLORS)

    def apply_theme():
        c = colors()
        page.bgcolor = c["page"]
        page.theme_mode = ft.ThemeMode.DARK if theme_is_dark() else ft.ThemeMode.LIGHT
        try:
            content_area.bgcolor = c["content"]
            sidebar.bgcolor = c["sidebar"]
            sidebar.border = right_border(1, c["sidebar_border"])
        except NameError:
            pass

    def load_login_theme_from_settings(username: str = ""):
        nonlocal app_settings, semester_start_date, selected_theme_mode, selected_vpn_mode, selected_startup_view
        app_settings = load_settings(username) if username else load_settings()
        semester_start_date = str(app_settings.get("semester_start_date") or "")
        selected_theme_mode = str(app_settings.get("theme_mode") or "light")
        selected_vpn_mode = normalized_vpn_mode(str(app_settings.get("vpn_mode") or "startup"))
        selected_startup_view = normalized_startup_view(str(app_settings.get("startup_view") or "plan"))

    def apply_login_theme():
        apply_theme()
        c = colors()
        field_bg = c["button_bg"] if theme_is_dark() else "#FFFFFF"
        login_shell.bgcolor = c["content"]
        login_title.color = c["text"]
        login_subtitle.color = c["muted"]
        login_vpn_title.color = c["text"]
        vpn_hint.color = c["muted"]
        login_wait_hint.color = c["muted"]
        remember_check.label_style = ft.TextStyle(color=c["muted"])
        vpn_switch.label_text_style = ft.TextStyle(color=c["muted"])
        for field in (username_input, cas_pwd_input, vpn_server_input):
            field.bgcolor = field_bg
            field.color = c["text"]
            field.border_color = c["border"]
            field.focused_border_color = c["button_text"]
            field.label_style = ft.TextStyle(color=c["muted"])
            field.hint_style = ft.TextStyle(color=c["muted"])
        login_btn.bgcolor = c["button_bg"]
        login_btn.color = c["button_text"]
        offline_btn.bgcolor = c["card"]
        offline_btn.color = c["muted"]
        if not status_text.value:
            status_text.color = c["muted"]

    def save_current_settings():
        save_settings(
            {
                "semester_start_date": semester_start_date,
                "theme_mode": selected_theme_mode,
                "vpn_mode": selected_vpn_mode,
                "startup_view": selected_startup_view,
            },
            active_account,
        )

    def normalized_startup_view(value: str) -> str:
        return value if value in {"blank", "plan", "schedule", "grades", "exams", "second_credits"} else "plan"

    def normalized_vpn_mode(value: str) -> str:
        if value == "never":
            return "manual"
        return value if value in {"startup", "refresh", "manual"} else "startup"

    def parse_start_monday():
        try:
            return datetime.strptime(semester_start_date.strip(), "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            return None

    def calculated_week() -> int | None:
        start = parse_start_monday()
        if not start:
            return None
        delta_days = (date.today() - start).days
        if delta_days < 0:
            return 1
        return max(1, min(30, delta_days // 7 + 1))

    def week_status_text() -> str:
        start = parse_start_monday()
        if not start:
            return "\u672a\u8bbe\u7f6e\u5f00\u5b66\u65f6\u95f4"
        if date.today() < start:
            return "\u5047\u671f\u4e2d"
        week = calculated_week()
        return f"\u7b2c {week} \u5468" if week else "\u672a\u8bbe\u7f6e\u5f00\u5b66\u65f6\u95f4"

    def apply_auto_week():
        nonlocal selected_week
        week = calculated_week()
        if week:
            selected_week = str(min(20, week))

    def semester_date_parts() -> tuple[str, str, str]:
        start = parse_start_monday()
        if not start:
            return "", "", ""
        return str(start.year), str(start.month), str(start.day)

    def sync_semester_date_dropdowns():
        year, month, day = semester_date_parts()
        semester_year_dropdown.value = year
        semester_month_dropdown.value = month
        semester_day_dropdown.value = day

    def selected_start_date_value() -> str:
        year = semester_year_dropdown.value or ""
        month = semester_month_dropdown.value or ""
        day = semester_day_dropdown.value or ""
        if not year or not month or not day:
            return ""
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    def start_login(after_creds: bool = False):
        if not after_creds:
            login_btn.disabled = True
            status_text.value = "\u6b63\u5728\u767b\u5f55..."
            status_text.color = colors()["button_text"]
            page.update()
        page.run_thread(do_login, after_creds)

    def start_offline(_=None):
        nonlocal auth, vpn, active_account, offline_mode
        username = username_input.value.strip()
        if not username:
            creds = load_credentials()
            username = (creds or {}).get("username", "")
        if not username:
            status_text.value = "\u8bf7\u5148\u8f93\u5165\u5b66\u53f7\uff0c\u518d\u8fdb\u5165\u79bb\u7ebf\u6a21\u5f0f"
            status_text.color = ft.Colors.RED
            page.update()
            return
        if auth:
            auth.close()
            auth = None
        if vpn:
            vpn.stop()
            vpn = None
        active_account = username
        username_input.value = username
        offline_mode = True
        container.content = app_shell
        reset_app_data()
        apply_theme()
        load_plan_cache()
        load_schedule_cache()
        load_today_schedule_cache()
        load_grade_cache()
        load_exam_cache()
        load_second_credit_cache()
        render_app()

    def do_login(after_creds: bool = False):
        nonlocal auth, vpn, active_account, selected_theme_mode, selected_vpn_mode, selected_startup_view, app_settings, offline_mode
        username = username_input.value.strip()
        cas_pwd = cas_pwd_input.value
        user_settings = load_settings(username) if username else load_settings()
        app_settings = user_settings
        selected_theme_mode = str(user_settings.get("theme_mode") or "light")
        selected_vpn_mode = normalized_vpn_mode(str(user_settings.get("vpn_mode") or "startup"))
        selected_startup_view = normalized_startup_view(str(user_settings.get("startup_view") or "plan"))
        apply_login_theme()
        use_vpn = selected_vpn_mode == "startup" and vpn_switch.value
        vpn_pwd = cas_pwd if use_vpn else ""

        if not username or not cas_pwd:
            if not after_creds:
                status_text.value = "\u8bf7\u8f93\u5165\u5b66\u53f7\u548c\u6559\u52a1\u7cfb\u7edf\u5bc6\u7801"
                status_text.color = ft.Colors.RED
                login_btn.disabled = False
                page.update()
            return

        vpn_server = vpn_server_input.value.strip()

        if use_vpn and not vpn_server:
            if not after_creds:
                status_text.value = "\u8bf7\u8f93\u5165 VPN \u670d\u52a1\u5668\u5730\u5740"
                status_text.color = ft.Colors.RED
                login_btn.disabled = False
                page.update()
            return

        login_btn.disabled = True
        status_text.value = "\u6b63\u5728\u51c6\u5907\u767b\u5f55..."
        status_text.color = colors()["button_text"]
        page.update()

        try:
            if use_vpn:
                status_text.value = "\u6b63\u5728\u8fde\u63a5 VPN..."
                page.update()
                if not (vpn and vpn.is_running()):
                    vpn = VpnManager(server=vpn_server, username=username, password=vpn_pwd)
                    if not vpn.start():
                        detail = vpn.error_summary()
                        status_text.value = f"VPN \u8fde\u63a5\u5931\u8d25\uff1a{detail or '\u8bf7\u68c0\u67e5\u670d\u52a1\u5668\u548c\u5bc6\u7801'}"
                        status_text.color = ft.Colors.RED
                        login_btn.disabled = False
                        page.update()
                        return
                status_text.value = "VPN \u5df2\u8fde\u63a5\uff0c\u6b63\u5728\u7b49\u5f85\u6559\u52a1\u7cfb\u7edf\u54cd\u5e94..."
                page.update()

            status_text.value = "\u6b63\u5728\u767b\u5f55\uff0c\u6559\u52a1\u7cfb\u7edf\u8f83\u6162\u65f6\u8bf7\u8010\u5fc3\u7b49\u5f85..."
            page.update()
            auth = AuthSession(proxy_url=PROXY_URL if use_vpn else "")
            ok = auth.login(username, cas_pwd, CAS_SERVICE_URL)

            if ok:
                active_account = username
                offline_mode = False
                if remember_check.value:
                    save_credentials(username, cas_pwd, cas_pwd, remember=True)
                else:
                    clear_credentials()

                status_text.value = "\u767b\u5f55\u6210\u529f"
                status_text.color = "#2F8F6B"
                show_app_view()
            else:
                detail = auth.last_error if auth else ""
                status_text.value = f"\u767b\u5f55\u5931\u8d25\uff1a{detail or '\u8bf7\u68c0\u67e5\u5b66\u53f7\u548c\u5bc6\u7801'}"
                status_text.color = ft.Colors.RED
                page.update()

        except Exception as ex:
            status_text.value = f"\u767b\u5f55\u5f02\u5e38\uff1a{ex}"
            status_text.color = ft.Colors.RED
            if vpn:
                vpn.stop()
                vpn = None
            page.update()
        finally:
            login_btn.disabled = False
            page.update()

    def do_logout(_=None):
        nonlocal auth, vpn, plan_data, schedule_items, today_schedule_items, grade_items, exam_items, second_credit_items
        nonlocal plan_error, schedule_error, today_schedule_error, grades_error, exams_error, second_credits_error, active_account, offline_mode
        nonlocal plan_loading, schedule_loading, today_schedule_loading, grades_loading, exams_loading, second_credits_loading
        nonlocal selected_week, selected_semester, selected_grade_semester, selected_exam_semester, selected_second_credit_kind, schedule_mode
        if auth:
            auth.close()
            auth = None
        if vpn:
            vpn.stop()
            vpn = None
        login_btn.disabled = False
        plan_data = {}
        schedule_items = []
        today_schedule_items = []
        grade_items = []
        exam_items = []
        second_credit_items = []
        plan_loading = False
        schedule_loading = False
        today_schedule_loading = False
        grades_loading = False
        exams_loading = False
        second_credits_loading = False
        active_account = ""
        offline_mode = False
        selected_week = "1"
        selected_semester = CURRENT_SEMESTER
        selected_grade_semester = ALL_SEMESTERS
        selected_exam_semester = CURRENT_SEMESTER
        selected_second_credit_kind = SECOND_CREDIT_QUALITY
        schedule_mode = "all"
        plan_error = ""
        schedule_error = ""
        today_schedule_error = ""
        grades_error = ""
        exams_error = ""
        second_credits_error = ""
        page.window.width = 1320
        page.window.height = 860
        load_login_theme_from_settings(username_input.value.strip())
        apply_login_theme()
        container.content = login_shell
        status_text.value = ""
        status_text.color = colors()["muted"]
        page.update()

    def set_view(name: str):
        nonlocal current_view
        current_view = name
        render_app()
        if name == "plan" and not plan_data and not plan_loading and not plan_updated_at:
            start_fetch_plan()
        if name == "schedule" and not schedule_items and not schedule_loading:
            start_fetch_schedule()
        if name == "grades" and not grade_items and not grades_loading:
            start_fetch_grades()
        if name == "exams" and not exam_items and not exams_loading and not exams_updated_at:
            start_fetch_exams()
        if name == "second_credits" and not second_credit_items and not second_credits_loading and not second_credits_updated_at:
            start_fetch_second_credits()

    def show_app_view():
        container.content = app_shell
        reset_app_data()
        apply_theme()
        load_plan_cache()
        load_schedule_cache()
        load_today_schedule_cache()
        load_grade_cache()
        load_exam_cache()
        load_second_credit_cache()
        render_app()
        page.update()
        start_fetch_semesters()
        if current_view == "plan" and not plan_data:
            start_fetch_plan()
        elif current_view == "schedule" and not schedule_items:
            start_fetch_schedule()
        elif current_view == "grades" and not grade_items:
            start_fetch_grades()
        elif current_view == "exams" and not exam_items:
            start_fetch_exams()
        elif current_view == "second_credits" and not second_credit_items:
            start_fetch_second_credits()

    def schedule_cache_key() -> str:
        return selected_semester if selected_semester != CURRENT_SEMESTER else CURRENT_SEMESTER

    def grade_cache_key() -> str:
        return selected_grade_semester if selected_grade_semester != ALL_SEMESTERS else ALL_SEMESTERS

    def exam_cache_key() -> str:
        return selected_exam_semester if selected_exam_semester != CURRENT_SEMESTER else CURRENT_SEMESTER

    def second_credit_cache_key() -> str:
        return selected_second_credit_kind

    def reset_app_data():
        nonlocal plan_data, schedule_items, today_schedule_items, grade_items, exam_items, second_credit_items, semester_items
        nonlocal plan_error, schedule_error, today_schedule_error, grades_error, exams_error, second_credits_error
        nonlocal plan_updated_at, schedule_updated_at, today_schedule_updated_at, grades_updated_at, exams_updated_at, second_credits_updated_at, semesters_updated_at
        nonlocal plan_loading, schedule_loading, today_schedule_loading, grades_loading, exams_loading, second_credits_loading
        nonlocal selected_week, selected_semester, selected_grade_semester, selected_exam_semester, selected_second_credit_kind, schedule_mode
        nonlocal app_settings, semester_start_date, selected_theme_mode, selected_vpn_mode, selected_startup_view, current_view
        app_settings = load_settings(active_account)
        semester_start_date = str(app_settings.get("semester_start_date") or "")
        selected_theme_mode = str(app_settings.get("theme_mode") or "light")
        selected_vpn_mode = normalized_vpn_mode(str(app_settings.get("vpn_mode") or "startup"))
        selected_startup_view = normalized_startup_view(str(app_settings.get("startup_view") or "plan"))
        current_view = selected_startup_view
        try:
            sync_semester_date_dropdowns()
            vpn_switch.value = selected_vpn_mode == "startup"
            on_vpn_toggle(None)
        except NameError:
            pass
        plan_data = {}
        schedule_items = []
        today_schedule_items = []
        grade_items = []
        exam_items = []
        second_credit_items = []
        plan_loading = False
        schedule_loading = False
        today_schedule_loading = False
        grades_loading = False
        exams_loading = False
        second_credits_loading = False
        selected_week = "1"
        apply_auto_week()
        selected_semester = CURRENT_SEMESTER
        schedule_mode = "all"
        selected_grade_semester = ALL_SEMESTERS
        selected_exam_semester = CURRENT_SEMESTER
        selected_second_credit_kind = SECOND_CREDIT_QUALITY
        semester_items = load_semesters(active_account) or []
        plan_error = ""
        schedule_error = ""
        today_schedule_error = ""
        grades_error = ""
        exams_error = ""
        second_credits_error = ""
        plan_updated_at = ""
        schedule_updated_at = ""
        today_schedule_updated_at = ""
        grades_updated_at = ""
        exams_updated_at = ""
        second_credits_updated_at = ""
        semesters_updated_at = load_semesters_updated_at(active_account)

    def format_updated_at(value: str) -> str:
        if not value:
            return "\u4e0a\u6b21\u6570\u636e\u66f4\u65b0\u65f6\u95f4\uff1a\u6682\u65e0"
        return f"\u4e0a\u6b21\u6570\u636e\u66f4\u65b0\u65f6\u95f4\uff1a{value.replace('T', ' ')}"

    def compact_updated_at(label: str, value: str) -> str:
        if not value:
            return f"{label}\uff1a\u6682\u65e0"
        return f"{label}\uff1a{value.replace('T', ' ')}"

    def load_plan_cache():
        nonlocal plan_data, plan_error, plan_updated_at
        plan_data = load_plan_completion(active_account) or {}
        plan_updated_at = load_plan_completion_updated_at(active_account)
        plan_error = "" if plan_data else plan_error

    def load_schedule_cache():
        nonlocal schedule_items, schedule_error, schedule_updated_at
        schedule_items = load_schedule(schedule_cache_key(), active_account) or []
        schedule_updated_at = load_schedule_updated_at(schedule_cache_key(), active_account)
        schedule_error = "" if schedule_items else schedule_error

    def load_today_schedule_cache():
        nonlocal today_schedule_items, today_schedule_error, today_schedule_updated_at
        today_schedule_items = load_today_schedule(active_account) or []
        today_schedule_updated_at = load_today_schedule_updated_at(active_account)
        today_schedule_error = "" if today_schedule_items else today_schedule_error

    def load_grade_cache():
        nonlocal grade_items, grades_error, grades_updated_at
        grade_items = load_grades(grade_cache_key(), active_account) or []
        grades_updated_at = load_grades_updated_at(grade_cache_key(), active_account)
        grades_error = "" if grade_items else grades_error

    def load_exam_cache():
        nonlocal exam_items, exams_error, exams_updated_at
        exam_items = load_exams(account=active_account, semester=exam_cache_key()) or []
        exams_updated_at = load_exams_updated_at(account=active_account, semester=exam_cache_key())
        exams_error = "" if exam_items else exams_error

    def load_second_credit_cache():
        nonlocal second_credit_items, second_credits_error, second_credits_updated_at
        second_credit_items = load_second_credits(account=active_account, semester=second_credit_cache_key()) or []
        second_credits_updated_at = load_second_credits_updated_at(
            account=active_account,
            semester=second_credit_cache_key(),
        )
        second_credits_error = "" if second_credit_items else second_credits_error

    def start_fetch_semesters():
        if offline_mode:
            return
        if not auth:
            return
        page.run_thread(load_semester_data, active_account)

    def offline_fetch_message(target: str):
        return f"\u79bb\u7ebf\u6a21\u5f0f\u4e0b\u53ea\u80fd\u67e5\u770b\u7f13\u5b58\uff0c\u9700\u8981\u8054\u7f51\u767b\u5f55\u540e\u5237\u65b0{target}"

    def ensure_vpn_for_refresh() -> str:
        nonlocal vpn
        if selected_vpn_mode != "refresh":
            return ""
        if not auth:
            return "\u9700\u8981\u5148\u8054\u7f51\u767b\u5f55"
        vpn_server = vpn_server_input.value.strip()
        username = username_input.value.strip()
        vpn_pwd = current_vpn_password(username)
        if not vpn_server or not username or not vpn_pwd:
            return "\u8bf7\u5148\u586b\u5199 VPN \u670d\u52a1\u5668\u3001\u5b66\u53f7\u548c\u6559\u52a1\u7cfb\u7edf\u5bc6\u7801"
        if not vpn:
            vpn = VpnManager(server=vpn_server, username=username, password=vpn_pwd)
            if not vpn.start():
                detail = vpn.error_summary()
                vpn = None
                return f"VPN \u8fde\u63a5\u5931\u8d25\uff1a{detail or '\u8bf7\u68c0\u67e5\u670d\u52a1\u5668\u548c\u5bc6\u7801'}"
        proxy_url = PROXY_URL
        if proxy_url.startswith("socks5://"):
            proxy_url = "socks5h://" + proxy_url[len("socks5://"):]
        auth.get_session().proxies = {"http": proxy_url, "https": proxy_url}
        return ""

    def vpn_proxy_settings() -> dict:
        proxy_url = PROXY_URL
        if proxy_url.startswith("socks5://"):
            proxy_url = "socks5h://" + proxy_url[len("socks5://"):]
        return {"http": proxy_url, "https": proxy_url}

    def apply_vpn_proxy(enabled: bool):
        if not auth:
            return
        auth.get_session().proxies = vpn_proxy_settings() if enabled else {}

    def current_vpn_password(username: str = "") -> str:
        if cas_pwd_input.value:
            return cas_pwd_input.value
        creds = load_credentials()
        if creds and (not username or creds.get("username") == username):
            return creds.get("cas_password") or creds.get("vpn_password") or ""
        return ""

    def vpn_is_running() -> bool:
        return bool(vpn and vpn.is_running())

    def toggle_manual_vpn(_=None):
        nonlocal vpn, vpn_manual_loading
        if vpn_manual_loading:
            return
        if vpn_is_running():
            vpn.stop()
            vpn = None
            apply_vpn_proxy(False)
            vpn_settings_message.value = "VPN \u5df2\u5173\u95ed"
            vpn_settings_message.color = colors()["success"]
            render_app()
            return
        vpn_server = vpn_server_input.value.strip()
        username = username_input.value.strip() or active_account
        vpn_pwd = current_vpn_password(username)
        if not vpn_server or not username or not vpn_pwd:
            vpn_settings_message.value = "\u8bf7\u5148\u586b\u5199 VPN \u670d\u52a1\u5668\u3001\u5b66\u53f7\u548c\u6559\u52a1\u7cfb\u7edf\u5bc6\u7801"
            vpn_settings_message.color = colors()["danger"]
            render_app()
            return
        vpn_manual_loading = True
        vpn_settings_message.value = "VPN \u6b63\u5728\u8fde\u63a5..."
        vpn_settings_message.color = colors()["muted"]
        render_app()
        page.run_thread(start_manual_vpn, vpn_server, username, vpn_pwd)

    def start_manual_vpn(vpn_server: str, username: str, vpn_pwd: str):
        nonlocal auth, vpn, vpn_manual_loading, offline_mode, active_account
        try:
            manager = VpnManager(server=vpn_server, username=username, password=vpn_pwd)
            if manager.start():
                vpn = manager
                apply_vpn_proxy(True)
                if offline_mode:
                    cas_pwd = current_vpn_password(username)
                    if cas_pwd:
                        online_auth = AuthSession(proxy_url=PROXY_URL)
                        if online_auth.login(username, cas_pwd, CAS_SERVICE_URL):
                            auth = online_auth
                            active_account = username
                            username_input.value = username
                            offline_mode = False
                            vpn_settings_message.value = "VPN \u5df2\u5f00\u542f\uff0c\u5df2\u5207\u6362\u5230\u5728\u7ebf\u6a21\u5f0f"
                            vpn_settings_message.color = colors()["success"]
                            start_fetch_semesters()
                        else:
                            online_auth.close()
                            vpn_settings_message.value = f"VPN \u5df2\u5f00\u542f\uff0c\u4f46\u81ea\u52a8\u767b\u5f55\u5931\u8d25\uff1a{online_auth.last_error or '\u8bf7\u91cd\u65b0\u767b\u5f55'}"
                            vpn_settings_message.color = colors()["danger"]
                    else:
                        vpn_settings_message.value = "VPN \u5df2\u5f00\u542f\uff0c\u4f46\u7f3a\u5c11\u6559\u52a1\u5bc6\u7801\uff0c\u9700\u8981\u91cd\u65b0\u767b\u5f55\u540e\u5207\u6362\u5728\u7ebf\u6a21\u5f0f"
                        vpn_settings_message.color = colors()["danger"]
                else:
                    vpn_settings_message.value = "VPN \u5df2\u5f00\u542f"
                    vpn_settings_message.color = colors()["success"]
            else:
                detail = manager.error_summary()
                vpn = None
                apply_vpn_proxy(False)
                vpn_settings_message.value = f"VPN \u8fde\u63a5\u5931\u8d25\uff1a{detail or '\u8bf7\u68c0\u67e5\u670d\u52a1\u5668\u548c\u5bc6\u7801'}"
                vpn_settings_message.color = colors()["danger"]
        finally:
            vpn_manual_loading = False
            render_app()

    def load_semester_data(account: str):
        nonlocal semester_items, semesters_updated_at
        try:
            from app.scraper import Scraper

            if not auth:
                return
            scraper = Scraper(auth)
            fetched = scraper.get_semesters()
            if account != active_account:
                return
            if fetched:
                semester_items = filter_recent_semesters(fetched)
                save_semesters(semester_items, account)
                semesters_updated_at = load_semesters_updated_at(account)
                render_app()
        except Exception:
            pass

    def semester_name(semester_id: str) -> str:
        for item in semester_items:
            if str(item.get("id")) == str(semester_id):
                return item.get("name") or str(semester_id)
        return str(semester_id)

    def annotate_grades(grades: list[dict], semester_id: str, name: str = "") -> list[dict]:
        annotated = []
        for grade in grades:
            item = dict(grade)
            item["semester"] = str(semester_id)
            item["semester_name"] = name or semester_name(str(semester_id))
            annotated.append(item)
        return annotated

    def start_fetch_schedule(_=None):
        nonlocal schedule_loading, schedule_error
        if offline_mode:
            schedule_error = offline_fetch_message("\u8bfe\u8868")
            render_app()
            return
        if not auth or schedule_loading:
            return
        vpn_error = ensure_vpn_for_refresh()
        if vpn_error:
            schedule_error = vpn_error
            render_app()
            return
        schedule_loading = True
        schedule_error = ""
        render_app()
        cache_key = schedule_cache_key()
        semester = "" if selected_semester == CURRENT_SEMESTER else selected_semester
        page.run_thread(load_schedule_data, active_account, cache_key, semester)

    def load_schedule_data(account: str, cache_key: str, semester: str):
        nonlocal schedule_items, schedule_loading, schedule_error, schedule_updated_at
        try:
            from app.scraper import Scraper

            if not auth:
                return
            scraper = Scraper(auth)
            fetched_schedule = scraper.fetch_schedule(semester=semester)
            if account != active_account or cache_key != schedule_cache_key():
                return
            schedule_items = fetched_schedule
            if schedule_items:
                save_schedule(cache_key, schedule_items, account)
                schedule_updated_at = load_schedule_updated_at(cache_key, account)
            schedule_error = "" if schedule_items else "No schedule data found"
        except Exception as ex:
            if account == active_account and cache_key == schedule_cache_key():
                schedule_error = str(ex)
        finally:
            if account == active_account and cache_key == schedule_cache_key():
                schedule_loading = False
                render_app()

    def start_fetch_today_schedule(_=None):
        nonlocal today_schedule_loading, today_schedule_error
        if offline_mode:
            today_schedule_error = offline_fetch_message("\u4eca\u65e5\u8bfe\u8868")
            render_app()
            return
        if not auth or today_schedule_loading:
            return
        vpn_error = ensure_vpn_for_refresh()
        if vpn_error:
            today_schedule_error = vpn_error
            render_app()
            return
        today_schedule_loading = True
        today_schedule_error = ""
        render_app()
        page.run_thread(load_today_schedule_data, active_account)

    def load_today_schedule_data(account: str):
        nonlocal today_schedule_items, today_schedule_loading, today_schedule_error, today_schedule_updated_at
        try:
            from app.scraper import Scraper

            if not auth:
                return
            scraper = Scraper(auth)
            fetched = scraper.fetch_today_schedule()
            if account != active_account:
                return
            today_schedule_items = fetched
            save_today_schedule(today_schedule_items, account)
            today_schedule_updated_at = load_today_schedule_updated_at(account)
            today_schedule_error = ""
        except Exception as ex:
            if account == active_account:
                today_schedule_error = str(ex)
        finally:
            if account == active_account:
                today_schedule_loading = False
                render_app()

    def start_fetch_grades(_=None):
        nonlocal grades_loading, grades_error
        if offline_mode:
            grades_error = offline_fetch_message("\u6210\u7ee9")
            render_app()
            return
        if not auth or grades_loading:
            return
        vpn_error = ensure_vpn_for_refresh()
        if vpn_error:
            grades_error = vpn_error
            render_app()
            return
        grades_loading = True
        grades_error = ""
        render_app()
        cache_key = grade_cache_key()
        grade_selection = selected_grade_semester
        page.run_thread(load_grade_data, active_account, cache_key, grade_selection)

    def load_grade_data(account: str, cache_key: str, grade_selection: str):
        nonlocal grade_items, grades_loading, grades_error, grades_updated_at, semester_items, semesters_updated_at
        try:
            from app.scraper import Scraper

            if not auth:
                return
            scraper = Scraper(auth)
            if grade_selection == ALL_SEMESTERS and not semester_items:
                fetched_semesters = filter_recent_semesters(scraper.get_semesters())
                if account != active_account or grade_selection != selected_grade_semester:
                    return
                if fetched_semesters:
                    semester_items = fetched_semesters
                    save_semesters(semester_items, account)
                    semesters_updated_at = load_semesters_updated_at(account)
            if grade_selection == ALL_SEMESTERS and semester_items:
                collected: list[dict] = []
                for semester_item in semester_items:
                    semester_id = str(semester_item.get("id") or "")
                    if not semester_id:
                        continue
                    try:
                        grades = scraper.fetch_grades(semester=semester_id)
                    except Exception as ex:
                        print(f"[Grades] semester {semester_id} failed: {ex}")
                        continue
                    if account != active_account:
                        return
                    annotated = annotate_grades(grades, semester_id, semester_item.get("name") or semester_id)
                    if annotated:
                        save_grades(annotated, semester_id, account)
                    collected.extend(annotated)
                if account != active_account or grade_selection != selected_grade_semester:
                    return
                grade_items = collected
            else:
                semester = "" if grade_selection == ALL_SEMESTERS else grade_selection
                fetched_grades = scraper.fetch_grades(semester=semester)
                if account != active_account or grade_selection != selected_grade_semester:
                    return
                grade_items = fetched_grades
                if grade_selection != ALL_SEMESTERS:
                    grade_items = annotate_grades(grade_items, grade_selection)
            if grade_items:
                save_grades(grade_items, cache_key, account)
                grades_updated_at = load_grades_updated_at(cache_key, account)
            grades_error = "" if grade_items else "No grade data found"
        except Exception as ex:
            if account == active_account and grade_selection == selected_grade_semester:
                grades_error = str(ex)
        finally:
            if account == active_account and grade_selection == selected_grade_semester:
                grades_loading = False
                render_app()

    def start_fetch_exams(_=None):
        nonlocal exams_loading, exams_error
        if offline_mode:
            exams_error = offline_fetch_message("\u8003\u8bd5")
            render_app()
            return
        if not auth or exams_loading:
            return
        vpn_error = ensure_vpn_for_refresh()
        if vpn_error:
            exams_error = vpn_error
            render_app()
            return
        exams_loading = True
        exams_error = ""
        render_app()
        cache_key = exam_cache_key()
        exam_selection = selected_exam_semester
        page.run_thread(load_exam_data, active_account, cache_key, exam_selection)

    def load_exam_data(account: str, cache_key: str, exam_selection: str):
        nonlocal exam_items, exams_loading, exams_error, exams_updated_at
        try:
            from app.scraper import Scraper

            if not auth:
                return
            scraper = Scraper(auth)
            semester = "" if exam_selection == CURRENT_SEMESTER else exam_selection
            fetched_exams = scraper.fetch_exams(semester=semester)
            if account != active_account or exam_selection != selected_exam_semester:
                return
            exam_items = fetched_exams
            save_exams(exam_items, account=account, semester=cache_key)
            exams_updated_at = load_exams_updated_at(account=account, semester=cache_key)
            exams_error = ""
        except Exception as ex:
            if account == active_account and exam_selection == selected_exam_semester:
                exams_error = str(ex)
        finally:
            if account == active_account and exam_selection == selected_exam_semester:
                exams_loading = False
                render_app()

    def start_fetch_plan(_=None):
        nonlocal plan_loading, plan_error
        if offline_mode:
            plan_error = offline_fetch_message("\u57f9\u517b\u8ba1\u5212")
            render_app()
            return
        if not auth or plan_loading:
            return
        vpn_error = ensure_vpn_for_refresh()
        if vpn_error:
            plan_error = vpn_error
            render_app()
            return
        plan_loading = True
        plan_error = ""
        render_app()
        page.run_thread(load_plan_data, active_account)

    def load_plan_data(account: str):
        nonlocal plan_data, plan_loading, plan_error, plan_updated_at
        try:
            from app.scraper import Scraper

            if not auth:
                return
            scraper = Scraper(auth)
            fetched = scraper.fetch_plan_completion()
            if account != active_account:
                return
            plan_data = fetched
            if plan_data:
                save_plan_completion(plan_data, account)
                plan_updated_at = load_plan_completion_updated_at(account)
                plan_error = ""
            else:
                plan_error = "\u6682\u65e0\u57f9\u517b\u8ba1\u5212\u6570\u636e"
        except Exception as ex:
            if account == active_account:
                plan_error = str(ex)
        finally:
            if account == active_account:
                plan_loading = False
                render_app()

    def start_fetch_second_credits(_=None):
        nonlocal second_credits_loading, second_credits_error
        if offline_mode:
            second_credits_error = offline_fetch_message("\u7d20\u62d3\u5206")
            render_app()
            return
        if not auth or second_credits_loading:
            return
        vpn_error = ensure_vpn_for_refresh()
        if vpn_error:
            second_credits_error = vpn_error
            render_app()
            return
        second_credits_loading = True
        second_credits_error = ""
        render_app()
        cache_key = second_credit_cache_key()
        selection = selected_second_credit_kind
        page.run_thread(load_second_credit_data, active_account, cache_key, selection)

    def load_second_credit_data(account: str, cache_key: str, selection: str):
        nonlocal second_credit_items, second_credits_loading, second_credits_error, second_credits_updated_at
        try:
            from app.scraper import Scraper

            if not auth:
                return
            if selection != SECOND_CREDIT_QUALITY:
                if account == active_account and selection == selected_second_credit_kind:
                    second_credit_items = []
                    second_credits_error = ""
                return
            scraper = Scraper(auth)
            fetched_items = scraper.fetch_second_credits(kind=selection)
            if account != active_account or selection != selected_second_credit_kind:
                return
            second_credit_items = fetched_items
            if second_credit_items:
                save_second_credits(second_credit_items, account=account, semester=cache_key)
                second_credits_updated_at = load_second_credits_updated_at(account=account, semester=cache_key)
                second_credits_error = ""
            else:
                second_credits_error = "\u6682\u65e0\u7d20\u62d3\u5206\u6570\u636e"
        except Exception as ex:
            if account == active_account and selection == selected_second_credit_kind:
                second_credits_error = str(ex)
        finally:
            if account == active_account and selection == selected_second_credit_kind:
                second_credits_loading = False
                render_app()

    def start_fetch_all(_=None):
        if offline_mode:
            vpn_settings_message.value = "\u79bb\u7ebf\u6a21\u5f0f\u4e0b\u65e0\u6cd5\u5237\u65b0\uff0c\u9700\u8981\u8054\u7f51\u767b\u5f55\u540e\u518d\u5168\u90e8\u5237\u65b0"
            vpn_settings_message.color = colors()["danger"]
            render_app()
            return
        if not auth:
            vpn_settings_message.value = "\u9700\u8981\u5148\u8054\u7f51\u767b\u5f55\uff0c\u624d\u80fd\u5168\u90e8\u5237\u65b0"
            vpn_settings_message.color = colors()["danger"]
            render_app()
            return
        if any((plan_loading, schedule_loading, today_schedule_loading, grades_loading, exams_loading, second_credits_loading)):
            vpn_settings_message.value = "\u5df2\u6709\u6570\u636e\u5728\u5237\u65b0\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5"
            vpn_settings_message.color = colors()["warning"]
            render_app()
            return
        vpn_settings_message.value = "\u5df2\u5f00\u59cb\u5168\u90e8\u5237\u65b0\uff0c\u6559\u52a1\u7cfb\u7edf\u54cd\u5e94\u6162\u65f6\u8bf7\u7a0d\u7b49"
        vpn_settings_message.color = colors()["button_text"]
        render_app()
        start_fetch_semesters()
        start_fetch_plan()
        start_fetch_schedule()
        start_fetch_today_schedule()
        start_fetch_grades()
        start_fetch_exams()
        start_fetch_second_credits()

    def render_app():
        apply_theme()
        sidebar.content = build_sidebar()
        content_area.content = build_content()
        page.update()

    def build_sidebar():
        c = colors()
        username = username_input.value.strip() or "Guest"
        today = date.today().strftime("%Y-%m-%d")
        return ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("\u4e2a\u4eba\u4fe1\u606f", size=12, color=c["muted"]),
                            ft.Text(username, size=22, weight=ft.FontWeight.W_700, color=c["text"], max_lines=1),
                            ft.Text(today, size=13, color=c["muted"]),
                            ft.Text(week_status_text(), size=13, weight=ft.FontWeight.W_600, color=c["button_text"]),
                            *(
                                [
                                    ft.Container(
                                        content=ft.Text("\u79bb\u7ebf\u6a21\u5f0f", size=12, weight=ft.FontWeight.W_700, color=c["warning"]),
                                        padding=pad_xy(10, 4),
                                        bgcolor=c["soft"],
                                        border=all_border(1, c["warning"]),
                                        border_radius=8,
                                    )
                                ]
                                if offline_mode else []
                            ),
                        ],
                        spacing=6,
                    ),
                    padding=pad(22, 26, 22, 18),
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("\u57fa\u7840\u529f\u80fd", size=12, color=c["muted"]),
                            nav_item("\u57f9\u517b\u8ba1\u5212", ft.Icons.MENU_BOOK, "plan"),
                            nav_item("\u8bfe\u8868", ft.Icons.CALENDAR_MONTH, "schedule"),
                            nav_item("\u6210\u7ee9", ft.Icons.BAR_CHART, "grades"),
                            nav_item("\u6211\u7684\u8003\u8bd5", ft.Icons.EVENT_NOTE, "exams"),
                            nav_item("\u7d20\u62d3\u5206", ft.Icons.WORKSPACE_PREMIUM, "second_credits"),
                        ],
                        spacing=8,
                    ),
                    padding=pad_xy(14, 10),
                ),
                ft.Container(expand=True),
                ft.Container(
                    content=ft.Column(
                        [
                            bottom_item("\u8bbe\u7f6e", ft.Icons.SETTINGS, view_name="settings", on_click=lambda _: set_view("settings")),
                            bottom_item("\u652f\u6301\u4e0e\u5e2e\u52a9", ft.Icons.HELP_OUTLINE, view_name="support", on_click=lambda _: set_view("support")),
                            bottom_item("\u9000\u51fa\u767b\u5f55", ft.Icons.LOGOUT, danger=True, on_click=do_logout),
                        ],
                        spacing=6,
                    ),
                    padding=pad(14, 12, 14, 20),
                ),
            ],
            spacing=0,
            expand=True,
        )

    def nav_item(label: str, icon, view_name: str):
        c = colors()
        active = current_view == view_name
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=20, color=c["button_text"] if active else c["muted"]),
                    ft.Text(label, size=15, color=c["text"] if active else c["muted"], weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400),
                ],
                spacing=12,
            ),
            height=46,
            padding=pad_xy(12, 0),
            alignment=ft.Alignment(-1, 0),
            bgcolor=c["active"] if active else None,
            border_radius=8,
            on_click=lambda _: set_view(view_name),
        )

    def bottom_item(label: str, icon, disabled: bool = False, danger: bool = False, on_click=None, view_name: str = ""):
        c = colors()
        active = bool(view_name and current_view == view_name)
        color = c["danger"] if danger else ("#A4B1AD" if disabled else (c["button_text"] if active else c["muted"]))
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=19, color=color),
                    ft.Text(label, size=14, color=color, weight=ft.FontWeight.W_600 if danger or active else ft.FontWeight.W_400),
                ],
                spacing=12,
            ),
            height=42,
            padding=pad_xy(12, 0),
            alignment=ft.Alignment(-1, 0),
            bgcolor=c["active"] if active else None,
            border_radius=8,
            on_click=on_click,
        )

    def build_content():
        if current_view == "blank":
            return build_blank_view()
        if current_view == "plan":
            return build_plan_view()
        if current_view == "grades":
            return build_grades_view()
        if current_view == "exams":
            return build_exams_view()
        if current_view == "second_credits":
            return build_second_credits_view()
        if current_view == "settings":
            return build_settings_view()
        if current_view == "support":
            return build_support_view()
        return build_schedule_view()

    def build_blank_view():
        c = colors()
        return ft.Container(
            content=ft.Container(expand=True),
            padding=pad_xy(28, 26),
            expand=True,
            bgcolor=c["content"],
        )

    def build_plan_view():
        if plan_loading:
            body = loading_view("\u6b63\u5728\u52a0\u8f7d\u57f9\u517b\u8ba1\u5212")
        elif plan_error:
            body = error_view(plan_error, start_fetch_plan)
        elif not plan_data:
            body = empty_view("\u6682\u65e0\u57f9\u517b\u8ba1\u5212\u6570\u636e")
        else:
            body = plan_body()

        return ft.Container(
            content=ft.Column(
                [
                    page_header(
                        "\u57f9\u517b\u8ba1\u5212",
                        f"\u4e13\u4e1a\u3001\u5b66\u5206\u5b8c\u6210\u60c5\u51b5\u4e0e GPA | {format_updated_at(plan_updated_at)}",
                        [small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_plan)],
                    ),
                    body,
                ],
                spacing=18,
                expand=True,
            ),
            padding=pad_xy(28, 26),
            expand=True,
            bgcolor=colors()["content"],
        )

    def plan_body():
        info = plan_data.get("info", {}) if isinstance(plan_data, dict) else {}
        sections = plan_data.get("sections", []) if isinstance(plan_data, dict) else []
        return ft.Column(
            [
                ft.Row(
                    [
                        plan_info_card("\u4e13\u4e1a\u540d\u79f0", info.get("major") or "-"),
                        plan_info_card("\u8981\u6c42\u5b66\u5206 / \u5b9e\u4fee\u5b66\u5206", plan_credit_text(info)),
                        plan_info_card("GPA", str(info.get("gpa") or "-")),
                    ],
                    spacing=12,
                ),
                plan_sections_view(sections),
            ],
            spacing=14,
            expand=True,
        )

    def plan_credit_text(info: dict) -> str:
        text = str(info.get("credit_completion") or "").strip()
        if text:
            return text
        required = info.get("required_credit")
        completed = info.get("completed_credit")
        if required or completed:
            return f"{required:g} / {completed:g}"
        return "-"

    def plan_info_card(label: str, value: str):
        c = colors()
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(label, size=12, color=c["muted"]),
                    ft.Text(value, size=18, weight=ft.FontWeight.W_700, color=c["text"], max_lines=2),
                ],
                spacing=4,
            ),
            height=84,
            padding=pad_xy(16, 14),
            bgcolor=c["soft"],
            border=all_border(1, c["border"]),
            border_radius=8,
            expand=True,
        )

    def plan_sections_view(sections: list[dict]):
        if not sections:
            return empty_view("\u6682\u65e0\u57f9\u517b\u8ba1\u5212\u660e\u7ec6")
        grouped_sections = plan_group_sections(sections)
        tiles = [plan_section_tile(section, index) for index, section in enumerate(grouped_sections)]
        return ft.ListView(tiles, spacing=10, expand=True, padding=pad(right=8))

    def plan_group_sections(sections: list[dict]) -> list[dict]:
        grouped: list[dict] = []
        current_parent: dict | None = None
        for section in sections:
            title = str(section.get("title") or "").strip()
            item = dict(section)
            item["children"] = []
            if plan_is_child_section(title) and current_parent is not None:
                current_parent.setdefault("children", []).append(item)
                continue
            grouped.append(item)
            current_parent = item if title != "\u8ba1\u5212\u5916\u8bfe\u7a0b" else None
        return grouped

    def plan_is_child_section(title: str) -> bool:
        return bool(re.match(r"^[\uFF08(]\s*(?:[\u4E00\u4E8C\u4E09\u56DB\u4E94\u516D\u4E03\u516B\u4E5D\u5341]+|\d+)\s*[\uFF09)]", title or ""))

    def plan_section_tile(section: dict, index: int, nested: bool = False):
        c = colors()
        title = section.get("title") or "\u672a\u5206\u7c7b\u8bfe\u7a0b"
        required = section.get("required_credit") or 0
        completed = section.get("completed_credit") or 0
        courses = section.get("courses") or []
        children = section.get("children") or []
        total_courses = len(courses) + sum(len(child.get("courses") or []) for child in children)
        subtitle = f"\u8981\u6c42/\u5b9e\u4fee {format_credit_value(required)}/{format_credit_value(completed)} | {total_courses} \u95e8\u8bfe"
        child_controls = [plan_section_tile(child, child_index, nested=True) for child_index, child in enumerate(children)]
        course_controls = [plan_course_row(course, title) for course in courses]
        controls = course_controls + child_controls
        return ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row(
                    [
                        ft.Text(title, size=15, weight=ft.FontWeight.W_700, color=c["text"], expand=True, max_lines=1),
                        plan_credit_progress(completed, required),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                subtitle=ft.Text(subtitle, size=12, color=c["muted"]),
                controls=controls or [ft.Text("\u6682\u65e0\u8bfe\u7a0b\u660e\u7ec6", size=12, color=c["muted"])],
                tile_padding=pad_xy(14, 4),
                controls_padding=pad(14 if not nested else 8, 0, 14, 12),
                collapsed_bgcolor=c["card"],
                bgcolor=c["card"],
                icon_color=c["muted"],
                collapsed_icon_color=c["muted"],
                expanded=(index == 0 and not nested),
            ),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=8,
        )

    def plan_credit_progress(completed, required):
        c = colors()
        try:
            completed_value = float(completed or 0)
            required_value = float(required or 0)
        except (TypeError, ValueError):
            completed_value = 0.0
            required_value = 0.0
        progress = min(1.0, completed_value / required_value) if required_value > 0 else (1.0 if completed_value > 0 else 0.0)
        color = c["success"] if required_value > 0 and completed_value >= required_value else c["button_text"]
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(f"\u8981\u6c42/\u5b9e\u4fee {required_value:g}/{completed_value:g}", size=11, color=c["muted"], text_align=ft.TextAlign.RIGHT),
                    ft.ProgressBar(value=progress, bar_height=5, color=color, bgcolor=c["border"]),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.END,
            ),
            width=150,
        )

    def plan_course_row(course: dict, section_title: str = ""):
        c = colors()
        name = course.get("name") or "\u672a\u547d\u540d\u8bfe\u7a0b"
        note = course.get("note") or ""
        passed_text = course.get("passed_text") or ""
        status_text_value, status_color = plan_status_info(f"{passed_text} {note}")
        credit = format_credit_value(course.get("credit") or 0)
        special = plan_special_text(course, section_title)
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=5, height=38, bgcolor=course_color(name), border_radius=5),
                    ft.Container(
                        content=ft.Text(
                            name,
                            size=13,
                            weight=ft.FontWeight.W_700,
                            color=c["text"],
                            max_lines=1,
                        ),
                        height=38,
                        alignment=ft.Alignment(-1, 0),
                        expand=True,
                    ),
                    compact_plan_tag(f"{credit} \u5b66\u5206"),
                    compact_plan_tag(special),
                    plan_status_badge(status_text_value, status_color, c["soft"]),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=50,
            padding=pad_xy(10, 0),
            bgcolor=c["soft"],
            border=all_border(1, c["border"]),
            border_radius=8,
            tooltip=plan_course_tooltip(course, section_title, status_text_value, special),
        )

    def compact_plan_tag(text: str):
        c = colors()
        return ft.Container(
            content=ft.Text(text or "-", size=11, color=c["muted"], max_lines=1),
            height=26,
            padding=pad_xy(8, 0),
            alignment=ft.Alignment(0, 0),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=7,
        )

    def plan_status_badge(text: str, color: str, bgcolor: str):
        return ft.Container(
            content=ft.Text(text, size=13, weight=ft.FontWeight.W_700, color=color),
            width=78,
            height=30,
            alignment=ft.Alignment(0, 0),
            bgcolor=bgcolor,
            border=all_border(1, f"{color}33"),
            border_radius=15,
        )

    def format_credit_value(value) -> str:
        try:
            number = float(value or 0)
            return f"{number:g}"
        except (TypeError, ValueError):
            return str(value or "0")

    def plan_special_text(course: dict, section_title: str = "") -> str:
        haystack = " ".join(
            str(value or "")
            for value in (
                course.get("requirement"),
                course.get("type"),
                course.get("category"),
                course.get("note"),
                section_title,
            )
        )
        for keyword in ("\u4e8c\u9009\u4e00", "\u4efb\u9009", "\u9650\u9009", "\u5fc5\u4fee", "\u8ba1\u5212\u5916", "\u9009\u4fee"):
            if keyword in haystack:
                return keyword
        return "-"

    def plan_course_semester_text(course: dict, section_title: str = "") -> str:
        haystack = " ".join(str(value or "") for value in (course.get("semester"), course.get("term"), course.get("note"), section_title))
        match = re.search(r"(\d{4}\s*[-~]\s*\d{4}\s*(?:\u7b2c)?[12]\s*(?:\u5b66\u671f)?)", haystack)
        if match:
            return match.group(1).replace(" ", "")
        match = re.search(r"(\u7b2c\s*[12]\s*\u5b66\u671f)", haystack)
        return match.group(1).replace(" ", "") if match else "-"

    def plan_course_tooltip(course: dict, section_title: str, status_text_value: str, special: str) -> str:
        return "\n".join(
            [
                course.get("name") or "\u672a\u547d\u540d\u8bfe\u7a0b",
                f"\u8bfe\u7a0b\u4ee3\u7801\uff1a{course.get('code') or '-'}",
                f"\u5b66\u5206\uff1a{format_credit_value(course.get('credit'))}",
                f"\u5b8c\u6210\u5b66\u5206\uff1a{format_credit_value(course.get('completed_credit'))}",
                f"\u6210\u7ee9\uff1a{course.get('score') or '-'}",
                f"\u72b6\u6001\uff1a{status_text_value}",
                f"\u7279\u6b8a\u60c5\u51b5\uff1a{special or '-'}",
                f"\u5f00\u8bfe\u5b66\u671f\uff1a{plan_course_semester_text(course, section_title)}",
                f"\u6240\u5c5e\u6a21\u5757\uff1a{section_title or '-'}",
                f"\u5907\u6ce8\uff1a{course.get('note') or '-'}",
            ]
        )

    def plan_status_info(raw: str) -> tuple[str, str]:
        c = colors()
        text = str(raw or "").strip()
        if any(word in text for word in ("\u5728\u8bfb", "\u4fee\u8bfb", "\u8fdb\u884c")):
            return "\u5728\u8bfb", c["warning"]
        if any(word in text for word in ("\u901a\u8fc7", "\u5df2\u5b8c\u6210", "\u5b8c\u6210", "\u662f")):
            return "\u5df2\u5b8c\u6210", c["success"]
        if any(word in text for word in ("\u5426", "\u7f3a", "\u672a", "\u4e0d")):
            return "\u672a\u5b8c\u6210", c["danger"]
        return text or "\u672a\u5b8c\u6210", c["muted"]

    def signal_dot(color: str):
        return ft.Container(width=10, height=10, bgcolor=color, border_radius=10)

    def build_settings_view():
        c = colors()
        week_text = week_status_text()
        start_hint = "\u9009\u62e9\u7b2c\u4e00\u5468\u7684\u661f\u671f\u4e00\u65e5\u671f"
        return ft.Container(
            content=ft.Column(
                [
                    page_header("\u8bbe\u7f6e", "\u5b66\u671f\u3001\u5916\u89c2\u4e0e\u7f13\u5b58\u7ba1\u7406"),
                    settings_section(
                        "\u5b66\u671f\u65f6\u95f4",
                        [
                            ft.Text(start_hint, size=12, color=c["muted"]),
                            ft.Row(
                                [
                                    semester_year_dropdown,
                                    semester_month_dropdown,
                                    semester_day_dropdown,
                                    ft.Container(
                                        content=ft.Text(week_text, size=14, weight=ft.FontWeight.W_700, color=c["button_text"]),
                                        height=42,
                                        padding=pad_xy(14, 0),
                                        alignment=ft.Alignment(0, 0),
                                        bgcolor=c["soft"],
                                        border=all_border(1, c["border"]),
                                        border_radius=8,
                                    ),
                                    small_button("\u4fdd\u5b58", ft.Icons.SAVE, save_semester_start_setting),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            semester_settings_message,
                        ],
                    ),
                    settings_section(
                        "\u5916\u89c2\u6a21\u5f0f",
                        [
                            ft.Row(
                                [
                                    theme_mode_button("\u767d\u5929", "light"),
                                    theme_mode_button("\u9ed1\u591c", "dark"),
                                    theme_mode_button("\u81ea\u52a8", "auto"),
                                ],
                                spacing=10,
                            ),
                            ft.Text("\u81ea\u52a8\u6a21\u5f0f\u4f1a\u5728 18:00-07:00 \u542f\u7528\u9ed1\u591c\u914d\u8272", size=12, color=c["muted"]),
                            theme_settings_message,
                        ],
                    ),
                    settings_section(
                        "VPN \u4f7f\u7528\u7b56\u7565",
                        [
                            ft.Row(
                                [
                                    vpn_mode_button("\u6253\u5f00\u8f6f\u4ef6\u65f6\u6253\u5f00", "startup"),
                                    vpn_mode_button("\u4f7f\u7528\u5237\u65b0\u529f\u80fd\u65f6\u6253\u5f00", "refresh"),
                                    vpn_mode_button("\u624b\u52a8", "manual"),
                                    manual_vpn_button(),
                                    small_button("\u5168\u90e8\u5237\u65b0", ft.Icons.CLOUD_SYNC, start_fetch_all),
                                ],
                                spacing=10,
                                wrap=True,
                            ),
                            ft.Text("\u79bb\u7ebf\u6a21\u5f0f\u53ea\u8bfb\u53d6\u672c\u5730\u7f13\u5b58\uff0c\u5237\u65b0\u6570\u636e\u9700\u8981\u8054\u7f51\u767b\u5f55\u3002", size=12, color=c["muted"]),
                            vpn_settings_message,
                        ],
                    ),
                    settings_section(
                        "\u542f\u52a8\u9ed8\u8ba4\u9875\u9762",
                        [
                            ft.Row(
                                [
                                    startup_view_button("\u57f9\u517b\u8ba1\u5212", "plan"),
                                    startup_view_button("\u8bfe\u8868", "schedule"),
                                    startup_view_button("\u6210\u7ee9", "grades"),
                                    startup_view_button("\u6211\u7684\u8003\u8bd5", "exams"),
                                    startup_view_button("\u7d20\u62d3\u5206", "second_credits"),
                                    startup_view_button("\u4ec0\u4e48\u90fd\u4e0d\u6253\u5f00", "blank"),
                                ],
                                spacing=10,
                                wrap=True,
                            ),
                            startup_settings_message,
                        ],
                    ),
                    settings_section(
                        "\u7f13\u5b58\u7ba1\u7406",
                        [
                            ft.Text("\u6e05\u7406\u5f53\u524d\u8d26\u53f7\u7684\u57f9\u517b\u8ba1\u5212\u3001\u8bfe\u8868\u3001\u4eca\u65e5\u8bfe\u8868\u3001\u6210\u7ee9\u3001\u8003\u8bd5\u3001\u7d20\u62d3\u5206\u548c\u5b66\u671f\u5217\u8868\u7f13\u5b58\uff0c\u4e0d\u4f1a\u5220\u9664\u5bc6\u7801\u548c\u8bbe\u7f6e\u3002", size=12, color=c["muted"]),
                            danger_button("\u6e05\u7406\u7f13\u5b58", ft.Icons.DELETE_SWEEP, clear_cache_clicked),
                            cache_settings_message,
                        ],
                    ),
                    ft.Text("\u7248\u672c\u53f7 1.0", size=12, color=c["muted"]),
                ],
                spacing=18,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=pad_xy(28, 26),
            expand=True,
            bgcolor=c["content"],
        )

    def build_support_view():
        c = colors()
        return ft.Container(
            content=ft.Column(
                [
                    page_header("\u652f\u6301\u4e0e\u5e2e\u52a9", "\u4f7f\u7528\u8bf4\u660e\u3001\u6570\u636e\u63d0\u9192\u548c\u4f5c\u8005\u4fe1\u606f"),
                    settings_section(
                        "\u4f7f\u7528\u8bf4\u660e",
                        [
                            support_text("\u672c App \u662f\u4e3a\u65e5\u5e38\u67e5\u770b\u8bfe\u8868\u3001\u6210\u7ee9\u3001\u8003\u8bd5\u548c\u57f9\u517b\u8ba1\u5212\u5236\u4f5c\u7684\u8f85\u52a9\u5de5\u5177\uff0c\u65b9\u4fbf\u5feb\u901f\u6d4f\u89c8\u4e2a\u4eba\u5b66\u4e1a\u4fe1\u606f\u3002"),
                            support_text("\u5b83\u4e0d\u662f\u5b66\u6821\u5b98\u65b9\u7cfb\u7edf\uff0c\u4e0d\u4ee3\u66ff\u6821\u5185\u5b98\u7f51\u6559\u52a1\u7cfb\u7edf\u7684\u4efb\u4f55\u901a\u77e5\u3001\u5ba1\u6838\u6216\u6700\u7ec8\u7ed3\u679c\u3002"),
                            support_text("\u5982\u679c App \u4e2d\u7684\u6570\u636e\u4e0e\u5b66\u6821\u5b98\u7f51\u4e0d\u4e00\u81f4\uff0c\u8bf7\u4ee5\u6821\u5185\u5b98\u7f51\u6559\u52a1\u7cfb\u7edf\u663e\u793a\u4e3a\u51c6\u3002"),
                        ],
                    ),
                    settings_section(
                        "\u6570\u636e\u66f4\u65b0",
                        [
                            support_text("\u8bfe\u8868\u3001\u6210\u7ee9\u3001\u8003\u8bd5\u3001\u7d20\u62d3\u5206\u548c\u57f9\u517b\u8ba1\u5212\u90fd\u4f1a\u4f7f\u7528\u672c\u5730\u7f13\u5b58\uff0c\u8fd9\u80fd\u8ba9\u9875\u9762\u6253\u5f00\u66f4\u5feb\u3002"),
                            support_text("\u4e3a\u4e86\u83b7\u53d6\u6700\u65b0\u7ed3\u679c\uff0c\u8bf7\u5c3d\u91cf\u5728\u67e5\u770b\u524d\u70b9\u51fb\u5bf9\u5e94\u9875\u9762\u7684\u5237\u65b0\u6309\u94ae\u3002"),
                            support_text("\u5c24\u5176\u662f\u9009\u8bfe\u3001\u6210\u7ee9\u53d1\u5e03\u3001\u8003\u8bd5\u5b89\u6392\u8c03\u6574\u7b49\u65f6\u95f4\u70b9\uff0c\u5efa\u8bae\u4ee5\u5b98\u7f51\u590d\u6838\u4e00\u6b21\u3002"),
                        ],
                    ),
                    settings_section(
                        "\u5e38\u89c1\u60c5\u51b5",
                        [
                            support_text("\u5982\u679c\u5237\u65b0\u5931\u8d25\uff0c\u53ef\u5148\u68c0\u67e5 VPN \u72b6\u6001\u3001\u6821\u56ed\u7f51\u7edc\u8fde\u901a\u6027\u548c\u8d26\u53f7\u5bc6\u7801\u662f\u5426\u6b63\u786e\u3002"),
                            support_text("\u5982\u679c\u67d0\u4e2a\u5b66\u671f\u6682\u65e0\u6570\u636e\uff0c\u53ef\u80fd\u662f\u5b98\u7f51\u672a\u516c\u5e03\u3001\u5b66\u671f\u5c1a\u672a\u5f00\u653e\uff0c\u6216\u8005\u8be5\u9879\u672c\u786e\u5b9e\u6ca1\u6709\u5b89\u6392\u3002"),
                            support_text("\u79bb\u7ebf\u6a21\u5f0f\u53ea\u9002\u5408\u4e34\u65f6\u67e5\u770b\u5df2\u7f13\u5b58\u7684\u6570\u636e\uff0c\u4e0d\u4f1a\u4ece\u5b98\u7f51\u62c9\u53d6\u6700\u65b0\u5185\u5bb9\u3002"),
                        ],
                    ),
                    settings_section(
                        "\u5b66\u6821\u7f51\u7ad9",
                        [
                            ft.Text(
                                "\u4e0b\u9762\u7684\u6309\u94ae\u4f1a\u7528\u7cfb\u7edf\u9ed8\u8ba4\u6d4f\u89c8\u5668\u6253\u5f00\u94fe\u63a5\u3002App \u5185\u90e8\u7684 VPN \u53ea\u4fdd\u8bc1 App \u81ea\u5df1\u8bf7\u6c42\u80fd\u8d70\u4ee3\u7406\uff0c\u4e0d\u4f1a\u81ea\u52a8\u63a5\u7ba1\u6d4f\u89c8\u5668\u3002",
                                size=12,
                                color=c["muted"],
                            ),
                            ft.Text(
                                "\u8bbf\u95ee\u6559\u52a1\u7cfb\u7edf\u6216\u5145\u7535\u8d39\u7b49\u5185\u7f51\u7ad9\u70b9\u65f6\uff0c\u8bf7\u786e\u8ba4\u6d4f\u89c8\u5668\u62e5\u6709\u53ef\u8fde\u63a5 VPN \u7684\u4ee3\u7406\u63d2\u4ef6\uff0c\u4f8b\u5982 SwitchyOmega\uff1b\u5e76\u5c06\u60c5\u666f\u6a21\u5f0f\u5207\u5230 SOCKS5 127.0.0.1:1080\u3002",
                                size=12,
                                color=c["muted"],
                            ),
                            school_website_row("\u5b66\u6821\u5b98\u7f51", "\u5b66\u6821\u516c\u5f00\u4e3b\u9875\uff0c\u6821\u56ed\u65b0\u95fb\u548c\u516c\u5171\u4fe1\u606f\u5165\u53e3\u3002", "https://www.shiep.edu.cn/"),
                            school_website_row("\u6559\u52a1\u7cfb\u7edf", "\u5b66\u6821\u5b98\u65b9\u6559\u52a1\u7cfb\u7edf\uff0c\u6700\u7ec8\u8bfe\u8868\u3001\u6210\u7ee9\u548c\u5ba1\u6838\u7ed3\u679c\u4ee5\u8fd9\u91cc\u4e3a\u51c6\u3002", "https://jw.shiep.edu.cn/eams/index.action"),
                            school_website_row("\u5145\u7535\u8d39\u7f51\u7ad9", "\u6821\u5185\u5145\u7535\u8d39\u5165\u53e3\uff0c\u4ec5\u5185\u7f51\u6216\u6d4f\u89c8\u5668 VPN \u4ee3\u7406\u53ef\u8bbf\u95ee\u3002", "http://10.50.2.206"),
                            school_website_row("\u4e0a\u7535\u4e91\u76d8", "\u5b66\u6821\u4e91\u76d8\u6587\u4ef6\u5165\u53e3\uff0c\u7528\u4e8e\u67e5\u770b\u548c\u7ba1\u7406\u6821\u5185\u6587\u6863\u3002", "https://pan.shiep.edu.cn/#/home/documents/all"),
                            website_settings_message,
                        ],
                    ),
                    ft.Container(expand=True),
                    support_author_block(),
                ],
                spacing=18,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=pad_xy(28, 26),
            expand=True,
            bgcolor=c["content"],
        )

    def support_text(text: str):
        return ft.Text(text, size=13, color=colors()["muted"], selectable=True)

    def local_image_bytes(filename: str) -> bytes:
        path = Path(__file__).resolve().parent / filename
        try:
            return path.read_bytes()
        except OSError:
            return b""

    def show_tip_code_dialog(_=None):
        tip_code = local_image_bytes("509e691a73ef7ce9cc08e7dbe27b2864.jpg")
        if not tip_code:
            return
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("\u652f\u6301\u6a58\u732b", size=16, weight=ft.FontWeight.W_700),
            content=ft.Container(
                content=ft.Image(src=tip_code, width=360, height=360, fit=ft.BoxFit.CONTAIN, border_radius=8),
                width=370,
                height=370,
                alignment=ft.Alignment(0, 0),
            ),
            actions=[ft.Button("\u5173\u95ed", on_click=lambda _: close_dialog(dialog))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def close_dialog(dialog):
        dialog.open = False
        page.update()

    def support_author_block():
        c = colors()
        avatar = local_image_bytes("Image_1763040610208.jpg")
        tip_code = local_image_bytes("509e691a73ef7ce9cc08e7dbe27b2864.jpg")
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Image(src=avatar, width=54, height=54, fit=ft.BoxFit.COVER, border_radius=27) if avatar else ft.Icon(ft.Icons.PERSON, size=26, color=c["muted"]),
                        width=58,
                        height=58,
                        alignment=ft.Alignment(0, 0),
                        bgcolor=c["soft"],
                        border=all_border(1, c["border"]),
                        border_radius=29,
                    ),
                    ft.Column(
                        [
                            ft.Text("\u6a58\u732bTabby", size=14, weight=ft.FontWeight.W_700, color=c["text"]),
                            ft.Text("\u505a\u4e86\u4e00\u4e2a\u66f4\u987a\u624b\u7684\u67e5\u8be2\u5c0f\u5de5\u5177\u3002\u5982\u679c\u89c9\u5f97\u7701\u4e86\u4e00\u70b9\u65f6\u95f4\uff0c\u53ef\u4ee5\u968f\u624b\u9001\u70b9 token\u3002", size=12, color=c["muted"], max_lines=2),
                        ],
                        spacing=3,
                        expand=True,
                    ),
                    ft.Column(
                        [
                            ft.Text("\u652f\u6301\u6a58\u732b", size=12, weight=ft.FontWeight.W_600, color=c["muted"]),
                            ft.GestureDetector(
                                content=ft.Container(
                                    content=ft.Image(src=tip_code, width=122, height=122, fit=ft.BoxFit.CONTAIN, border_radius=6) if tip_code else ft.Text("-", size=12, color=c["muted"]),
                                    width=126,
                                    height=126,
                                    padding=pad_xy(2, 2),
                                    bgcolor=c["card"],
                                    border=all_border(1, c["border"]),
                                    border_radius=8,
                                ),
                                on_tap=show_tip_code_dialog,
                                on_double_tap=show_tip_code_dialog,
                                tooltip="\u70b9\u51fb\u67e5\u770b\u5927\u56fe",
                            ),
                            ft.Text("\u70b9\u51fb\u6216\u53cc\u51fb\u653e\u5927", size=10, color=c["muted2"]),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=pad_xy(14, 12),
            bgcolor=c["soft"],
            border=all_border(1, c["border"]),
            border_radius=8,
        )

    def settings_section(title: str, controls: list[ft.Control]):
        c = colors()
        return ft.Container(
            content=ft.Column(
                [ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=c["text"]), *controls],
                spacing=12,
            ),
            padding=pad_xy(18, 16),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=8,
        )

    def open_school_website(url: str):
        try:
            webbrowser.open(url, new=2)
            website_settings_message.value = f"\u5df2\u5728\u6d4f\u89c8\u5668\u6253\u5f00\uff1a{url}"
            website_settings_message.color = colors()["success"]
        except Exception as ex:
            website_settings_message.value = f"\u6253\u5f00\u5931\u8d25\uff1a{ex}"
            website_settings_message.color = colors()["danger"]
        page.update()

    def school_website_row(title: str, description: str, url: str):
        c = colors()
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(title, size=14, weight=ft.FontWeight.W_700, color=c["text"]),
                                ft.Text(description, size=12, color=c["muted"], max_lines=2),
                                ft.Text(url, size=11, color=c["muted2"], max_lines=1),
                            ],
                            spacing=3,
                        ),
                        expand=True,
                    ),
                    small_button("\u6253\u5f00", ft.Icons.OPEN_IN_BROWSER, lambda _, target=url: open_school_website(target)),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=pad_xy(12, 10),
            bgcolor=c["soft"],
            border=all_border(1, c["border"]),
            border_radius=8,
        )

    def theme_mode_button(label: str, mode: str):
        active = selected_theme_mode == mode
        c = colors()
        return ft.Button(
            label,
            height=40,
            style=ft.ButtonStyle(
                color=c["text"] if active else c["muted"],
                bgcolor=c["active"] if active else c["button_bg"],
                side=ft.BorderSide(1, c["active_border"] if active else c["border"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=lambda _: set_theme_mode(mode),
        )

    def vpn_mode_button(label: str, mode: str):
        active = selected_vpn_mode == mode
        c = colors()
        return ft.Button(
            label,
            height=40,
            style=ft.ButtonStyle(
                color=c["text"] if active else c["muted"],
                bgcolor=c["active"] if active else c["button_bg"],
                side=ft.BorderSide(1, c["active_border"] if active else c["border"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=lambda _: set_vpn_mode(mode),
        )

    def manual_vpn_button():
        c = colors()
        running = vpn_is_running()
        label = "\u8fde\u63a5\u4e2d..." if vpn_manual_loading else ("\u5173\u95ed VPN" if running else "\u5f00\u542f VPN")
        icon = ft.Icons.POWER_SETTINGS_NEW if running else ft.Icons.PLAY_ARROW
        return ft.Button(
            content=ft.Row([ft.Icon(icon, size=16), ft.Text(label, size=13)], spacing=6),
            height=40,
            disabled=vpn_manual_loading,
            style=ft.ButtonStyle(
                color=c["danger"] if running else c["button_text"],
                bgcolor=c["button_bg"],
                side=ft.BorderSide(1, c["danger"] if running else c["border"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=toggle_manual_vpn,
        )

    def startup_view_button(label: str, view_name: str):
        active = selected_startup_view == view_name
        c = colors()
        return ft.Button(
            label,
            height=40,
            style=ft.ButtonStyle(
                color=c["text"] if active else c["muted"],
                bgcolor=c["active"] if active else c["button_bg"],
                side=ft.BorderSide(1, c["active_border"] if active else c["border"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=lambda _: set_startup_view(view_name),
        )

    def danger_button(label: str, icon, on_click):
        c = colors()
        return ft.Button(
            content=ft.Row([ft.Icon(icon, size=16), ft.Text(label, size=13)], spacing=6),
            height=40,
            style=ft.ButtonStyle(
                color=c["danger"],
                bgcolor=c["button_bg"],
                side=ft.BorderSide(1, c["danger"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=on_click,
        )

    def save_semester_start_setting(_=None):
        nonlocal semester_start_date
        value = selected_start_date_value()
        if value:
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                semester_settings_message.value = "\u8bf7\u9009\u62e9\u6709\u6548\u65e5\u671f"
                semester_settings_message.color = colors()["danger"]
                page.update()
                return
            if parsed.weekday() != 0:
                semester_settings_message.value = "\u8bf7\u9009\u62e9\u7b2c\u4e00\u5468\u7684\u661f\u671f\u4e00\u65e5\u671f"
                semester_settings_message.color = colors()["danger"]
                page.update()
                return
        semester_start_date = value
        sync_semester_date_dropdowns()
        apply_auto_week()
        save_current_settings()
        semester_settings_message.value = "\u5df2\u4fdd\u5b58\u5f00\u5b66\u65f6\u95f4"
        semester_settings_message.color = colors()["success"]
        render_app()

    def set_theme_mode(mode: str):
        nonlocal selected_theme_mode
        selected_theme_mode = mode
        save_current_settings()
        theme_settings_message.value = "\u5916\u89c2\u6a21\u5f0f\u5df2\u66f4\u65b0"
        theme_settings_message.color = colors()["success"]
        render_app()

    def set_vpn_mode(mode: str):
        nonlocal selected_vpn_mode, vpn
        selected_vpn_mode = normalized_vpn_mode(mode)
        vpn_switch.value = selected_vpn_mode == "startup"
        on_vpn_toggle(None)
        save_current_settings()
        vpn_settings_message.value = "VPN \u4f7f\u7528\u7b56\u7565\u5df2\u66f4\u65b0"
        vpn_settings_message.color = colors()["success"]
        render_app()

    def set_startup_view(view_name: str):
        nonlocal selected_startup_view
        selected_startup_view = normalized_startup_view(view_name)
        save_current_settings()
        startup_settings_message.value = "\u542f\u52a8\u9ed8\u8ba4\u9875\u9762\u5df2\u66f4\u65b0"
        startup_settings_message.color = colors()["success"]
        render_app()

    def clear_cache_clicked(_=None):
        nonlocal plan_data, schedule_items, today_schedule_items, grade_items, exam_items, second_credit_items, semester_items
        nonlocal plan_updated_at, schedule_updated_at, today_schedule_updated_at, grades_updated_at, exams_updated_at, second_credits_updated_at, semesters_updated_at
        nonlocal plan_error, schedule_error, today_schedule_error, grades_error, exams_error, second_credits_error
        nonlocal plan_loading, schedule_loading, today_schedule_loading, grades_loading, exams_loading, second_credits_loading
        clear_account_cache(active_account)
        plan_data = {}
        schedule_items = []
        today_schedule_items = []
        grade_items = []
        exam_items = []
        second_credit_items = []
        semester_items = []
        plan_loading = False
        schedule_loading = False
        today_schedule_loading = False
        grades_loading = False
        exams_loading = False
        second_credits_loading = False
        plan_error = ""
        schedule_error = ""
        today_schedule_error = ""
        grades_error = ""
        exams_error = ""
        second_credits_error = ""
        plan_updated_at = ""
        schedule_updated_at = ""
        today_schedule_updated_at = ""
        grades_updated_at = ""
        exams_updated_at = ""
        second_credits_updated_at = ""
        semesters_updated_at = ""
        cache_settings_message.value = "\u5df2\u6e05\u7406\u5f53\u524d\u8d26\u53f7\u7f13\u5b58"
        cache_settings_message.color = colors()["success"]
        render_app()

    def page_header(title: str, subtitle: str, actions: list[ft.Control] | None = None):
        c = colors()
        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(title, size=24, weight=ft.FontWeight.W_700, color=c["text"]),
                        ft.Text(subtitle, size=13, color=c["muted"]),
                    ],
                    spacing=4,
                    expand=True,
                ),
                *(actions or []),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def build_schedule_view():
        semester_options = [ft.dropdown.Option(CURRENT_SEMESTER, "\u5f53\u524d\u5b66\u671f")]
        semester_options.extend(
            ft.dropdown.Option(str(item.get("id")), item.get("name") or str(item.get("id")))
            for item in semester_items
            if item.get("id")
        )
        week_dropdown = ft.Dropdown(
            width=118,
            height=42,
            value=selected_week,
            options=[ft.dropdown.Option(str(i), f"\u7b2c {i} \u5468") for i in range(1, 21)],
            on_select=on_week_change,
        )
        semester_dropdown = ft.Dropdown(
            width=220,
            height=42,
            value=selected_semester,
            options=semester_options,
            on_select=on_semester_change,
        )

        if schedule_mode == "today":
            if today_schedule_loading:
                body = loading_view("\u6b63\u5728\u52a0\u8f7d\u4eca\u65e5\u8bfe\u8868")
            elif today_schedule_error:
                body = error_view(today_schedule_error, start_fetch_today_schedule)
            else:
                body = today_schedule_list()
            subtitle = f"\u4eca\u65e5\u8bfe\u7a0b\u5b89\u6392 | {compact_updated_at('\u4eca\u65e5\u8bfe\u8868\u66f4\u65b0', today_schedule_updated_at)}"
            actions = [
                schedule_mode_button("\u5168\u90e8\u8bfe\u8868", "all"),
                schedule_mode_button("\u4eca\u65e5\u8bfe\u8868", "today"),
                small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_today_schedule),
            ]
        elif schedule_loading:
            body = loading_view("\u6b63\u5728\u52a0\u8f7d\u8bfe\u8868")
            subtitle = f"\u6309\u5b66\u671f/\u5468\u67e5\u770b\u8bfe\u7a0b\u5b89\u6392 | {compact_updated_at('\u8bfe\u8868\u66f4\u65b0', schedule_updated_at)} | {compact_updated_at('\u5b66\u671f\u5217\u8868', semesters_updated_at)}"
            actions = [
                schedule_mode_button("\u5168\u90e8\u8bfe\u8868", "all"),
                schedule_mode_button("\u4eca\u65e5\u8bfe\u8868", "today"),
                semester_dropdown,
                week_dropdown,
                small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_schedule),
            ]
        elif schedule_error:
            body = error_view(schedule_error, start_fetch_schedule)
            subtitle = f"\u6309\u5b66\u671f/\u5468\u67e5\u770b\u8bfe\u7a0b\u5b89\u6392 | {compact_updated_at('\u8bfe\u8868\u66f4\u65b0', schedule_updated_at)} | {compact_updated_at('\u5b66\u671f\u5217\u8868', semesters_updated_at)}"
            actions = [
                schedule_mode_button("\u5168\u90e8\u8bfe\u8868", "all"),
                schedule_mode_button("\u4eca\u65e5\u8bfe\u8868", "today"),
                semester_dropdown,
                week_dropdown,
                small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_schedule),
            ]
        else:
            body = schedule_grid()
            subtitle = f"\u6309\u5b66\u671f/\u5468\u67e5\u770b\u8bfe\u7a0b\u5b89\u6392 | {compact_updated_at('\u8bfe\u8868\u66f4\u65b0', schedule_updated_at)} | {compact_updated_at('\u5b66\u671f\u5217\u8868', semesters_updated_at)}"
            actions = [
                schedule_mode_button("\u5168\u90e8\u8bfe\u8868", "all"),
                schedule_mode_button("\u4eca\u65e5\u8bfe\u8868", "today"),
                semester_dropdown,
                week_dropdown,
                small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_schedule),
            ]

        return ft.Container(
            content=ft.Column(
                [
                    page_header(
                        "\u8bfe\u8868",
                        subtitle,
                        actions,
                    ),
                    body,
                ],
                spacing=18,
                expand=True,
            ),
            padding=pad_xy(28, 26),
            expand=True,
        )

    def on_week_change(e):
        nonlocal selected_week
        selected_week = e.control.value
        render_app()

    def on_semester_change(e):
        nonlocal selected_semester, schedule_items, schedule_loading, schedule_error
        selected_semester = e.control.value
        schedule_loading = False
        schedule_error = ""
        load_schedule_cache()
        render_app()
        if not schedule_items:
            start_fetch_schedule()

    def set_schedule_mode(mode: str):
        nonlocal schedule_mode
        schedule_mode = mode
        render_app()
        if mode == "today" and not today_schedule_items and not today_schedule_loading and not today_schedule_updated_at:
            start_fetch_today_schedule()

    def schedule_mode_button(label: str, mode: str):
        c = colors()
        active = schedule_mode == mode
        return ft.Button(
            label,
            height=40,
            style=ft.ButtonStyle(
                color=c["text"] if active else c["muted"],
                bgcolor=c["active"] if active else c["button_bg"],
                side=ft.BorderSide(1, c["active_border"] if active else c["border"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=lambda _: set_schedule_mode(mode),
        )

    def schedule_grid():
        c_theme = colors()
        slot_width = 74
        day_width = 128
        slot_height = 60
        gap = 6
        selected = int(selected_week)
        visible_courses = [
            item for item in schedule_items
            if not item.get("weeks") or selected in item.get("weeks", [])
        ]
        by_day_start: dict[tuple[int, int], list[dict]] = {}
        floating = []
        for course in visible_courses:
            day = int(course.get("day_of_week") or 0)
            start = int(course.get("start_slot") or 0)
            end = int(course.get("end_slot") or start or 0)
            if day < 1 or day > 7 or start < 1:
                floating.append(course)
                continue
            course["_ui_start"] = max(1, start)
            course["_ui_end"] = min(MAX_SLOT, max(start, end))
            by_day_start.setdefault((day, course["_ui_start"]), []).append(course)

        table = ft.Row(
            [
                ft.Column(
                    [grid_header("", slot_width)]
                    + [slot_cell(slot, slot_width, slot_height) for slot in SLOTS],
                    spacing=gap,
                ),
                *[
                    schedule_day_column(day_index, by_day_start, day_width, slot_height, gap)
                    for day_index in range(1, 8)
                ],
            ],
            spacing=8,
        )
        table_width = slot_width + 7 * day_width + 7 * 8

        footer = ft.Text(
            f"\u672c\u5468 {len({c.get('name') for c in visible_courses})} \u95e8\u8bfe"
            + (f" | {len(floating)} \u95e8\u672a\u6392\u56fa\u5b9a\u65f6\u95f4" if floating else ""),
            size=12,
            color=c_theme["muted"],
        )
        return ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text("\u5de6\u53f3\u6ed1\u52a8\u67e5\u770b\u5b8c\u6574\u8bfe\u8868", size=12, color=c_theme["muted"]),
                                        table,
                                    ],
                                    spacing=8,
                                    scroll=ft.ScrollMode.AUTO,
                                    expand=True,
                                ),
                                width=table_width,
                                expand=False,
                            ),
                        ],
                        scroll=ft.ScrollMode.ALWAYS,
                        expand=True,
                    ),
                    padding=pad_xy(12, 10),
                    bgcolor=c_theme["soft"],
                    border=all_border(1, c_theme["border"]),
                    border_radius=8,
                    expand=True,
                ),
                footer,
            ],
            spacing=10,
            expand=True,
        )

    def today_schedule_list():
        if not today_schedule_items:
            return empty_view("\u4eca\u65e5\u6682\u65e0\u8bfe\u7a0b")
        rows = [today_course_row(course) for course in today_schedule_items]
        return ft.ListView(rows, spacing=10, expand=True, padding=pad(right=8))

    def today_course_row(course: dict):
        c = colors()
        name = course.get("name") or course.get("course_name") or ""
        slot = course.get("slot_text") or format_slot_range(course)
        location = course.get("location") or "-"
        teacher = course.get("teacher") or "-"
        campus = course.get("campus") or "-"
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=6, height=62, bgcolor=course_color(name), border_radius=6),
                    ft.Container(
                        content=ft.Text(
                            name,
                            size=15,
                            weight=ft.FontWeight.W_600,
                            color=c["text"],
                            max_lines=1,
                        ),
                        height=62,
                        alignment=ft.Alignment(-1, 0),
                        expand=True,
                    ),
                    metric_text("\u8282\u6b21", slot),
                    metric_text("\u6559\u5ba4", location),
                    metric_text("\u6559\u5e08", teacher),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=82,
            padding=pad_xy(14, 0),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=8,
            shadow=ft.BoxShadow(blur_radius=10, spread_radius=0, color=c["shadow"], offset=ft.Offset(0, 2)),
            tooltip="\n".join(
                [
                    name,
                    f"\u65e5\u671f\uff1a{course.get('date') or '-'}",
                    f"\u8282\u6b21\uff1a{slot}",
                    f"\u6559\u5ba4\uff1a{location}",
                    f"\u6821\u533a\uff1a{campus}",
                    f"\u6559\u5e08\uff1a{teacher}",
                ]
            ),
        )

    def format_slot_range(course: dict):
        start = course.get("start_slot") or ""
        end = course.get("end_slot") or start
        return f"{start}-{end}" if start and end and start != end else str(start or "-")

    def schedule_day_column(day_index: int, by_day_start: dict, width: int, slot_height: int, gap: int):
        controls = [grid_header(DAYS[day_index - 1], width)]
        slot = 1
        while slot <= MAX_SLOT:
            courses = by_day_start.get((day_index, slot), [])
            if courses:
                main_course = courses[0]
                end = int(main_course.get("_ui_end") or slot)
                duration = max(1, min(MAX_SLOT, end) - slot + 1)
                controls.append(course_block(courses, duration, width, slot_height, gap))
                slot += duration
            else:
                controls.append(empty_slot(width, slot_height))
                slot += 1
        return ft.Column(controls, spacing=gap)

    def grid_header(text: str, width: int):
        c = colors()
        return ft.Container(
            content=ft.Text(text, size=12, weight=ft.FontWeight.W_600, color=c["muted"]),
            width=width,
            height=30,
            alignment=ft.Alignment(0, 0),
        )

    def slot_cell(slot: int, width: int, height: int):
        c = colors()
        start_time, end_time = SLOT_TIMES[slot - 1].split("-")
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(str(slot), size=13, weight=ft.FontWeight.W_600, color=c["muted"]),
                    ft.Column(
                        [
                            ft.Text(start_time, size=9, color=c["muted"]),
                            ft.Text(end_time, size=9, color=c["muted2"]),
                        ],
                        spacing=0,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=width,
            height=height,
            alignment=ft.Alignment(0, 0),
            bgcolor=c["soft"],
            border_radius=6,
            border=all_border(1, c["grid_border"]),
        )

    def empty_slot(width: int, height: int):
        c = colors()
        return ft.Container(
            width=width,
            height=height,
            bgcolor=c["card"],
            border_radius=6,
            border=all_border(1, c["grid_border"]),
        )

    def course_block(courses: list[dict], duration: int, width: int, slot_height: int, gap: int):
        course = courses[0]
        color = course_color(course.get("name", ""))
        location = course.get("location", "")
        week_text = course.get("week_text") or format_course_weeks(course)
        extra = f" +{len(courses) - 1}" if len(courses) > 1 else ""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        f"{course.get('name', '')}{extra}",
                        size=12,
                        weight=ft.FontWeight.W_700,
                        color="#253633",
                        max_lines=2,
                    ),
                    ft.Text(location, size=10, color="#44534F", max_lines=1),
                    ft.Text(week_text, size=10, color="#44534F", max_lines=1),
                ],
                spacing=2,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            width=width,
            height=duration * slot_height + (duration - 1) * gap,
            padding=pad_xy(10, 6),
            bgcolor=color,
            border_radius=7,
            tooltip=course_tooltip(course),
        )
    def course_tooltip(course: dict):
        week_text = course.get("week_text") or format_course_weeks(course)
        return "\n".join(
            [
                course.get("name", ""),
                f"\u5730\u70b9\uff1a{course.get('location', '') or '-'}",
                f"\u6559\u5e08\uff1a{course.get('teacher', '') or '-'}",
                f"\u8282\u6b21\uff1a{course.get('start_slot', '-')}-{course.get('end_slot', '-')}",
                f"\u5468\u6b21\uff1a{week_text}",
            ]
        )

    def format_course_weeks(course: dict):
        weeks = course.get("weeks") or []
        if not weeks:
            return "\u5168\u5468"
        ordered = sorted(set(int(week) for week in weeks))
        if len(ordered) > 1 and all(week % 2 == 1 for week in ordered):
            return f"{ordered[0]}-{ordered[-1]} \u5355\u5468"
        if len(ordered) > 1 and all(week % 2 == 0 for week in ordered):
            return f"{ordered[0]}-{ordered[-1]} \u53cc\u5468"
        if ordered == list(range(ordered[0], ordered[-1] + 1)):
            return f"{ordered[0]}-{ordered[-1]} \u5468"
        return ",".join(str(week) for week in ordered)

    def build_grades_view():
        semester_options = [ft.dropdown.Option(ALL_SEMESTERS, "\u5168\u90e8\u5b66\u671f")]
        semester_options.extend(
            ft.dropdown.Option(str(item.get("id")), item.get("name") or str(item.get("id")))
            for item in semester_items
            if item.get("id")
        )
        dropdown = ft.Dropdown(
            width=220,
            height=42,
            value=selected_grade_semester,
            options=semester_options,
            on_select=on_grade_semester_change,
        )

        if grades_loading:
            body = loading_view("\u6b63\u5728\u52a0\u8f7d\u6210\u7ee9")
        elif grades_error:
            body = error_view(grades_error, start_fetch_grades)
        else:
            body = grade_list()

        return ft.Container(
            content=ft.Column(
                [
                    page_header(
                        "\u6210\u7ee9\u5355",
                        f"\u8bfe\u7a0b\u3001\u5b66\u5206\u3001\u7efc\u5408\u5206\u6570\u4e0e\u7ee9\u70b9 | {format_updated_at(grades_updated_at)}",
                        [dropdown, small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_grades)],
                    ),
                    body,
                ],
                spacing=18,
                expand=True,
            ),
            padding=pad_xy(28, 26),
            expand=True,
        )

    def on_grade_semester_change(e):
        nonlocal selected_grade_semester, grades_error, grades_loading
        selected_grade_semester = e.control.value
        grades_loading = False
        grades_error = ""
        load_grade_cache()
        render_app()
        if not grade_items:
            start_fetch_grades()

    def build_exams_view():
        semester_options = [ft.dropdown.Option(CURRENT_SEMESTER, "\u5f53\u524d\u5b66\u671f")]
        semester_options.extend(
            ft.dropdown.Option(str(item.get("id")), item.get("name") or str(item.get("id")))
            for item in semester_items
            if item.get("id")
        )
        dropdown = ft.Dropdown(
            width=220,
            height=42,
            value=selected_exam_semester,
            options=semester_options,
            on_select=on_exam_semester_change,
        )

        if exams_loading:
            body = loading_view("\u6b63\u5728\u52a0\u8f7d\u8003\u8bd5")
        elif exams_error:
            body = error_view(exams_error, start_fetch_exams)
        else:
            body = exam_list()

        return ft.Container(
            content=ft.Column(
                [
                    page_header(
                        "\u6211\u7684\u8003\u8bd5",
                        f"\u8003\u8bd5\u5b89\u6392 | {format_updated_at(exams_updated_at)}",
                        [dropdown, small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_exams)],
                    ),
                    body,
                ],
                spacing=18,
                expand=True,
            ),
            padding=pad_xy(28, 26),
            expand=True,
        )

    def on_exam_semester_change(e):
        nonlocal selected_exam_semester, exams_error, exams_loading
        selected_exam_semester = e.control.value
        exams_loading = False
        exams_error = ""
        load_exam_cache()
        render_app()
        if not exam_items and not exams_updated_at:
            start_fetch_exams()

    def build_second_credits_view():
        if second_credits_loading:
            body = loading_view("\u6b63\u5728\u52a0\u8f7d\u7d20\u62d3\u5206")
        elif second_credits_error:
            body = error_view(second_credits_error, start_fetch_second_credits)
        else:
            body = second_credit_list()

        return ft.Container(
            content=ft.Column(
                [
                    page_header(
                        "\u7d20\u62d3\u5206",
                        f"\u7b2c\u4e8c\u8bfe\u5802\u7d20\u8d28\u62d3\u5c55\u5b66\u5206 | {format_updated_at(second_credits_updated_at)}",
                        [small_button("\u5237\u65b0", ft.Icons.REFRESH, start_fetch_second_credits)],
                    ),
                    body,
                ],
                spacing=18,
                expand=True,
            ),
            padding=pad_xy(28, 26),
            expand=True,
        )

    def second_credit_list():
        if not second_credit_items:
            return empty_view("\u6682\u65e0\u7d20\u62d3\u5206\u6570\u636e")
        rows = [second_credit_row(item) for item in second_credit_items]
        return ft.Column(
            [
                second_credit_summary_bar(),
                ft.ListView(rows, spacing=10, expand=True, padding=pad(right=8)),
            ],
            spacing=12,
            expand=True,
        )

    def item_text(item: dict, *keys: str, default: str = "") -> str:
        for key in keys:
            value = item.get(key)
            if value is None or value == "":
                continue
            return str(value).strip()
        return default

    def second_credit_summary_bar():
        earned = 0.0
        for item in second_credit_items:
            status, _, _ = second_credit_status_info(item)
            if status != "\u5df2\u901a\u8fc7":
                continue
            earned += item_credit_value(item)

        return ft.Container(
            content=ft.Row(
                [
                    second_credit_summary_card(earned),
                    ft.Text("\u53ea\u7edf\u8ba1\u5df2\u901a\u8fc7\u6761\u76ee\uff0c\u5f85\u5ba1\u6838\u548c\u672a\u901a\u8fc7\u4e0d\u8ba1\u5165\u5df2\u83b7\u5f97\u5b66\u5206", size=12, color=colors()["muted"]),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=pad_xy(12, 10),
            bgcolor=colors()["soft"],
            border=all_border(1, colors()["border"]),
            border_radius=8,
        )

    def second_credit_summary_card(earned: float):
        c = colors()
        enough = earned >= SECOND_CREDIT_REQUIRED
        progress = min(1.0, earned / SECOND_CREDIT_REQUIRED) if SECOND_CREDIT_REQUIRED > 0 else 0
        color = c["success"] if enough else c["button_text"]
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("\u7d20\u62d3\u5206\u603b\u5206", size=12, weight=ft.FontWeight.W_600, color=c["text"], max_lines=1),
                    ft.Row(
                        [
                            ft.Text(f"{earned:g}", size=20, weight=ft.FontWeight.W_700, color=color),
                            ft.Text(f"/ {SECOND_CREDIT_REQUIRED:g}", size=13, color=c["muted"]),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.ProgressBar(value=progress, height=4, color=color, bgcolor=c["border"]),
                ],
                spacing=6,
            ),
            width=230,
            height=84,
            padding=pad_xy(12, 10),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=8,
        )

    def item_credit_value(item: dict) -> float:
        try:
            return float(item.get("credit") or item.get("credits") or item.get("score") or item.get("point") or 0)
        except (TypeError, ValueError):
            match = re.search(r"-?\d+(?:\.\d+)?", str(item.get("credit") or ""))
            return float(match.group(0)) if match else 0.0

    def second_credit_row(item: dict):
        c = colors()
        name = item_text(item, "name", "project_name", "activity_name", "course_name", "title", default="\u672a\u547d\u540d\u9879\u76ee")
        category = item_text(item, "category", "type", "module", "kind", default="-")
        subcategory = item_text(item, "subcategory", "subclass", "sub_type", default="-")
        semester = item_text(item, "semester", "term", default="-")
        label1 = item_text(item, "label1", "tag1", default="-")
        label2 = item_text(item, "label2", "tag2", default="-")
        apply_type = item_text(item, "apply_type", "applyType", default="-")
        credit = f"{item_credit_value(item):g}"
        status_text_value, status_color, status_bg = second_credit_status_info(item)
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=6, height=78, bgcolor=course_color(name), border_radius=6),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    name,
                                    size=15,
                                    weight=ft.FontWeight.W_700,
                                    color=c["text"],
                                    max_lines=1,
                                ),
                                ft.Text(category, size=12, color=c["muted"], max_lines=1),
                                ft.Text(
                                    f"\u5b50\u7c7b\uff1a{subcategory} | \u6807\u7b7e\uff1a{label1} / {label2} | \u7533\u8bf7\uff1a{apply_type} | \u5b66\u671f\uff1a{semester}",
                                    size=11,
                                    color=c["muted2"],
                                    max_lines=1,
                                ),
                            ],
                            spacing=3,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        height=78,
                        alignment=ft.Alignment(-1, 0),
                        expand=True,
                    ),
                    metric_text("\u5b66\u5206", credit),
                    status_badge(status_text_value, status_color, status_bg),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=98,
            padding=pad_xy(14, 0),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=8,
            shadow=ft.BoxShadow(blur_radius=10, spread_radius=0, color=c["shadow"], offset=ft.Offset(0, 2)),
            tooltip=second_credit_tooltip(item, name, category, subcategory, credit, semester, label1, label2, apply_type, status_text_value),
        )

    def second_credit_status_info(item: dict) -> tuple[str, str, str]:
        raw_status = item_text(item, "status", "state", "audit_status", "result", default="\u672a\u77e5")
        if any(word in raw_status for word in ("\u672a\u901a\u8fc7", "\u9000\u56de", "\u9a73\u56de", "\u5931\u8d25")):
            return "\u672a\u901a\u8fc7", "#C33B3B", "#FCEDED"
        if any(word in raw_status for word in ("\u5f85", "\u5ba1\u6838\u4e2d", "\u7533\u8bf7", "\u5904\u7406\u4e2d", "\u672a\u63d0\u4ea4")):
            return "\u5f85\u5ba1\u6838", "#B98600", "#FFF5D6"
        if any(word in raw_status for word in ("\u901a\u8fc7", "\u5b8c\u6210", "\u5df2\u8ba4\u5b9a", "\u5df2\u5ba1\u6838")):
            return "\u5df2\u901a\u8fc7", "#2F8F6B", "#EAF7F1"
        return raw_status, "#7B8783", "#F7FAF9"

    def second_credit_tooltip(
        item: dict,
        name: str,
        category: str,
        subcategory: str,
        credit: str,
        semester: str,
        label1: str,
        label2: str,
        apply_type: str,
        status_text_value: str,
    ):
        source = item_text(item, "source", "department", "unit", default="-")
        note = item_text(item, "note", "remark", "memo", default="-")
        return "\n".join(
            [
                name,
                f"\u7c7b\u522b\uff1a{category}",
                f"\u5b50\u7c7b\uff1a{subcategory}",
                f"\u5b66\u5206\uff1a{credit}",
                f"\u5b66\u671f\uff1a{semester}",
                f"\u6807\u7b7e\uff1a{label1} / {label2}",
                f"\u7533\u8bf7\u7c7b\u578b\uff1a{apply_type}",
                f"\u72b6\u6001\uff1a{status_text_value}",
                f"\u6765\u6e90\uff1a{source}",
                f"\u5907\u6ce8\uff1a{note}",
            ]
        )

    def exam_list():
        if not exam_items:
            return empty_view("\u6682\u65e0\u8003\u8bd5")
        rows = [exam_row(exam) for exam in sorted(exam_items, key=exam_sort_key)]
        return ft.ListView(rows, spacing=10, expand=True, padding=pad(right=8))

    def grade_list():
        items = current_grade_items()
        if not items:
            return empty_view("\u6682\u65e0\u6210\u7ee9")

        rows = [grade_row(grade) for grade in items]
        return ft.ListView(rows, spacing=10, expand=True, padding=pad(right=8))

    def current_grade_items():
        if selected_grade_semester == ALL_SEMESTERS:
            return grade_items
        return [
            grade for grade in grade_items
            if not grade.get("semester")
            or grade.get("semester") == selected_grade_semester
            or str(grade.get("semester")) == selected_grade_semester
        ]

    def exam_row(exam: dict):
        c = colors()
        name = exam.get("course_name") or exam.get("course") or exam.get("name") or ""
        date_text = exam.get("date") or exam.get("exam_date") or "-"
        time_text = exam.get("time") or exam.get("exam_time") or "-"
        status_text_value, status_color, status_bg = exam_status_info(exam)
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=6, height=62, bgcolor=course_color(name), border_radius=6),
                    ft.Container(
                        content=ft.Text(
                            name or "\u672a\u547d\u540d\u8003\u8bd5",
                            size=15,
                            weight=ft.FontWeight.W_600,
                            color=c["text"],
                            max_lines=1,
                        ),
                        height=62,
                        alignment=ft.Alignment(-1, 0),
                        expand=True,
                    ),
                    metric_text("\u65e5\u671f", date_text),
                    metric_text("\u65f6\u95f4", time_text),
                    status_badge(status_text_value, status_color, status_bg),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=82,
            padding=pad_xy(14, 0),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=8,
            shadow=ft.BoxShadow(blur_radius=10, spread_radius=0, color=c["shadow"], offset=ft.Offset(0, 2)),
            tooltip=exam_tooltip(exam),
        )

    def status_badge(text: str, color: str, bgcolor: str):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=8, height=8, bgcolor=color, border_radius=4),
                    ft.Text(text, size=13, weight=ft.FontWeight.W_700, color=color),
                ],
                spacing=7,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=86,
            height=34,
            alignment=ft.Alignment(0, 0),
            bgcolor=bgcolor,
            border=all_border(1, f"{color}33"),
            border_radius=17,
        )

    def exam_status_info(exam: dict) -> tuple[str, str, str]:
        raw_status = str(exam.get("status") or "").strip()
        note = str(exam.get("note") or "").strip()
        ended = "\u5df2\u7ed3\u675f"
        running = "\u6b63\u5728"
        upcoming = "\u672a\u5f00\u59cb"
        unscheduled = "\u672a\u5b89\u6392"
        date_text = str(exam.get("date") or exam.get("exam_date") or "").strip()
        time_text = str(exam.get("time") or exam.get("exam_time") or "").strip()

        if exam.get("has_info") is False or "\u8bf7\u4e8e\u8bfe\u7a0b\u7ed3\u675f\u524d\u54a8\u8be2" in note:
            return unscheduled, "#9AA5A1", "#F7FAF9"

        if not raw_status and not date_text and not time_text:
            return unscheduled, "#9AA5A1", "#F7FAF9"

        if raw_status:
            if any(word in raw_status for word in (ended, "\u7ed3\u675f", "\u5df2\u8003")):
                return ended, "#C33B3B", "#FCEDED"
            if any(word in raw_status for word in (running, "\u8fdb\u884c")):
                return running, "#B98600", "#FFF5D6"
            if any(word in raw_status for word in (upcoming, "\u672a\u8003", "\u5c06\u5f00\u59cb")):
                return upcoming, "#2F8F6B", "#EAF7F1"
            if any(word in raw_status for word in (unscheduled, "\u65e0\u4fe1\u606f", "\u6682\u65e0", "\u65e0")):
                return unscheduled, "#9AA5A1", "#F7FAF9"

        start, end = parse_exam_datetime(exam)
        now = datetime.now()
        if start and end:
            if now > end:
                return ended, "#C33B3B", "#FCEDED"
            if start <= now <= end:
                return running, "#B98600", "#FFF5D6"
            return upcoming, "#2F8F6B", "#EAF7F1"
        if start:
            if now.date() > start.date():
                return ended, "#C33B3B", "#FCEDED"
            if now.date() == start.date():
                return running, "#B98600", "#FFF5D6"
        return upcoming, "#2F8F6B", "#EAF7F1"

    def exam_sort_key(exam: dict):
        status_text_value, _, _ = exam_status_info(exam)
        is_unscheduled = status_text_value == "\u672a\u5b89\u6392"
        start, _ = parse_exam_datetime(exam)
        return (1 if is_unscheduled else 0, start or datetime.max, exam.get("course_name") or "")

    def parse_exam_datetime(exam: dict):
        date_text = str(exam.get("date") or exam.get("exam_date") or "").strip()
        time_text = str(exam.get("time") or exam.get("exam_time") or "").strip()
        date_match = re.search(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})", date_text)
        if not date_match:
            return None, None
        year, month, day = (int(part) for part in date_match.groups())
        times = re.findall(r"(\d{1,2})\s*[:\uff1a]\s*(\d{2})", time_text)
        try:
            if not times:
                start = datetime(year, month, day)
                return start, None
            start_hour, start_minute = (int(part) for part in times[0])
            end_hour, end_minute = (int(part) for part in (times[-1] if len(times) > 1 else times[0]))
            start = datetime(year, month, day, start_hour, start_minute)
            end = datetime(year, month, day, end_hour, end_minute)
            return start, end
        except ValueError:
            return None, None

    def exam_tooltip(exam: dict):
        status_text_value, _, _ = exam_status_info(exam)
        return "\n".join(
            [
                exam.get("course_name") or exam.get("course") or exam.get("name") or "",
                f"\u65e5\u671f\uff1a{exam.get('date') or exam.get('exam_date') or '-'}",
                f"\u65f6\u95f4\uff1a{exam.get('time') or exam.get('exam_time') or '-'}",
                f"\u5730\u70b9\uff1a{exam.get('location') or '-'}",
                f"\u72b6\u6001\uff1a{status_text_value}",
            ]
        )

    def grade_row(grade: dict):
        c = colors()
        name = grade.get("course_name", "")
        color = course_color(name)
        score = grade.get("score", "")
        credit = grade.get("credit", 0)
        gpa = grade.get("gpa", 0)
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=6, height=62, bgcolor=color, border_radius=6),
                    ft.Container(
                        content=ft.Text(
                            name,
                            size=15,
                            weight=ft.FontWeight.W_600,
                            color=c["text"],
                            max_lines=1,
                        ),
                        height=62,
                        alignment=ft.Alignment(-1, 0),
                        expand=True,
                    ),
                    metric_text("\u5b66\u5206", credit),
                    metric_text("\u7efc\u5408\u5206\u6570", score),
                    metric_text("\u7ee9\u70b9", gpa),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=82,
            padding=pad_xy(14, 0),
            bgcolor=c["card"],
            border=all_border(1, c["border"]),
            border_radius=8,
            shadow=ft.BoxShadow(blur_radius=10, spread_radius=0, color=c["shadow"], offset=ft.Offset(0, 2)),
        )

    def metric_text(label: str, value):
        c = colors()
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(label, size=10, color=c["muted2"]),
                    ft.Text(str(value), size=14, weight=ft.FontWeight.W_600, color=c["text"]),
                ],
                spacing=1,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            width=86,
            height=62,
            alignment=ft.Alignment(-1, 0),
        )

    def small_button(label: str, icon, on_click):
        c = colors()
        return ft.Button(
            content=ft.Row([ft.Icon(icon, size=16), ft.Text(label, size=13)], spacing=6),
            height=40,
            style=ft.ButtonStyle(
                color=c["button_text"],
                bgcolor=c["button_bg"],
                side=ft.BorderSide(1, c["border"]),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=on_click,
        )

    def loading_view(text: str):
        return ft.Container(
            content=ft.Column(
                [ft.ProgressRing(width=26, height=26, stroke_width=3), ft.Text(text, color="#66736F")],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

    def empty_view(text: str):
        return ft.Container(
            content=ft.Text(text, size=15, color="#7B8783"),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

    def error_view(message: str, retry):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(message, size=14, color="#B04444"),
                    small_button("\u91cd\u8bd5", ft.Icons.REFRESH, retry),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

    def placeholder_view(title: str):
        return ft.Container(
            content=ft.Column(
                [
                    page_header(title, "\u6682\u672a\u5f00\u653e"),
                    empty_view(""),
                ],
                expand=True,
            ),
            padding=pad_xy(28, 26),
            expand=True,
        )

    def on_vpn_toggle(_):
        show = vpn_switch.value
        vpn_server_input.visible = show
        vpn_hint.visible = show
        page.update()

    username_input = ft.TextField(label="\u5b66\u53f7", width=320, autofocus=True)
    cas_pwd_input = ft.TextField(
        label="\u6559\u52a1\u7cfb\u7edf\u5bc6\u7801",
        width=320,
        password=True,
        can_reveal_password=True,
        on_submit=lambda _: start_login(),
    )
    remember_check = ft.Checkbox(label="\u8bb0\u4f4f\u5bc6\u7801", value=True)
    remember_row = ft.Container(
        content=remember_check,
        width=320,
        alignment=ft.Alignment(-1, 0),
    )
    vpn_switch = ft.Switch(label="\u4f7f\u7528 VPN \u8fde\u63a5", value=True, on_change=on_vpn_toggle)
    vpn_server_input = ft.TextField(
        label="VPN \u670d\u52a1\u5668\u5730\u5740",
        width=320,
        hint_text="濠?vpn.shiep.edu.cn",
        value=VPN_SERVER,
        visible=True,
    )
    vpn_hint = ft.Text("VPN \u4f7f\u7528\u6559\u52a1\u7cfb\u7edf\u540c\u4e00\u5bc6\u7801\uff0c\u65e0\u9700\u91cd\u590d\u586b\u5199", size=12, color="#87928E", visible=True)
    status_text = ft.Text("", size=14)
    login_btn = ft.Button("\u767b\u5f55", width=320, on_click=lambda _: start_login())
    login_title = ft.Text("SUEP \u6559\u52a1\u7cfb\u7edf", size=24, weight=ft.FontWeight.BOLD)
    login_subtitle = ft.Text("\u4e0a\u6d77\u7535\u529b\u5927\u5b66", size=14)
    login_vpn_title = ft.Text("VPN \u8bbe\u7f6e", size=14, weight=ft.FontWeight.W_600)
    login_wait_hint = ft.Text("\u6559\u52a1\u7cfb\u7edf\u5076\u5c14\u54cd\u5e94\u8f83\u6162\uff0c\u70b9\u51fb\u767b\u5f55\u540e\u8bf7\u8010\u5fc3\u7b49\u5f85\u3002", size=12, width=320, text_align=ft.TextAlign.CENTER)
    current_year = date.today().year
    start_year, start_month, start_day = semester_date_parts()
    semester_year_dropdown = ft.Dropdown(
        width=120,
        height=42,
        label="\u5e74",
        value=start_year,
        options=[ft.dropdown.Option(str(year), f"{year}") for year in range(2022, current_year + 3)],
    )
    semester_month_dropdown = ft.Dropdown(
        width=96,
        height=42,
        label="\u6708",
        value=start_month,
        options=[ft.dropdown.Option(str(month), f"{month:02d}") for month in range(1, 13)],
    )
    semester_day_dropdown = ft.Dropdown(
        width=96,
        height=42,
        label="\u65e5",
        value=start_day,
        options=[ft.dropdown.Option(str(day), f"{day:02d}") for day in range(1, 32)],
    )
    semester_settings_message = ft.Text("", size=12)
    theme_settings_message = ft.Text("", size=12)
    vpn_settings_message = ft.Text("", size=12)
    website_settings_message = ft.Text("", size=12)
    startup_settings_message = ft.Text("", size=12)
    cache_settings_message = ft.Text("", size=12)
    offline_btn = ft.Button("\u79bb\u7ebf\u8fdb\u5165", width=320, on_click=start_offline)

    login_shell = ft.Container(
        content=ft.Column(
            [
                login_title,
                login_subtitle,
                ft.Divider(height=18, color=ft.Colors.TRANSPARENT),
                username_input,
                ft.Container(height=4),
                cas_pwd_input,
                remember_row,
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                login_vpn_title,
                vpn_switch,
                vpn_server_input,
                vpn_hint,
                ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
                login_btn,
                offline_btn,
                login_wait_hint,
                status_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
        expand=True,
        alignment=ft.Alignment(0, 0),
        bgcolor="#FFFFFF",
    )

    sidebar = ft.Container(
        width=250,
        bgcolor="#EAF8F3",
        border=right_border(1, "#DDEAE6"),
    )
    content_area = ft.Container(expand=True, bgcolor="#FFFFFF")
    app_shell = ft.Row([sidebar, content_area], spacing=0, expand=True)

    container = ft.Container(content=login_shell, expand=True)
    apply_login_theme()
    page.add(container)

    creds = load_credentials()
    if creds:
        username_input.value = creds.get("username", "")
        cas_pwd_input.value = creds.get("cas_password", "")
        remember_check.value = creds.get("remember", False)
        saved_settings = load_settings(username_input.value)
        selected_theme_mode = str(saved_settings.get("theme_mode") or "light")
        selected_vpn_mode = normalized_vpn_mode(str(saved_settings.get("vpn_mode") or "startup"))
        selected_startup_view = normalized_startup_view(str(saved_settings.get("startup_view") or "plan"))
        vpn_switch.value = selected_vpn_mode == "startup"
        on_vpn_toggle(None)
        apply_login_theme()
        if creds.get("remember"):
            page.update()
            start_login(after_creds=True)


if __name__ == "__main__":
    ft.run(main)
