"""AI 프롬프트 로딩 유틸리티"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 프롬프트 디렉토리 경로
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(prompt_name: str, default: str = "") -> str:
  """
  프롬프트 파일을 로드합니다.

  Args:
      prompt_name: 프롬프트 파일명 (확장자 제외 또는 포함)
                   예: "weekly_report_analysis" 또는 "weekly_report_analysis.txt"
      default: 파일을 찾지 못했을 때 반환할 기본값

  Returns:
      프롬프트 텍스트 또는 기본값

  Example:
      >>> prompt = load_prompt("weekly_report_analysis")
      >>> prompt = load_prompt("custom_prompt.txt", default="기본 프롬프트")
  """
  # 확장자가 없으면 .txt 추가
  if not prompt_name.endswith(".txt"):
    prompt_name = f"{prompt_name}.txt"

  prompt_file = PROMPTS_DIR / prompt_name

  try:
    with open(prompt_file, "r", encoding="utf-8") as f:
      content = f.read()
      logger.info(f"✅ Prompt loaded: {prompt_name} ({len(content)} chars)")
      return content
  except FileNotFoundError:
    logger.warning(
        f"⚠️ Prompt file not found: {prompt_file}, using default")
    return default
  except Exception as e:
    logger.error(f"❌ Failed to load prompt {prompt_name}: {e}")
    return default


def load_prompt_with_variables(
    prompt_name: str,
    variables: dict,
    default: str = ""
) -> str:
  """
  프롬프트 파일을 로드하고 변수를 치환합니다.

  Args:
      prompt_name: 프롬프트 파일명
      variables: 치환할 변수 딕셔너리 {변수명: 값}
      default: 파일을 찾지 못했을 때 반환할 기본값

  Returns:
      변수가 치환된 프롬프트 텍스트

  Example:
      >>> prompt = load_prompt_with_variables(
      ...     "weekly_report_analysis",
      ...     {"work_logs": "업무일지 내용", "resume_content": "이력서"}
      ... )
  """
  template = load_prompt(prompt_name, default)

  if not template:
    return default

  try:
    for key, value in variables.items():
      placeholder = f"{{{key}}}"
      template = template.replace(placeholder, str(value))

    return template
  except Exception as e:
    logger.error(f"❌ Failed to substitute variables in prompt: {e}")
    return template
