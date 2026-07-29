"""数据模型 — 课表 & 成绩"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Course:
    """单节课"""
    name: str              # 课程名称
    teacher: str           # 教师
    location: str          # 教室 / 地点
    day_of_week: int       # 星期几 (1=周一 .. 7=周日)
    start_slot: int        # 起始节次 (1-based)
    end_slot: int          # 结束节次
    weeks: list[int] = field(default_factory=list)  # 上课周次 [1,2,...,18]
    note: str = ""


@dataclass
class Grade:
    """单科成绩"""
    semester: str          # 学年学期, e.g. "2025-2026-1"
    course_name: str       # 课程名称
    credit: float          # 学分
    score: str             # 成绩（可能是 "优秀"/"92"/"通过" 等）
    gpa: float = 0.0       # 绩点
    exam_type: str = ""    # 考试类型（正常/补考/重修）
    is_passed: bool = True


@dataclass
class GradeSummary:
    """成绩汇总"""
    grades: list[Grade] = field(default_factory=list)
    total_credits: float = 0.0      # 总修学分
    weighted_sum: float = 0.0       # 加权分数和
    overall_gpa: float = 0.0        # 总绩点
    updated_at: Optional[datetime] = None
