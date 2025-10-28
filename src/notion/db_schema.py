"""Notion 데이터베이스 스키마 정의"""

from typing import Dict, Any


def get_work_log_schema() -> Dict[str, Any]:
  """업무일지 DB 추가 속성 스키마"""
  return {
    "정량적성과": {
      "rich_text": {}
    },
    "성과타입": {
      "select": {
        "options": [
          {"name": "개발", "color": "blue"},
          {"name": "리뷰", "color": "purple"},
          {"name": "회의", "color": "green"},
          {"name": "학습", "color": "yellow"},
          {"name": "기타", "color": "gray"}
        ]
      }
    },
    "기술스택": {
      "multi_select": {
        "options": [
          {"name": "Python", "color": "blue"},
          {"name": "JavaScript", "color": "yellow"},
          {"name": "TypeScript", "color": "blue"},
          {"name": "React", "color": "blue"},
          {"name": "Kotlin", "color": "purple"},
          {"name": "Spring Boot", "color": "green"},
          {"name": "PostgreSQL", "color": "blue"},
          {"name": "Redis", "color": "red"},
          {"name": "Docker", "color": "blue"},
          {"name": "AWS", "color": "orange"},
          {"name": "Git", "color": "gray"}
        ]
      }
    },
    "이력서반영": {
      "select": {
        "options": [
          {"name": "예", "color": "green"},
          {"name": "아니오", "color": "gray"}
        ]
      }
    },
    "AI 생성 완료": {
      "select": {
        "options": [
          {"name": "완료", "color": "green"},
          {"name": "미완료", "color": "gray"}
        ]
      }
    }
  }


def get_weekly_report_schema() -> Dict[str, Any]:
  """
  주간 리포트 DB 스키마 (title 속성 제외)

  Note: 주간 리포트는 마크다운 형식으로 본문에 작성되므로 추가 속성이 필요하지 않습니다.
        Title 속성만 사용하며, 이는 DB 생성 시 자동으로 생성됩니다.
  """
  return {}


def get_monthly_report_schema() -> Dict[str, Any]:
  """
  월간 리포트 DB 스키마 (title 속성 제외)

  Note: 월간 리포트는 마크다운 형식으로 본문에 작성되므로 추가 속성이 필요하지 않습니다.
        Title 속성만 사용하며, 이는 DB 생성 시 자동으로 생성됩니다.
  """
  return {}
