#!/usr/bin/env python3
"""원티드 채용공고 스크래퍼 테스트 스크립트

사용법:
    python scripts/test_wanted_scraper.py [--scrape] [--max-jobs N] [--categories CAT1,CAT2]

예시:
    # 기본 테스트 (스크래핑 없이 캐시된 데이터 사용)
    python scripts/test_wanted_scraper.py

    # 새로 스크래핑
    python scripts/test_wanted_scraper.py --scrape

    # 최대 10개 공고만 스크래핑
    python scripts/test_wanted_scraper.py --scrape --max-jobs 10

    # 특정 직군만 스크래핑
    python scripts/test_wanted_scraper.py --scrape --categories backend,devops
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resume_evaluator import (
    WantedJobScraper,
    WantedJobCategory,
    WantedPromptGenerator,
    WantedEvaluationWorkflow,
    WantedWorkflowConfig,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# 카테고리 이름 매핑
CATEGORY_MAP = {
    "backend": WantedJobCategory.BACKEND,
    "frontend": WantedJobCategory.FRONTEND,
    "fullstack": WantedJobCategory.FULLSTACK,
    "devops": WantedJobCategory.DEVOPS,
    "java": WantedJobCategory.JAVA,
    "python": WantedJobCategory.PYTHON,
    "ios": WantedJobCategory.APP_IOS,
    "android": WantedJobCategory.APP_ANDROID,
    "data": WantedJobCategory.DATA_ENGINEER,
    "ml": WantedJobCategory.ML_ENGINEER,
    "qa": WantedJobCategory.QA,
    "security": WantedJobCategory.SECURITY,
}


async def test_scraper(max_jobs: int = 5, categories: list[WantedJobCategory] | None = None):
    """스크래퍼 테스트"""
    print("\n" + "=" * 60)
    print("🧪 원티드 스크래퍼 테스트")
    print("=" * 60)

    if categories is None:
        categories = [WantedJobCategory.BACKEND, WantedJobCategory.JAVA]

    scraper = WantedJobScraper()

    print(f"\n📋 스크래핑 직군: {', '.join(c.value for c in categories)}")
    print(f"📋 최대 공고 수: {max_jobs}")

    data = await scraper.scrape_positions_by_category(
        categories=categories,
        headless=True,
        max_jobs=max_jobs,
        years_min=0,
        years_max=3,
    )

    print(f"\n✅ 스크래핑 완료: {len(data.positions)}개 포지션")

    # 기업별 통계
    companies = {}
    for pos in data.positions:
        company = pos.company or "Unknown"
        companies[company] = companies.get(company, 0) + 1

    print("\n📊 기업별 포지션 수:")
    for company, count in sorted(companies.items(), key=lambda x: -x[1])[:10]:
        print(f"  - {company}: {count}개")

    # 샘플 포지션 출력
    print("\n📄 샘플 포지션:")
    for pos in data.positions[:3]:
        print(f"\n  📌 {pos.title}")
        print(f"     회사: {pos.company}")
        print(f"     URL: {pos.detail_url}")
        print(f"     자격요건: {len(pos.requirements)}개")
        if pos.requirements:
            for req in pos.requirements[:3]:
                print(f"       - {req[:60]}...")
        print(f"     기술스택: {', '.join(pos.tech_stack[:5]) if pos.tech_stack else '없음'}")

    # 데이터 저장
    scraper.save_scraped_data(data)
    print(f"\n💾 데이터 저장 완료")

    return data


async def test_prompt_generator(scraped_data=None):
    """프롬프트 생성기 테스트"""
    print("\n" + "=" * 60)
    print("🧪 프롬프트 생성기 테스트")
    print("=" * 60)

    generator = WantedPromptGenerator()

    if scraped_data is None:
        # 캐시된 데이터 로드
        scraper = WantedJobScraper()
        scraped_data = scraper.load_scraped_data()

        if not scraped_data:
            print("❌ 스크래핑된 데이터가 없습니다. --scrape 옵션으로 먼저 스크래핑하세요.")
            return None

    # 프롬프트 생성
    prompt = generator.generate_system_prompt(
        scraped_data,
        target_position="Backend Developer"
    )

    print(f"\n✅ 프롬프트 생성 완료")
    print(f"   - 길이: {len(prompt.prompt)}자")
    print(f"   - 소스 해시: {prompt.source_hash}")

    # 프롬프트 미리보기
    print("\n📄 프롬프트 미리보기 (처음 500자):")
    print("-" * 40)
    print(prompt.prompt[:500])
    print("...")
    print("-" * 40)

    # 저장
    generator.save_prompt(prompt)
    print(f"\n💾 프롬프트 저장 완료")

    return prompt


async def test_workflow():
    """워크플로우 테스트 (초기화만)"""
    print("\n" + "=" * 60)
    print("🧪 워크플로우 초기화 테스트")
    print("=" * 60)

    config = WantedWorkflowConfig(
        ai_provider="claude",
        force_scrape=False,
        headless=True,
        max_jobs=5,
    )

    workflow = WantedEvaluationWorkflow(config)

    success = await workflow.initialize(
        categories=[WantedJobCategory.BACKEND, WantedJobCategory.JAVA]
    )

    if success:
        print("\n✅ 워크플로우 초기화 성공")
        status = workflow.get_status()
        print("\n📊 워크플로우 상태:")
        for key, value in status.items():
            print(f"  {key}: {value}")
    else:
        print("\n❌ 워크플로우 초기화 실패")

    return workflow


async def main():
    parser = argparse.ArgumentParser(description="원티드 스크래퍼 테스트")
    parser.add_argument("--scrape", action="store_true", help="새로 스크래핑 수행")
    parser.add_argument("--max-jobs", type=int, default=5, help="최대 스크래핑할 공고 수")
    parser.add_argument("--categories", type=str, default="backend,java",
                        help="스크래핑할 직군 (쉼표로 구분)")
    parser.add_argument("--workflow", action="store_true", help="워크플로우 테스트")

    args = parser.parse_args()

    # 카테고리 파싱
    category_names = [c.strip().lower() for c in args.categories.split(",")]
    categories = []
    for name in category_names:
        if name in CATEGORY_MAP:
            categories.append(CATEGORY_MAP[name])
        else:
            print(f"⚠️ 알 수 없는 카테고리: {name}")
            print(f"   사용 가능: {', '.join(CATEGORY_MAP.keys())}")

    if not categories:
        categories = [WantedJobCategory.BACKEND, WantedJobCategory.JAVA]

    scraped_data = None

    if args.scrape:
        scraped_data = await test_scraper(max_jobs=args.max_jobs, categories=categories)

    await test_prompt_generator(scraped_data)

    if args.workflow:
        await test_workflow()

    print("\n" + "=" * 60)
    print("✅ 모든 테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
