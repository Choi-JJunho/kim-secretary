#!/usr/bin/env python3
"""카페24 PM 이력서 평가 테스트 스크립트"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.resume_evaluator.workflow_cafe24 import Cafe24EvaluationWorkflow, Cafe24WorkflowConfig


async def test_workflow_initialization():
    """워크플로우 초기화 테스트"""
    print("=" * 60)
    print("📊 카페24 PM 이력서 평가 워크플로우 초기화 테스트")
    print("=" * 60)

    config = Cafe24WorkflowConfig(ai_provider="claude")
    workflow = Cafe24EvaluationWorkflow(config)

    success = await workflow.initialize()

    if success:
        print("\n✅ 워크플로우 초기화 성공")
        status = workflow.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
    else:
        print("\n❌ 워크플로우 초기화 실패")

    return workflow if success else None


async def test_resume_evaluation(workflow=None, resume_path=None):
    """이력서 평가 테스트"""
    print()
    print("=" * 60)
    print("📋 카페24 PM 이력서 평가 테스트")
    print("=" * 60)

    # 이력서 파일 경로 결정
    if not resume_path:
        # 기본 테스트 파일 찾기
        default_paths = [
            project_root / "juno_resume.pdf",
            project_root / "최준호_이력서.pdf",
            project_root / "resume.pdf",
        ]
        for path in default_paths:
            if path.exists():
                resume_path = path
                break

    if not resume_path or not Path(resume_path).exists():
        print("❌ 테스트용 이력서 PDF 파일을 찾을 수 없습니다.")
        print("   다음 경로에 PDF 파일을 추가하세요:")
        print("   - juno_resume.pdf")
        print("   - 최준호_이력서.pdf")
        return None

    print(f"📄 이력서 파일: {resume_path}")

    # 워크플로우가 없으면 초기화
    if not workflow:
        config = Cafe24WorkflowConfig(ai_provider="claude")
        workflow = Cafe24EvaluationWorkflow(config)
        await workflow.initialize()

    print()
    print("🔍 이력서 평가 중...")

    try:
        result = await workflow.evaluate_resume_file(str(resume_path), "PM")

        print()
        print("-" * 60)
        print("📊 평가 결과")
        print("-" * 60)
        print(workflow.format_result(result))

        return result

    except Exception as e:
        print(f"\n❌ 평가 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """테스트 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    # 1. 워크플로우 초기화 테스트
    workflow = await test_workflow_initialization()

    # 2. 이력서 평가 테스트 (명령줄 인자로 파일 경로 지정 가능)
    resume_path = sys.argv[1] if len(sys.argv) > 1 else None
    if resume_path or workflow:
        await test_resume_evaluation(workflow, resume_path)


if __name__ == "__main__":
    asyncio.run(main())
