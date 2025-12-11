#!/usr/bin/env python3
"""이력서 평가 테스트 스크립트"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.resume_evaluator.workflow import ResumeEvaluationWorkflow, WorkflowConfig


async def main():
    """테스트 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    # PDF 파일 경로
    pdf_path = project_root / "juno_resume.pdf"

    if not pdf_path.exists():
        print(f"❌ PDF 파일을 찾을 수 없습니다: {pdf_path}")
        return

    print(f"📄 이력서 파일: {pdf_path}")
    print()

    # 워크플로우 설정
    config = WorkflowConfig(
        ai_provider="claude",
    )

    workflow = ResumeEvaluationWorkflow(config)

    # 시스템 프롬프트 로드 시도
    try:
        workflow.evaluator.load_system_prompt_from_file()
        workflow._initialized = True
        print("✅ 시스템 프롬프트 로드 완료")
    except FileNotFoundError:
        print("⚠️ 시스템 프롬프트가 없습니다. 워크플로우 초기화를 수행합니다...")
        await workflow.initialize()

    print()
    print("🔍 이력서 평가 중...")
    print()

    # 이력서 평가
    result = await workflow.evaluate_resume_file(str(pdf_path), "Server Developer")

    # 결과 출력
    print(workflow.format_result(result))

    return result


if __name__ == "__main__":
    asyncio.run(main())
