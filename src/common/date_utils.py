"""날짜 및 주차 처리 유틸리티"""

from datetime import datetime, timedelta
from typing import List, Tuple
import pytz

KST = pytz.timezone('Asia/Seoul')


def get_week_info(date: datetime) -> Tuple[int, int]:
  """
  날짜에서 ISO 주차 정보를 추출합니다.

  Args:
      date: 날짜 객체

  Returns:
      (year, week) 튜플

  Example:
      >>> date = datetime(2025, 1, 15)
      >>> get_week_info(date)
      (2025, 3)
  """
  iso_calendar = date.isocalendar()
  return iso_calendar[0], iso_calendar[1]


def get_week_date_range(year: int, week: int) -> Tuple[datetime, datetime]:
  """
  ISO 주차의 시작일과 종료일을 반환합니다.

  Args:
      year: 연도
      week: 주차 (ISO week)

  Returns:
      (start_date, end_date) 튜플

  Example:
      >>> get_week_date_range(2025, 3)
      (datetime(2025, 1, 13), datetime(2025, 1, 19))
  """
  # ISO week의 첫 번째 날은 월요일
  jan_4 = datetime(year, 1, 4, tzinfo=KST)
  week_1_monday = jan_4 - timedelta(days=jan_4.weekday())

  # 목표 주차의 월요일
  target_monday = week_1_monday + timedelta(weeks=week - 1)
  target_sunday = target_monday + timedelta(days=6)

  return target_monday, target_sunday


def format_week_string(year: int, week: int) -> str:
  """
  주차를 문자열로 포맷팅합니다.

  Args:
      year: 연도
      week: 주차

  Returns:
      포맷팅된 문자열 (예: "2025-W03")

  Example:
      >>> format_week_string(2025, 3)
      '2025-W03'
  """
  return f"{year}-W{week:02d}"


def parse_week_string(week_str: str) -> Tuple[int, int]:
  """
  주차 문자열을 파싱합니다.

  Args:
      week_str: 주차 문자열 (예: "2025-W03")

  Returns:
      (year, week) 튜플

  Example:
      >>> parse_week_string("2025-W03")
      (2025, 3)
  """
  parts = week_str.split('-W')
  return int(parts[0]), int(parts[1])


def group_dates_by_week(dates: List[str]) -> dict:
  """
  날짜 리스트를 주차별로 그룹화합니다.

  Args:
      dates: ISO 형식의 날짜 문자열 리스트 (YYYY-MM-DD)

  Returns:
      주차를 키로 하고 날짜 리스트를 값으로 하는 딕셔너리
      키 형식: "2025-W03"

  Example:
      >>> dates = ["2025-01-13", "2025-01-14", "2025-01-20"]
      >>> group_dates_by_week(dates)
      {'2025-W03': ['2025-01-13', '2025-01-14'], '2025-W04': ['2025-01-20']}
  """
  weeks = {}

  for date_str in dates:
    try:
      date = datetime.fromisoformat(date_str)
      year, week = get_week_info(date)
      week_key = format_week_string(year, week)

      if week_key not in weeks:
        weeks[week_key] = []
      weeks[week_key].append(date_str)
    except (ValueError, IndexError) as e:
      # Skip invalid dates
      continue

  return weeks


def get_weeks_in_range(
    start_date: datetime,
    end_date: datetime
) -> List[Tuple[int, int]]:
  """
  시작일과 종료일 사이의 모든 주차를 반환합니다.

  Args:
      start_date: 시작 날짜
      end_date: 종료 날짜

  Returns:
      (year, week) 튜플 리스트

  Example:
      >>> start = datetime(2025, 1, 13)
      >>> end = datetime(2025, 1, 27)
      >>> get_weeks_in_range(start, end)
      [(2025, 3), (2025, 4)]
  """
  weeks = []
  current = start_date

  while current <= end_date:
    year, week = get_week_info(current)
    week_tuple = (year, week)

    if not weeks or weeks[-1] != week_tuple:
      weeks.append(week_tuple)

    # Move to next week
    current += timedelta(weeks=1)

  return weeks
