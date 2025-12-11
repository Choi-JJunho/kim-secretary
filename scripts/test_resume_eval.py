#!/usr/bin/env python3
"""이력서 평가 테스트 스크립트 (직군 분류 포함)"""

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


async def test_classification_only():
    """직군 분류만 테스트"""
    print("=" * 60)
    print("📊 직군 분류 테스트")
    print("=" * 60)

    pdf_path = project_root / "최준호_이력서.pdf"
    if not pdf_path.exists():
        pdf_path = project_root / "juno_resume.pdf"

    if not pdf_path.exists():
        print(f"❌ PDF 파일을 찾을 수 없습니다")
        return None

    print(f"📄 이력서 파일: {pdf_path}")

    config = WorkflowConfig(ai_provider="claude")
    workflow = ResumeEvaluationWorkflow(config)

    # 직군 분류
    classification = await workflow.classify_resume_file(str(pdf_path))

    print()
    print(f"🎯 추천 직군: {classification.primary_category.value}")
    print(f"📊 신뢰도: {classification.confidence:.0%}")
    print(f"💡 분류 근거: {classification.reasoning}")

    if classification.secondary_categories:
        secondary = ", ".join([c.value for c in classification.secondary_categories])
        print(f"📋 추가 추천: {secondary}")

    if classification.skills_detected:
        skills = ", ".join(classification.skills_detected[:10])
        print(f"🛠️ 감지된 기술: {skills}")

    if classification.experience_years:
        print(f"📅 추정 경력: {classification.experience_years}년")

    return classification


async def test_full_workflow():
    """직군 분류 + 평가 전체 워크플로우 테스트"""
    print()
    print("=" * 60)
    print("🔄 전체 워크플로우 테스트 (직군 분류 → 평가)")
    print("=" * 60)

    pdf_path = project_root / "최준호_이력서.pdf"
    if not pdf_path.exists():
        pdf_path = project_root / "juno_resume.pdf"

    if not pdf_path.exists():
        print(f"❌ PDF 파일을 찾을 수 없습니다")
        return None

    print(f"📄 이력서 파일: {pdf_path}")

    config = WorkflowConfig(ai_provider="claude")
    workflow = ResumeEvaluationWorkflow(config)

    print()
    print("🔍 직군 분류 + 평가 진행 중...")

    # 직군 분류 + 평가
    result = await workflow.evaluate_with_classification(str(pdf_path))

    # 분류 결과
    print()
    print("-" * 60)
    print("📊 직군 분류 결과")
    print("-" * 60)
    print(f"🎯 추천 직군: {result.classification.primary_category.value}")
    print(f"📊 신뢰도: {result.classification.confidence:.0%}")

    if result.recommended_job_urls:
        print(f"🔗 추천 채용공고:")
        for url in result.recommended_job_urls:
            print(f"   - {url}")

    # 평가 결과
    print()
    print("-" * 60)
    print("📋 평가 결과")
    print("-" * 60)
    print(workflow.format_result(result.evaluation))

    return result


async def test_legacy_workflow():
    """기존 워크플로우 테스트 (레거시)"""
    print()
    print("=" * 60)
    print("📋 기존 워크플로우 테스트 (레거시)")
    print("=" * 60)

    pdf_path = project_root / "최준호_이력서.pdf"
    if not pdf_path.exists():
        pdf_path = project_root / "juno_resume.pdf"

    if not pdf_path.exists():
        print(f"❌ PDF 파일을 찾을 수 없습니다")
        return None

    print(f"📄 이력서 파일: {pdf_path}")

    config = WorkflowConfig(ai_provider="claude")
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

    result = await workflow.evaluate_resume_file(str(pdf_path), "Server Developer")
    print(workflow.format_result(result))

    return result


async def main():
    """테스트 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    # 1. 직군 분류만 테스트
    await test_classification_only()

    # 2. 전체 워크플로우 테스트 (직군 분류 → 평가)
    await test_full_workflow()


if __name__ == "__main__":
    asyncio.run(main())
