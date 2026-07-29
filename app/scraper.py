"""Academic data scraper for QZ EAMS."""



import json
import re
import time
from typing import Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .auth import AuthSession
from .config import EAMS_BASE_URL


# 鈹€鈹€ 寮烘櫤绯荤粺椤甸潰 / 鏁版嵁鎺ュ彛 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
COURSE_TABLE_URL = f"{EAMS_BASE_URL}/courseTableForStd.action"
COURSE_TABLE_AJAX_URL = f"{EAMS_BASE_URL}/courseTableForStd!courseTable.action"
TODAY_COURSE_URL = f"{EAMS_BASE_URL}/studTodayCourse.action"
TODAY_COURSE_SEARCH_URL = f"{EAMS_BASE_URL}/studTodayCourse!search.action"
GRADE_SEARCH_URL = f"{EAMS_BASE_URL}/teach/grade/course/person!search.action"
SEMESTER_DATA_URL = f"{EAMS_BASE_URL}/dataQuery.action"
MY_PLAN_COMPLETION_URL = f"{EAMS_BASE_URL}/myPlanCompl.action"

# Optional detected API endpoints from config.py.
try:
    from .config import COURSE_TABLE_DATA_URL
except ImportError:
    COURSE_TABLE_DATA_URL = None

try:
    from .config import GRADE_DATA_URL
except ImportError:
    GRADE_DATA_URL = None

# Default candidate endpoints, ordered from direct data endpoints to full pages.
SCHEDULE_API_CANDIDATES = [
    COURSE_TABLE_DATA_URL,
    f"{EAMS_BASE_URL}/courseTableForStd!getCourseTableData.action",
    f"{EAMS_BASE_URL}/courseTableForStd!getData.action",
    f"{EAMS_BASE_URL}/courseTableForStd!courseTable.action",
    COURSE_TABLE_URL,
]
SCHEDULE_API_CANDIDATES = [u for u in SCHEDULE_API_CANDIDATES if u]

GRADE_CANDIDATES = [
    GRADE_DATA_URL,
    f"{EAMS_BASE_URL}/teach/grade/course/person!search.action",
    f"{EAMS_BASE_URL}/gradeQuery!search.action",
    f"{EAMS_BASE_URL}/gradeQuery.action",
    f"{EAMS_BASE_URL}/grade!search.action",
]
GRADE_CANDIDATES = [u for u in GRADE_CANDIDATES if u]

EXAM_CANDIDATES = [
    f"{EAMS_BASE_URL}/stdExamTable!examTable.action",
    f"{EAMS_BASE_URL}/stdExamTable.action",
    f"{EAMS_BASE_URL}/stdExamTable!search.action",
]

IDENTIFY_APPLY_URL = f"{EAMS_BASE_URL}/identifyApply.action"
IDENTIFY_APPLY_SEARCH_URL = f"{EAMS_BASE_URL}/identifyApply!search.action"


