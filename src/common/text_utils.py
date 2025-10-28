"""텍스트 처리 유틸리티"""

from typing import Optional


def truncate_text(
    text: str,
    max_length: int,
    suffix: str = "...",
    show_total: bool = False
) -> str:
  """
  텍스트를 지정된 길이로 자르고 생략 표시를 추가합니다.

  Args:
      text: 원본 텍스트
      max_length: 최대 길이
      suffix: 생략 표시 (기본값: "...")
      show_total: 전체 길이를 표시할지 여부

  Returns:
      잘린 텍스트

  Example:
      >>> truncate_text("긴 텍스트입니다" * 100, 50)
      "긴 텍스트입니다긴 텍스트입니다긴 텍스트입니다긴 텍스트입니다..."
      >>> truncate_text("긴 텍스트", 50, show_total=True)
      "긴 텍스트 (총 10자)"
  """
  if len(text) <= max_length:
    if show_total:
      return f"{text} (총 {len(text)}자)"
    return text

  truncated = text[:max_length]

  if show_total:
    return f"{truncated}{suffix}\n\n(총 {len(text)}자)\n"

  return f"{truncated}{suffix}"


def create_preview(
    text: str,
    preview_length: int = 1000,
    show_total: bool = True
) -> str:
  """
  텍스트의 미리보기를 생성합니다.

  Args:
      text: 원본 텍스트
      preview_length: 미리보기 길이 (기본값: 1000)
      show_total: 전체 길이 표시 여부 (기본값: True)

  Returns:
      미리보기 텍스트

  Example:
      >>> preview = create_preview("매우 긴 텍스트...", 100)
      "매우 긴 텍스트...\n\n(총 XXX자)\n"
  """
  return truncate_text(
      text,
      max_length=preview_length,
      suffix="...",
      show_total=show_total
  )


def split_by_lines(
    text: str,
    max_lines: int,
    separator: str = "\n"
) -> str:
  """
  텍스트를 지정된 줄 수로 자릅니다.

  Args:
      text: 원본 텍스트
      max_lines: 최대 줄 수
      separator: 줄 구분자

  Returns:
      잘린 텍스트

  Example:
      >>> text = "1\\n2\\n3\\n4\\n5"
      >>> split_by_lines(text, 3)
      "1\\n2\\n3"
  """
  lines = text.split(separator)
  if len(lines) <= max_lines:
    return text

  return separator.join(lines[:max_lines])