class Scraper:
    """Academic data scraper."""

    def __init__(self, auth: AuthSession):
        if not auth.is_authenticated():
            raise ValueError("闇€瑕佸厛鐧诲綍鎵嶈兘鍒涘缓 Scraper")
        self.session = auth.get_session()
        self._semester_id = ""

    def _try_json_api(self, url: str, params: dict) -> list[dict] | None:
        """Try a JSON API endpoint."""
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return None
            ct = resp.headers.get("Content-Type", "")
            if "json" not in ct:
                return None
            data = resp.json()
        except Exception:
            return None

        if isinstance(data, dict):
            for key in ("courseTableList", "courseList", "courses", "data", "result"):
                if key in data:
                    data = data[key]
                    break
        if not isinstance(data, list):
            return None
        if not data:
            return None

        return self._normalize_courses(data)

    # Schedule

    def fetch_schedule(self, semester: str = "") -> list[dict]:
        """Fetch schedule data."""
        context = self._get_course_table_context()
        if context:
            post_data = {
                "ignoreHead": "1",
                "setting.kind": context.get("setting_kind", "std"),
                "startWeek": "1",
                "project.id": context.get("project_id", "1"),
                "semester.id": semester or context.get("semester_id", ""),
                "ids": context.get("student_id", ""),
            }
            post_data = {key: value for key, value in post_data.items() if value}
            try:
                resp = self.session.post(
                    COURSE_TABLE_AJAX_URL,
                    data=post_data,
                    headers={"X-Requested-With": "XMLHttpRequest"},
                    timeout=30,
                )
                resp.encoding = "utf-8"
                if resp.status_code == 200:
                    courses = self._parse_qz_schedule_html(resp.text)
                    if courses:
                        print(f"[鐖櫕] 璇捐〃鑾峰彇鎴愬姛 ({COURSE_TABLE_AJAX_URL})")
                        return courses
                    self._save_debug_page(resp.text, "last_course_ajax.html")
            except requests.RequestException as ex:
                print(f"[鐖櫕] 璇捐〃 AJAX 璇锋眰澶辫触: {ex}")

        params = {"_": str(int(time.time() * 1000))}
        if semester:
            params["semester.id"] = semester

        # 浼樺厛璇曟暟鎹?API锛堣繑鍥?JSON锛屾渶蹇級
        for url in SCHEDULE_API_CANDIDATES:
            if "courseTableForStd.action" in url and "getData" not in url and "getCourseTableData" not in url:
                continue  # 瀹屾暣椤甸潰鐣欏埌鏈€鍚?            result = self._try_json_api(url, params)
            if result:
                print(f"[鐖櫕] 璇捐〃鑾峰彇鎴愬姛 ({url})")
                return result

        # 鏈€鍚庢墠鐢ㄥ畬鏁撮〉闈?        print("[鐖櫕] 姝ｅ湪鑾峰彇瀹屾暣璇捐〃椤甸潰...")
        resp = self.session.get(COURSE_TABLE_URL, params=params, timeout=30)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            return []

        html = resp.text

        # 灏濊瘯澶氱瑙ｆ瀽鏂瑰紡
        for parser in [self._parse_json_from_script, self._parse_html_table, self._parse_course_divs]:
            courses = parser(html)
            if courses:
                print(f"[鐖櫕] 浠庨〉闈腑瑙ｆ瀽鍑?{len(courses)} 闂ㄨ")
                return courses

        print("[鐖櫕] 鏈兘瑙ｆ瀽璇捐〃, 宸蹭繚瀛樺埌 data/last_page.html")
        with open("data/last_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        return []

    def fetch_today_schedule(self) -> list[dict]:
        """Fetch today's course list from the real QZ EAMS endpoint."""
        try:
            resp = self.session.get(
                TODAY_COURSE_SEARCH_URL,
                params={"_": str(int(time.time() * 1000))},
                timeout=15,
            )
            resp.encoding = "utf-8"
        except requests.RequestException as ex:
            print(f"[Scraper] today schedule request failed: {ex}")
            return []

        if resp.status_code != 200:
            return []
        courses = self._parse_today_schedule_table(resp.text)
        if courses:
            print(f"[Scraper] today schedule fetched ({len(courses)} items)")
        return courses

    def _parse_today_schedule_table(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html or "", "html.parser")
        table = soup.find("table", class_=re.compile(r"gridtable", re.I)) or soup.find("table")
        if not table:
            return []

        today_text = ""
        heading = soup.find("h2")
        if heading:
            match = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", heading.get_text(" ", strip=True))
            today_text = match.group(1) if match else ""

        courses = []
        seen = set()
        for row in table.find_all("tr")[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
            if len(cells) < 2:
                continue
            name = cells[1] if len(cells) > 1 else ""
            details = cells[1:6]
            if not any(details):
                continue
            start_slot = self._slot_from_text(cells[0])
            course = {
                "name": name,
                "course_no": cells[2] if len(cells) > 2 else "",
                "teacher": cells[3] if len(cells) > 3 else "",
                "campus": cells[4] if len(cells) > 4 else "",
                "location": cells[5] if len(cells) > 5 else "",
                "slot_text": cells[0],
                "date": today_text,
                "start_slot": start_slot,
                "end_slot": start_slot,
            }
            key = (course["name"], course["slot_text"], course["location"])
            if key in seen:
                continue
            seen.add(key)
            courses.append(course)
        return self._merge_schedule_cells(courses)

    @staticmethod
    def _slot_from_text(text: str) -> int:
        match = re.search(r"(\d+)", text or "")
        return int(match.group(1)) if match else 0

    def _get_course_table_context(self) -> dict[str, str]:
        """Extract dynamic course-table AJAX parameters."""
        try:
            resp = self.session.get(COURSE_TABLE_URL, timeout=30)
            resp.encoding = "utf-8"
        except requests.RequestException:
            return {}
        if resp.status_code != 200:
            return {}

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        context = {
            "setting_kind": "std",
            "project_id": "1",
            "semester_id": "",
            "student_id": "",
        }

        for pattern in (
            r'semesterCalendar\([^;]*?value\s*:\s*["\'](\d+)',
            r'name=["\']semester\.id["\'][^>]*value=["\'](\d+)',
            r'semester\.id=(\d+)',
        ):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                context["semester_id"] = match.group(1)
                break

        for pattern in (
            r'addInput\([^)]*["\']ids["\']\s*,\s*["\'](\d+)',
            r'\bids\s*=\s*["\']?(\d+)',
            r'\bids=(\d+)',
            r'\bstd\.id\s*[:=]\s*["\']?(\d+)',
        ):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                context["student_id"] = match.group(1)
                break

        kind_select = soup.find("select", {"name": "setting.kind"})
        if kind_select:
            selected = kind_select.find("option", selected=True) or kind_select.find("option")
            if selected and selected.get("value"):
                context["setting_kind"] = selected["value"]

        project_select = soup.find("select", {"name": "project.id"})
        if project_select:
            selected = project_select.find("option", selected=True) or project_select.find("option")
            if selected and selected.get("value", "").isdigit():
                context["project_id"] = selected["value"]

        return context if context["student_id"] else {}

    def _parse_qz_schedule_html(self, html: str) -> list[dict]:
        """Parse QZ schedule JavaScript returned by AJAX."""
        scheduled = []
        activity_pattern = re.compile(
            r'activity\s*=\s*new\s+TaskActivity\(\s*'
            r'"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*'
            r'"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*'
            r'"([^"]*)"\s*\)\s*;',
            re.S,
        )
        activity_matches = list(activity_pattern.finditer(html))
        unit_count_match = re.search(r'var\s+unitCount\s*=\s*(\d+)', html)
        unit_count = int(unit_count_match.group(1)) if unit_count_match else 13

        for position, match in enumerate(activity_matches):
            end = activity_matches[position + 1].start() if position + 1 < len(activity_matches) else len(html)
            block = html[match.end():end]
            teacher = match.group(2).strip()
            course_text = match.group(4).strip()
            location = match.group(6).strip()
            valid_weeks = re.sub(r"\s+", "", match.group(7))
            course_name, text_weeks, week_text = self._parse_course_title(course_text)
            weeks = self._weeks_from_valid_flags(valid_weeks)
            if text_weeks:
                weeks = text_weeks
            if not course_name:
                continue

            indexes = re.findall(
                r'index\s*=\s*(\d+)\s*\*\s*unitCount\s*\+\s*(\d+)',
                block,
                re.I,
            )
            for day_index, slot_index in indexes:
                scheduled.append({
                    "name": course_name,
                    "teacher": teacher,
                    "location": location,
                    "day_of_week": int(day_index) + 1,
                    "start_slot": int(slot_index) + 1,
                    "end_slot": int(slot_index) + 1,
                    "weeks": weeks,
                    "week_text": week_text or self._format_weeks(weeks),
                    "note": "",
                })

        scheduled = self._merge_schedule_cells(scheduled)
        catalog = self._parse_qz_course_catalog(html)
        if not scheduled:
            return catalog

        scheduled_names = {course["name"] for course in scheduled}
        scheduled.extend(
            course for course in catalog
            if course["name"] not in scheduled_names
        )
        return scheduled

    @staticmethod
    def _merge_schedule_cells(courses: list[dict]) -> list[dict]:
        merged = {}
        for course in courses:
            key = (
                course["name"],
                course["teacher"],
                course["location"],
                course["day_of_week"],
                tuple(course["weeks"]),
            )
            item = merged.get(key)
            if item is None:
                merged[key] = dict(course)
            else:
                item["start_slot"] = min(item["start_slot"], course["start_slot"])
                item["end_slot"] = max(item["end_slot"], course["end_slot"])
        return list(merged.values())

    @staticmethod
    def _weeks_from_valid_flags(valid_weeks: str) -> list[int]:
        flags = re.sub(r"\s+", "", valid_weeks or "")
        if len(flags) >= 20:
            return [
                index
                for index, flag in enumerate(flags)
                if flag == "1" and index > 0
            ]
        return [
            index + 1
            for index, flag in enumerate(flags)
            if flag == "1"
        ]

    @classmethod
    def _parse_course_title(cls, title: str) -> tuple[str, list[int], str]:
        title = (title or "").strip()
        weeks, week_text = cls._parse_week_descriptor(title)
        clean = re.sub(
            r"[（(]?\s*\d+\s*[-–—~至]\s*\d+\s*(?:单周|双周|单双周|周)?\s*[）)]?\s*$",
            "",
            title,
        ).strip()
        clean = re.sub(r"\([^()]*\)\s*$", "", clean).strip()
        return clean, weeks, week_text

    @staticmethod
    def _parse_week_descriptor(text: str) -> tuple[list[int], str]:
        match = re.search(
            r"[（(]?\s*(\d+)\s*[-–—~至]\s*(\d+)\s*(单周|双周|单双周)?\s*(?:周)?\s*[）)]?",
            text or "",
        )
        if not match:
            return [], ""
        start, end = int(match.group(1)), int(match.group(2))
        kind = match.group(3) or ""
        weeks = list(range(start, end + 1))
        if kind == "单周":
            weeks = [week for week in weeks if week % 2 == 1]
        elif kind == "双周":
            weeks = [week for week in weeks if week % 2 == 0]
        suffix = " 单周" if kind == "单周" else (" 双周" if kind == "双周" else " 周")
        return weeks, f"{start}-{end}{suffix}"

    @staticmethod
    def _format_weeks(weeks: list[int]) -> str:
        if not weeks:
            return "全周"
        ordered = sorted(set(int(week) for week in weeks))
        if len(ordered) > 1 and all(week % 2 == 1 for week in ordered):
            return f"{ordered[0]}-{ordered[-1]} 单周"
        if len(ordered) > 1 and all(week % 2 == 0 for week in ordered):
            return f"{ordered[0]}-{ordered[-1]} 双周"
        if ordered == list(range(ordered[0], ordered[-1] + 1)):
            return f"{ordered[0]}-{ordered[-1]} 周"
        return ",".join(str(week) for week in ordered)

    def _parse_qz_course_catalog(self, html: str) -> list[dict]:
        """Parse fallback course rows from an AJAX response."""
        soup = BeautifulSoup(html, "html.parser")
        for table in soup.find_all("table"):
            headers = [cell.get_text(" ", strip=True) for cell in table.find_all("th")]
            if "璇剧▼鍚嶇О" not in headers or "鏁欏笀" not in headers:
                continue
            name_index = headers.index("璇剧▼鍚嶇О")
            teacher_index = headers.index("鏁欏笀")
            courses = []
            for row in table.find_all("tr")[1:]:
                cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
                if len(cells) <= max(name_index, teacher_index):
                    continue
                name = cells[name_index]
                if name:
                    courses.append({
                        "name": name,
                        "teacher": cells[teacher_index],
                        "location": "",
                        "day_of_week": 0,
                        "start_slot": 0,
                        "end_slot": 0,
                        "weeks": [],
                        "note": "",
                    })
            return courses
        return []

    @staticmethod
    def _save_debug_page(html: str, filename: str):
        from pathlib import Path
        path = Path("data") / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def _parse_json_from_script(self, html: str) -> list[dict]:
        """Extract JSON data from script tags."""
        soup = BeautifulSoup(html, "html.parser")

        for var_name in ["courseTableData", "courseData", "scheduleData",
                         "jsonData", "allCourses", "data"]:
            pattern = re.compile(
                rf'{var_name}\s*=\s*(\[.*?\])\s*;',
                re.DOTALL
            )
            match = pattern.search(html)
            if match:
                try:
                    import json
                    data = json.loads(match.group(1))
                    if isinstance(data, list) and len(data) > 0:
                        return self._normalize_courses(data)
                except json.JSONDecodeError:
                    continue

        # 涔熸壘涓€涓?id 涓?data 鐨?script 鏍囩
        script = soup.find("script", {"id": "data"})
        if script and script.string:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    return self._normalize_courses(data)
            except json.JSONDecodeError:
                pass

        return []

    def _parse_html_table(self, html: str) -> list[dict]:
        """Parse legacy schedule HTML tables."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id=re.compile(r"courseTable|classTable|scheduleTable"))
        if not table:
            table = soup.find("table", class_=re.compile(r"courseTable|classTable|scheduleTable"))
        if not table:
            return []

        courses = []
        rows = table.find_all("tr")
        for row in rows[1:]:  # 璺宠繃琛ㄥご
            cells = row.find_all("td")
            for col_idx, cell in enumerate(cells):
                course_items = cell.find_all("div", class_="course") or cell.find_all("div", recursive=False)
                if not course_items:
                    course_items = [cell] if cell.get_text(strip=True) else []

                for item in course_items:
                    text = item.get_text("\n", strip=True)
                    if not text:
                        continue
                    parsed = self._parse_cell_text(text)
                    if parsed:
                        parsed["day_of_week"] = col_idx + 1  # 鍒?鏄熸湡
                        courses.append(parsed)

        return courses

    def _parse_course_divs(self, html: str) -> list[dict]:
        """Parse div-rendered course blocks."""
        soup = BeautifulSoup(html, "html.parser")
        course_divs = soup.find_all("div", class_=re.compile(r"course|class-info|lesson"))
        if not course_divs:
            return []

        courses = []
        for div in course_divs:
            text = div.get_text("\n", strip=True)
            if not text:
                continue
            # 灏濊瘯鎻愬彇浣嶇疆淇℃伅
            style = div.get("style", "")
            grid_match = re.search(r"grid-column:\s*(\d+)", style)
            row_match = re.search(r"grid-row:\s*(\d+)", style)

            parsed = self._parse_cell_text(text)
            if parsed:
                if grid_match:
                    parsed["day_of_week"] = int(grid_match.group(1))
                # 鑺傛鍙兘闇€瑕佹牴鎹?row 鎺ㄧ畻
                courses.append(parsed)

        return courses

    def _parse_cell_text(self, text: str) -> Optional[dict]:
        """Parse a schedule cell text block."""

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None

        course_name, title_weeks, title_week_text = self._parse_course_title(lines[0])
        course = {
            "name": course_name or lines[0],
            "teacher": "",
            "location": "",
            "weeks": title_weeks,
            "week_text": title_week_text,
            "start_slot": 0,
            "end_slot": 0,
            "note": "",
        }

        for i, line in enumerate(lines):
            if "教师" in line or "老师" in line:
                course["teacher"] = re.sub(r"^(教师|老师)[：:\s]*", "", line)
            elif i == 1 and not course["teacher"] and len(line) < 20:
                course["teacher"] = line

            if re.search(r"[教馆楼室场]", line) or "实验室" in line:
                course["location"] = re.sub(r"^(地点|教室)[：:\s]*", "", line)
            elif i == 2 and not course["location"]:
                course["location"] = line

            weeks_match = re.search(r"(\d+)\s*[-–—~至]\s*(\d+)\s*(单周|双周)?\s*周?", line)
            if weeks_match:
                start, end = int(weeks_match.group(1)), int(weeks_match.group(2))
                weeks = list(range(start, end + 1))
                kind = weeks_match.group(3) or ""
                if kind == "单周":
                    weeks = [week for week in weeks if week % 2 == 1]
                elif kind == "双周":
                    weeks = [week for week in weeks if week % 2 == 0]
                course["weeks"] = weeks
                course["week_text"] = f"{start}-{end}" + (f" {kind}" if kind else " 周")

            slot_match = re.search(r"(\d+)\s*[-–—~至]\s*(\d+)\s*节", line)
            if slot_match:
                course["start_slot"] = int(slot_match.group(1))
                course["end_slot"] = int(slot_match.group(2))

            if "备注" in line:
                course["note"] = re.sub(r"^备注[：:\s]*", "", line)
        return course

    def _normalize_courses(self, data: list[dict]) -> list[dict]:
        """Normalize JSON courses into a common dict shape."""
        normalized = []
        for item in data:
            c = {
                "name": item.get("name") or item.get("courseName") or item.get("course_name", ""),
                "teacher": item.get("teacher") or item.get("teacherName") or item.get("teacher_name", ""),
                "location": item.get("location") or item.get("classroom") or item.get("room", ""),
                "day_of_week": int(item.get("dayOfWeek") or item.get("day") or item.get("weekday", 0)),
                "start_slot": int(item.get("startUnit") or item.get("startSlot") or item.get("start", 0)),
                "end_slot": int(item.get("endUnit") or item.get("endSlot") or item.get("end", 0)),
                "weeks": item.get("weeks") or item.get("weekList") or item.get("weeksList", []),
                "week_text": item.get("week_text") or item.get("weekText") or item.get("weeksText", ""),
                "note": item.get("note") or item.get("remark", ""),
            }
            # weeks 鍙兘鏄瓧绗︿覆 "1,2,3..." 鎴?"1-16"
            if isinstance(c["weeks"], str):
                c["weeks"] = self._parse_weeks_str(c["weeks"])
            if not c["week_text"]:
                c["week_text"] = self._format_weeks(c["weeks"])
            if c["name"]:
                normalized.append(c)
        return normalized

    # Grades

    def fetch_grades(self, semester: str = "") -> list[dict]:
        """Fetch grade data."""


        old_semester = self._semester_id
        if semester:
            self._semester_id = semester

        for url in GRADE_CANDIDATES:
            result = self._try_grade_url(url)
            if result is not None:
                if result:
                    print(f"[Scraper] grade data fetched from {url}")
                    self._semester_id = old_semester
                    return result
                # 椤甸潰璁块棶鎴愬姛浣嗘棤鎴愮哗
                continue
            # 椤甸潰鎵撲笉寮€锛岃瘯涓嬩竴涓?
        print("[Scraper] no grade data found")
        self._semester_id = old_semester
        return []

    def _try_grade_url(self, url: str) -> Optional[list[dict]]:
        semester_id = self._semester_id or "404"
        timestamp = str(int(time.time() * 1000))
        param_candidates = [
            {"semesterId": semester_id, "projectType": "", "_": timestamp},
            {"semester.id": semester_id, "projectType": "", "_": timestamp},
            {"semesterId": semester_id, "_": timestamp},
            {"semester.id": semester_id, "_": timestamp},
        ]
        saw_success = False

        for params in param_candidates:
            try:
                resp = self.session.get(url, params=params, timeout=15)
                resp.encoding = "utf-8"
            except requests.RequestException:
                continue

            if resp.status_code != 200:
                continue

            saw_success = True
            html = resp.text

            courses = self._parse_grades_from_json(html)
            if courses:
                return courses

            courses = self._parse_grades_from_table(html)
            if courses:
                return courses

        return [] if saw_success else None

    def _parse_grades_from_json(self, html: str) -> list[dict]:
        """Extract JSON grade data from a page."""
        # 鏌ユ壘甯歌 JSON 鍙橀噺
        for var in ["gradeData", "gradeList", "gradeTableData", "data"]:
            pattern = re.compile(rf'{var}\s*=\s*(\[.*?\])\s*;', re.DOTALL)
            match = pattern.search(html)
            if match:
                try:
                    import json
                    data = json.loads(match.group(1))
                    if data:
                        return self._normalize_grades(data)
                except json.JSONDecodeError:
                    continue

        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            if not script.string:
                continue
            for var in ["gradeData", "gradeList", "data"]:
                pattern = re.compile(rf'{var}\s*=\s*(\[.*?\])\s*;', re.DOTALL)
                match = pattern.search(script.string)
                if match:
                    try:
                        import json
                        data = json.loads(match.group(1))
                        if data:
                            return self._normalize_grades(data)
                    except json.JSONDecodeError:
                        continue

        return []

    def _parse_grades_from_table(self, html: str) -> list[dict]:
        """Parse grade HTML tables."""
        soup = BeautifulSoup(html, "html.parser")
        table = (
            soup.find("table", id=re.compile(r"grade|score|result|grid", re.I))
            or soup.find("table", class_=re.compile(r"grade|score|result|grid", re.I))
        )

        if not table:
            return []

        headers = []
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all("th")]
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(["th", "td"])]

        grades = []
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 3:
                continue

            grade = {
                "semester": "",
                "course_name": "",
                "credit": 0.0,
                "score": "",
                "gpa": 0.0,
                "exam_type": "",
                "is_passed": True,
            }

            for idx, val in enumerate(cells):
                if idx >= len(headers):
                    break
                h = headers[idx].strip()
                h_lower = h.lower()
                if any(key in h for key in ("课程类别", "课程性质", "课程属性", "类别", "性质", "考试类型", "考核方式")):
                    grade["exam_type"] = val
                elif any(key in h for key in ("学期", "学年", "Semester")):
                    grade["semester"] = val
                elif "学分" in h or "Credit" in h:
                    try:
                        grade["credit"] = float(val)
                    except ValueError:
                        grade["credit"] = 0.0
                elif any(key in h for key in ("最终", "成绩", "分数", "得分", "Score", "Grade")):
                    grade["score"] = val
                elif "绩点" in h or "GPA" in h.upper():
                    try:
                        grade["gpa"] = float(val)
                    except ValueError:
                        grade["gpa"] = 0.0
                elif (
                    "课程名称" in h
                    or "教学班" in h
                    or "科目" in h
                    or "course name" in h_lower
                    or h in ("课程", "Course")
                ):
                    grade["course_name"] = val
                elif "是否" in h or "通过" in h or "Pass" in h:
                    grade["is_passed"] = any(word in val for word in ("通过", "及格", "是", "Y", "Pass"))

            if grade["course_name"]:
                grades.append(grade)

        return grades

    def _normalize_grades(self, data: list[dict]) -> list[dict]:
        """Normalize JSON grade records."""
        normalized = []
        for item in data:
            g = {
                "semester": item.get("semester") or item.get("semesterName") or item.get("academicYear", ""),
                "course_name": item.get("courseName") or item.get("course_name") or item.get("name", ""),
                "credit": float(item.get("credit") or item.get("courseCredit", 0) or 0),
                "score": str(item.get("score") or item.get("grade") or item.get("mark", "")),
                "gpa": float(item.get("gpa") or item.get("gradePoint", 0) or 0),
                "exam_type": item.get("examType") or item.get("exam_type", ""),
                "is_passed": item.get("isPassed") or item.get("pass", False) or False,
            }
            if g["course_name"]:
                normalized.append(g)
        return normalized

    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?    #  杈呭姪鏂规硶
    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
    def fetch_exams(self, semester: str = "") -> list[dict]:
        """Fetch exam schedule data from real QZ EAMS exam table endpoints."""
        semester_ids = [str(semester)] if semester else []
        if not semester_ids:
            context = self._get_course_table_context()
            if context.get("semester_id"):
                semester_ids.append(context["semester_id"])
        if not semester_ids:
            semesters = [str(item.get("id")) for item in self.get_semesters() if item.get("id")]
            if semesters:
                semester_ids.append(semesters[0])

        timestamp = str(int(time.time() * 1000))
        for semester_id in semester_ids:
            try:
                resp = self.session.get(
                    f"{EAMS_BASE_URL}/stdExamTable!examTable.action",
                    params={"semester.id": semester_id, "_": timestamp},
                    timeout=15,
                )
                resp.encoding = "utf-8"
            except requests.RequestException:
                continue
            if resp.status_code != 200:
                continue
            exams = self._parse_exams_from_table(resp.text)
            if exams:
                print(f"[Scraper] exam data fetched for semester {semester_id}")
                return exams

        params = {"_": timestamp}
        for url in EXAM_CANDIDATES:
            result = self._try_exam_url(url, params)
            if result is not None:
                if result:
                    print(f"[Scraper] exam data fetched from {url}")
                    return result
                continue
        print("[Scraper] no exam data found from known URLs")
        return []

    def _try_exam_url(self, url: str, params: dict) -> Optional[list[dict]]:
        saw_success = False
        request_plan = [
            ("get", params),
            ("post", params),
        ]
        for method, request_params in request_plan:
            try:
                if method == "post":
                    resp = self.session.post(url, data=request_params, timeout=15)
                else:
                    resp = self.session.get(url, params=request_params, timeout=15)
                resp.encoding = "utf-8"
            except requests.RequestException:
                continue

            if resp.status_code != 200:
                continue

            saw_success = True
            html = resp.text
            exams = self._parse_exams_from_json(html)
            if exams:
                return exams

            exams = self._parse_exams_from_table(html)
            if exams:
                return exams

        return [] if saw_success else None

    def _parse_exams_from_json(self, text: str) -> list[dict]:
        payloads = []
        stripped = (text or "").strip()
        if stripped.startswith(("{", "[")):
            try:
                payloads.append(json.loads(stripped))
            except json.JSONDecodeError:
                pass

        for var_name in ("examData", "examList", "examTableData", "data", "rows"):
            pattern = re.compile(rf"{var_name}\s*=\s*(\[.*?\]|\{{.*?\}})\s*;", re.S)
            for match in pattern.finditer(text or ""):
                try:
                    payloads.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    continue

        for payload in payloads:
            for items in self._exam_items_from_payload(payload):
                exams = self._normalize_exams(items)
                if exams:
                    return exams
        return []

    def _exam_items_from_payload(self, payload) -> list[list[dict]]:
        if isinstance(payload, list):
            dict_items = [item for item in payload if isinstance(item, dict)]
            return [dict_items] if dict_items else []
        if not isinstance(payload, dict):
            return []

        found = []
        for key in ("examList", "exams", "examTableData", "data", "result", "rows", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                dict_items = [item for item in value if isinstance(item, dict)]
                if dict_items:
                    found.append(dict_items)
            elif isinstance(value, dict):
                found.extend(self._exam_items_from_payload(value))

        if not found:
            for value in payload.values():
                if isinstance(value, (dict, list)):
                    found.extend(self._exam_items_from_payload(value))
        return found

    def _parse_exams_from_table(self, html: str) -> list[dict]:
        exams = []
        seen = set()
        raw_rows = re.split(r"(?=<tr\b)", html or "", flags=re.I)
        row_chunks = []
        for chunk in raw_rows:
            chunk = chunk.strip()
            if re.match(r"<tr\b", chunk, re.I):
                row_chunks.append(chunk.split("</tr>", 1)[0] + "</tr>")

        if row_chunks:
            headers = []
            for chunk in row_chunks:
                cells = self._cells_from_table_row_chunk(chunk)
                if not cells:
                    continue
                if self._cells_are_exam_headers(cells):
                    headers = cells
                    continue
                exam = self._exam_from_real_table_cells(headers, cells)
                if not exam.get("course_name"):
                    continue
                key = (
                    exam.get("course_name", ""),
                    exam.get("date", ""),
                    exam.get("time", ""),
                    exam.get("location", ""),
                    exam.get("note", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                exams.append(exam)
            if exams:
                return exams

        soup = BeautifulSoup(html or "", "html.parser")

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue

            headers = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])]
            if not headers:
                continue

            start_index = 1
            if not self._headers_look_like_exam(headers):
                th_headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
                if th_headers and self._headers_look_like_exam(th_headers):
                    headers = th_headers
                else:
                    start_index = 0

            for row in rows[start_index:]:
                cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
                if len(cells) < 2:
                    continue
                exam = self._map_exam_cells(headers, cells)
                if not exam.get("course_name"):
                    exam = self._fallback_exam_from_cells(cells)
                if not exam.get("course_name"):
                    continue
                key = (
                    exam.get("course_name", ""),
                    exam.get("date", ""),
                    exam.get("time", ""),
                    exam.get("location", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                exams.append(exam)

        return exams

    @staticmethod
    def _cells_from_table_row_chunk(chunk: str) -> list[str]:
        cells = []
        for match in re.finditer(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", chunk or "", re.I | re.S):
            cell_html = match.group(1)
            text = BeautifulSoup(cell_html, "html.parser").get_text(" ", strip=True)
            cells.append(re.sub(r"\s+", " ", text).strip())
        return cells

    def _exam_from_real_table_cells(self, headers: list[str], cells: list[str]) -> dict:
        if len(cells) >= 8:
            return {
                "course_code": cells[0],
                "course_name": cells[1],
                "exam_type": cells[2],
                "date": cells[3],
                "time": cells[4],
                "location": cells[5],
                "status": cells[6],
                "note": cells[7],
                "has_info": True,
            }
        if len(cells) >= 4 and self._headers_look_like_exam(headers):
            return {
                "course_code": cells[0],
                "course_name": cells[1],
                "exam_type": cells[2],
                "date": "",
                "time": "",
                "location": "",
                "status": "\u672a\u5b89\u6392",
                "note": cells[3],
                "has_info": False,
            }
        return self._fallback_exam_from_cells(cells)

    @staticmethod
    def _headers_look_like_exam(headers: list[str]) -> bool:
        joined = " ".join(headers).lower()
        keywords = (
            "\u8bfe\u7a0b", "\u79d1\u76ee", "\u8003\u8bd5", "\u65e5\u671f",
            "\u65f6\u95f4", "\u8003\u573a", "course", "exam", "date", "time",
        )
        return any(keyword in joined for keyword in keywords)

    @staticmethod
    def _cells_are_exam_headers(cells: list[str]) -> bool:
        joined = " ".join(cells).lower()
        header_keywords = (
            "\u8bfe\u7a0b\u540d\u79f0", "\u8003\u8bd5\u65e5\u671f", "\u8003\u8bd5\u5b89\u6392",
            "\u8003\u8bd5\u5730\u70b9", "\u8003\u8bd5\u60c5\u51b5", "\u5176\u5b83\u8bf4\u660e",
            "course name", "exam date", "exam time",
        )
        return any(keyword in joined for keyword in header_keywords)

    def _map_exam_cells(self, headers: list[str], cells: list[str]) -> dict:
        exam = {
            "course_name": "",
            "date": "",
            "time": "",
            "location": "",
            "status": "",
        }
        for idx, value in enumerate(cells):
            header = headers[idx] if idx < len(headers) else ""
            header_lower = header.lower()
            if self._header_matches(header_lower, ("\u8bfe\u7a0b", "\u79d1\u76ee", "course", "name")):
                exam["course_name"] = value
            elif self._header_matches(header_lower, ("\u65e5\u671f", "date", "day")):
                exam["date"] = value
            elif self._header_matches(header_lower, ("\u65f6\u95f4", "time")):
                date_part, time_part = self._split_exam_datetime(value)
                exam["date"] = exam["date"] or date_part
                exam["time"] = time_part or value
            elif self._header_matches(header_lower, ("\u5730\u70b9", "\u8003\u573a", "\u6559\u5ba4", "room", "place", "location")):
                exam["location"] = value
            elif self._header_matches(header_lower, ("\u72b6\u6001", "status")):
                exam["status"] = value

        if not exam["date"] or not exam["time"]:
            date_part, time_part = self._split_exam_datetime(" ".join(cells))
            exam["date"] = exam["date"] or date_part
            exam["time"] = exam["time"] or time_part
        return exam

    @staticmethod
    def _header_matches(header: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in header for keyword in keywords)

    def _fallback_exam_from_cells(self, cells: list[str]) -> dict:
        joined = " ".join(cells)
        date_part, time_part = self._split_exam_datetime(joined)
        course = cells[0] if cells else ""
        location = ""
        for value in cells[1:]:
            if value not in (date_part, time_part) and not self._looks_like_datetime(value):
                location = value
                break
        return {
            "course_name": course,
            "date": date_part,
            "time": time_part,
            "location": location,
            "status": "",
        }

    @staticmethod
    def _looks_like_datetime(text: str) -> bool:
        return bool(re.search(r"\d{1,4}[-/.]\d{1,2}|\d{1,2}:\d{2}", text or ""))

    @staticmethod
    def _split_exam_datetime(text: str) -> tuple[str, str]:
        value = text or ""
        date_match = re.search(
            r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|20\d{2}\s*\u5e74\s*\d{1,2}\s*\u6708\s*\d{1,2}\s*\u65e5)",
            value,
        )
        time_match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:-|~|\u2013|\u2014|\u81f3|to)\s*\d{1,2}:\d{2}|\d{1,2}:\d{2})",
            value,
            re.I,
        )
        date_part = date_match.group(1).strip() if date_match else ""
        time_part = time_match.group(1).strip() if time_match else ""
        return date_part, time_part

    def _normalize_exams(self, data: list[dict]) -> list[dict]:
        normalized = []
        for item in data:
            date_value = self._first_value(
                item,
                "date", "examDate", "exam_date", "ksrq", "ksDate",
                "\u65e5\u671f", "\u8003\u8bd5\u65e5\u671f",
            )
            time_value = self._first_value(
                item,
                "time", "examTime", "exam_time", "kssj", "timeRange", "startTime",
                "\u65f6\u95f4", "\u8003\u8bd5\u65f6\u95f4",
            )
            date_part, time_part = self._split_exam_datetime(f"{date_value} {time_value}")
            exam = {
                "course_name": self._first_value(
                    item,
                    "course_name", "courseName", "course", "name", "lessonName", "taskName",
                    "\u8bfe\u7a0b\u540d\u79f0", "\u8bfe\u7a0b", "\u79d1\u76ee",
                ),
                "date": date_value or date_part,
                "time": time_value or time_part,
                "location": self._first_value(
                    item,
                    "location", "room", "classroom", "place", "examRoom", "examPlace",
                    "\u5730\u70b9", "\u8003\u573a", "\u6559\u5ba4",
                ),
                "status": self._first_value(item, "status", "state", "\u72b6\u6001"),
            }
            if not exam["date"] or not exam["time"]:
                fallback_date, fallback_time = self._split_exam_datetime(" ".join(str(v) for v in item.values()))
                exam["date"] = exam["date"] or fallback_date
                exam["time"] = exam["time"] or fallback_time
            if exam["course_name"]:
                normalized.append(exam)
        return normalized

    def fetch_plan_completion(self) -> dict:
        """Fetch and parse plan-completion data."""
        timestamp = str(int(time.time() * 1000))
        try:
            resp = self.session.get(MY_PLAN_COMPLETION_URL, params={"_": timestamp}, timeout=20)
            resp.encoding = "utf-8"
        except requests.RequestException:
            return {}
        if resp.status_code != 200:
            return {}
        result = self._parse_plan_completion(resp.text)
        if result:
            print(f"[Scraper] plan-completion data fetched ({len(result.get('sections', []))} sections)")
        return result

    def _parse_plan_completion(self, html: str) -> dict:
        soup = BeautifulSoup(html or "", "html.parser")
        info = self._parse_plan_info(soup)
        sections = self._parse_plan_sections(soup)
        return {"info": info, "sections": sections} if info or sections else {}

    def _parse_plan_info(self, soup: BeautifulSoup) -> dict:
        table = soup.find("table", class_=re.compile(r"infoTable", re.I))
        if table is None:
            return {}
        pairs: list[tuple[str, str]] = []
        for row in table.find_all("tr"):
            cells = [self._clean_text(cell.get_text(" ", strip=True).replace("\xa0", " ")) for cell in row.find_all("td")]
            for index in range(0, len(cells) - 1, 2):
                key = cells[index].rstrip(":： ")
                value = cells[index + 1]
                if key or value:
                    pairs.append((key, value))
        values = [value for _, value in pairs]

        def value_after(*needles: str) -> str:
            for key, value in pairs:
                if any(needle in key for needle in needles):
                    return value
            return ""

        major = value_after("专业", "方向") or next((value for value in values if "专业" in value), "")
        credit_text = value_after("学分")
        if not credit_text:
            credit_text = next((value for value in values if re.search(r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?", value)), "")
        credit_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", credit_text)
        required_credit = 0.0
        completed_credit = 0.0
        if credit_match:
            required_credit = float(credit_match.group(1))
            completed_credit = float(credit_match.group(2))
        return {
            "major": major,
            "credit_completion": credit_text,
            "required_credit": required_credit,
            "completed_credit": completed_credit,
            "gpa": value_after("GPA"),
            "audit_result": value_after("审核结果"),
            "audit_time": value_after("审核时间"),
            "department": value_after("院系"),
            "grade": value_after("年级"),
        }

    def _parse_plan_sections(self, soup: BeautifulSoup) -> list[dict]:
        tables = soup.find_all("table", class_=re.compile(r"formTable", re.I))
        if not tables:
            tables = soup.select("#chartView table")
        if not tables:
            return []

        sections = []
        for table_index, table in enumerate(tables):
            if table_index > 0:
                plan_out = {
                    "title": "计划外课程",
                    "required_credit": 0.0,
                    "completed_credit": 0.0,
                    "status": "",
                    "note": "",
                    "courses": [],
                }
                for row in table.find_all("tr"):
                    cells = [self._clean_text(cell.get_text(" ", strip=True).replace("\xa0", " ")) for cell in row.find_all("td")]
                    if len(cells) < 8 or not cells[0].isdigit():
                        continue
                    plan_out["courses"].append({
                        "index": cells[0],
                        "code": cells[1],
                        "name": cells[2],
                        "category": cells[3],
                        "credit": self._parse_credit_value(cells[4]),
                        "completed_credit": self._parse_credit_value(cells[5]),
                        "score": cells[6],
                        "passed": "否" not in cells[7],
                        "passed_text": cells[7],
                        "note": cells[8] if len(cells) > 8 else "计划外",
                    })
                if plan_out["courses"]:
                    sections.append(plan_out)
                continue

            current = None
            for row in table.find_all("tr"):
                cells = [self._clean_text(cell.get_text(" ", strip=True).replace("\xa0", " ")) for cell in row.find_all("td")]
                if not cells or cells[0] in ("课程", "序号"):
                    continue
                classes = row.get("class") or []
                if "darkColumn" in classes or not cells[0].isdigit():
                    title = cells[0]
                    if not title:
                        continue
                    current = {
                        "title": title,
                        "required_credit": self._parse_credit_value(cells[1] if len(cells) > 1 else ""),
                        "completed_credit": self._parse_credit_value(cells[2] if len(cells) > 2 else ""),
                        "status": cells[4] if len(cells) > 4 else "",
                        "note": cells[5] if len(cells) > 5 else "",
                        "courses": [],
                    }
                    sections.append(current)
                    continue
                if len(cells) >= 8:
                    if current is None:
                        current = {
                            "title": "未分类课程",
                            "required_credit": 0.0,
                            "completed_credit": 0.0,
                            "status": "",
                            "note": "",
                            "courses": [],
                        }
                        sections.append(current)
                    current["courses"].append({
                        "index": cells[0],
                        "code": cells[1],
                        "name": cells[2],
                        "credit": self._parse_credit_value(cells[3]),
                        "completed_credit": self._parse_credit_value(cells[4]),
                        "score": cells[5],
                        "passed": "否" not in cells[6],
                        "passed_text": cells[6],
                        "note": cells[7],
                    })
        return sections

    def fetch_second_credits(self, kind: str = "quality") -> list[dict]:
        """Fetch quality-development second-credit records."""
        if kind != "quality":
            return []

        timestamp = str(int(time.time() * 1000))
        try:
            self.session.get(IDENTIFY_APPLY_URL, params={"_": timestamp}, timeout=15)
        except requests.RequestException:
            pass

        request_plan = [
            ("get", {"_": timestamp}),
            ("post", {"_": timestamp}),
            ("get", {}),
        ]
        for method, params in request_plan:
            try:
                if method == "post":
                    resp = self.session.post(IDENTIFY_APPLY_SEARCH_URL, data=params, timeout=15)
                else:
                    resp = self.session.get(IDENTIFY_APPLY_SEARCH_URL, params=params, timeout=15)
                resp.encoding = "utf-8"
            except requests.RequestException:
                continue
            if resp.status_code != 200:
                continue

            records = self._parse_second_credits_from_json(resp.text)
            if not records:
                records = self._parse_second_credits_from_table(resp.text)
            if records:
                print(f"[Scraper] second-credit data fetched ({len(records)} items)")
                return records

        print("[Scraper] no second-credit data found")
        return []

    def _parse_second_credits_from_json(self, text: str) -> list[dict]:
        stripped = (text or "").strip()
        payloads = []
        if stripped.startswith(("{", "[")):
            try:
                payloads.append(json.loads(stripped))
            except json.JSONDecodeError:
                pass

        for var_name in ("identifyApplyData", "secondCreditData", "data", "rows", "items"):
            pattern = re.compile(rf"{var_name}\s*=\s*(\[.*?\]|\{{.*?\}})\s*;", re.S)
            for match in pattern.finditer(text or ""):
                try:
                    payloads.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    continue

        for payload in payloads:
            for items in self._second_credit_items_from_payload(payload):
                normalized = self._normalize_second_credits(items)
                if normalized:
                    return normalized
        return []

    def _second_credit_items_from_payload(self, payload) -> list[list[dict]]:
        if isinstance(payload, list):
            dict_items = [item for item in payload if isinstance(item, dict)]
            return [dict_items] if dict_items else []
        if not isinstance(payload, dict):
            return []

        found = []
        for key in ("identifyApplyList", "secondCredits", "credits", "data", "result", "rows", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                dict_items = [item for item in value if isinstance(item, dict)]
                if dict_items:
                    found.append(dict_items)
            elif isinstance(value, dict):
                found.extend(self._second_credit_items_from_payload(value))
        if not found:
            for value in payload.values():
                if isinstance(value, (dict, list)):
                    found.extend(self._second_credit_items_from_payload(value))
        return found

    def _parse_second_credits_from_table(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html or "", "html.parser")
        table = soup.find("table", id=re.compile(r"identifyApply", re.I))
        if table is None:
            table = soup.find("table", class_=re.compile(r"gridtable", re.I))
        if table is None:
            return []

        headers = [self._clean_text(cell.get_text(" ", strip=True)) for cell in table.find_all("th")]
        records = []
        for row in table.find_all("tr"):
            cells = [self._clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
            if len(cells) < 5:
                continue
            record = self._second_credit_from_cells(headers, cells)
            if record.get("name"):
                records.append(record)
        return records

    def _second_credit_from_cells(self, headers: list[str], cells: list[str]) -> dict:
        if headers and len(headers) == len(cells):
            mapped = dict(zip(headers, cells))
        elif len(cells) >= 10:
            mapped = {
                "学年学期": cells[1],
                "项目分类": cells[2],
                "项目子类": cells[3],
                "具体名称": cells[4],
                "标签1": cells[5],
                "标签2": cells[6],
                "申请类型": cells[7],
                "学分": cells[8],
                "审核状态": cells[9],
            }
        else:
            mapped = {}

        return {
            "semester": self._first_value(mapped, "学年学期", "semester", "term"),
            "category": self._first_value(mapped, "项目分类", "category", "classification"),
            "subcategory": self._first_value(mapped, "项目子类", "subcategory", "subclass"),
            "name": self._first_value(mapped, "具体名称", "name", "title", "activityName"),
            "label1": self._first_value(mapped, "标签1", "label1"),
            "label2": self._first_value(mapped, "标签2", "label2"),
            "apply_type": self._first_value(mapped, "申请类型", "apply_type", "applyType"),
            "credit": self._parse_credit_value(self._first_value(mapped, "学分", "credit", "credits", "score")),
            "status": self._normalize_second_credit_status(
                self._first_value(mapped, "审核状态", "status", "state", "auditStatus")
            ),
        }

    def _normalize_second_credits(self, data: list[dict]) -> list[dict]:
        normalized = []
        for item in data or []:
            if not isinstance(item, dict):
                continue
            name = self._first_value(item, "name", "title", "activityName", "projectName", "具体名称")
            record = {
                "semester": self._first_value(item, "semester", "term", "schoolTerm", "学年学期"),
                "category": self._first_value(item, "category", "classification", "className", "项目分类"),
                "subcategory": self._first_value(item, "subcategory", "subclass", "subclassName", "项目子类"),
                "name": name,
                "label1": self._first_value(item, "label1", "tag1", "标签1"),
                "label2": self._first_value(item, "label2", "tag2", "标签2"),
                "apply_type": self._first_value(item, "apply_type", "applyType", "申请类型"),
                "credit": self._parse_credit_value(self._first_value(item, "credit", "credits", "score", "学分")),
                "status": self._normalize_second_credit_status(
                    self._first_value(item, "status", "state", "auditStatus", "审核状态")
                ),
            }
            if record["name"]:
                normalized.append(record)
        return normalized

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _parse_credit_value(value) -> float:
        match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
        return float(match.group(0)) if match else 0.0

    @staticmethod
    def _normalize_second_credit_status(value: str) -> str:
        text = re.sub(r"\s+", "", str(value or ""))
        if any(word in text for word in ("未通过", "不通过", "驳回", "退回", "失败")):
            return "未通过"
        if any(word in text for word in ("待", "审核中", "未提交", "申请中")):
            return "待审核"
        if any(word in text for word in ("通过", "已审核", "完成", "已认定")):
            return "已通过"
        return text or "待审核"

    @staticmethod
    def _first_value(item: dict, *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, dict):
                for nested_key in ("name", "text", "value"):
                    nested = value.get(nested_key)
                    if nested:
                        return str(nested).strip()
                continue
            if isinstance(value, (list, tuple)):
                value = " ".join(str(part) for part in value if part is not None)
            return str(value).strip()
        return ""

    def check_connectivity(self) -> bool:
        """Check whether the EAMS home page is reachable."""
        try:
            resp = self.session.get(f"{EAMS_BASE_URL}/index.action", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _filter_recent_semesters(semesters: list[dict]) -> list[dict]:
        recent = []
        for item in semesters or []:
            name = str(item.get("name") or "")
            match = re.search(r"(20\d{2})\s*-\s*(20\d{2})", name)
            if not match or int(match.group(1)) >= 2021:
                recent.append(item)
        return recent

    def get_semesters(self) -> list[dict]:
        """Fetch available semester options."""
        try:
            resp = self.session.get(COURSE_TABLE_URL, timeout=15)
            resp.encoding = "utf-8"
        except requests.RequestException:
            return []

        html = resp.text
        semesters = self._parse_semesters_from_html(html)
        if semesters:
            return self._filter_recent_semesters(semesters)

        tag_match = re.search(r'id=["\']([^"\']*Semester)["\']', html)
        value_match = re.search(r'semesterCalendar\(\{[^}]*value\s*:\s*["\']?(\d+)', html)
        tag_id = tag_match.group(1) if tag_match else ""
        value = value_match.group(1) if value_match else ""

        try:
            cal_resp = self.session.post(
                SEMESTER_DATA_URL,
                data={
                    "tagId": tag_id,
                    "dataType": "semesterCalendar",
                    "value": value,
                    "empty": "false",
                },
                timeout=15,
            )
            cal_resp.encoding = "utf-8"
        except requests.RequestException:
            return []

        return self._filter_recent_semesters(self._parse_semesters_from_calendar(cal_resp.text))

    def _parse_semesters_from_html(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        semesters: list[dict] = []
        seen: set[str] = set()
        selects = soup.find_all(
            "select",
            attrs={
                "id": re.compile(r"semester|term|schoolYear", re.I),
            },
        )
        selects += soup.find_all(
            "select",
            attrs={
                "name": re.compile(r"semester|term|schoolYear", re.I),
            },
        )
        for select in selects:
            for option in select.find_all("option"):
                value = option.get("value", "").strip()
                name = option.get_text(" ", strip=True) or value
                if value and value not in seen:
                    seen.add(value)
                    semesters.append({
                        "id": value,
                        "name": name,
                    })
        return semesters

    @staticmethod
    def _parse_semesters_from_calendar(text: str) -> list[dict]:
        semesters: list[dict] = []
        seen: set[str] = set()
        pattern = re.compile(
            r'id\s*:\s*(\d+)\s*,\s*schoolYear\s*:\s*"([^"]+)"\s*,\s*name\s*:\s*"([^"]+)"',
            re.I,
        )
        for semester_id, school_year, term_name in pattern.findall(text or ""):
            if semester_id in seen:
                continue
            seen.add(semester_id)
            semesters.append({
                "id": semester_id,
                "name": f"{school_year} 第{term_name}学期",
            })
        semesters.sort(key=lambda item: int(item["id"]), reverse=True)
        return semesters

    @staticmethod
    @staticmethod
    def _parse_weeks_str(weeks_str: str) -> list[int]:
        """Parse week expressions like 1,2,3,6-10,1-15单周."""
        weeks = []
        for part in str(weeks_str or "").split(","):
            part = part.strip()
            if not part:
                continue
            span = re.match(r"(\d+)\s*[-–—~至]\s*(\d+)\s*(单周|双周)?", part)
            if span:
                start, end = int(span.group(1)), int(span.group(2))
                span_weeks = list(range(start, end + 1))
                if span.group(3) == "单周":
                    span_weeks = [week for week in span_weeks if week % 2 == 1]
                elif span.group(3) == "双周":
                    span_weeks = [week for week in span_weeks if week % 2 == 0]
                weeks.extend(span_weeks)
            else:
                try:
                    weeks.append(int(part))
                except ValueError:
                    continue
        return sorted(set(weeks))
        return sorted(set(weeks))
