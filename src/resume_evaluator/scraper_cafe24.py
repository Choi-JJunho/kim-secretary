"""카페24 채용공고 스크래퍼 (Playwright 기반) - 동적 탐색"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page

from .models import JobRequirement, ScrapedData, PositionCategory, Cafe24JobCategory

logger = logging.getLogger(__name__)


class Cafe24JobScraper:
    """카페24 채용공고 스크래퍼 - 동적 탐색"""

    BASE_URL = "https://www.cafe24corp.com/recruit/jobs"

    def __init__(self, data_dir: str = "data/resume_evaluator/cafe24"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_data_path = self.data_dir / "scraped_positions.json"

    async def _goto_next_page(self, page: Page, next_page_num: int) -> bool:
        """다음 페이지로 이동"""
        try:
            next_link = page.locator(f'ul.paging li a:has-text("{next_page_num}")')
            if await next_link.count() > 0:
                await next_link.click()
                await page.wait_for_timeout(1500)
                return True
            return False
        except Exception:
            return False

    async def scrape_positions_by_category(
        self,
        category: Cafe24JobCategory,
        headless: bool = True,
        max_jobs: int = 10
    ) -> ScrapedData:
        """특정 직군의 포지션 스크래핑 (동적 탐색)

        Args:
            category: 직군 카테고리
            headless: 헤드리스 모드 여부
            max_jobs: 최대 스크래핑할 공고 수

        Returns:
            ScrapedData: 스크래핑된 데이터
        """
        logger.info(f"🚀 카페24 {category.value} 포지션 스크래핑 시작...")

        positions = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            try:
                # 채용 목록 페이지로 이동
                await page.goto(self.BASE_URL)
                await page.wait_for_timeout(2000)

                # 모든 페이지를 순회하며 스크래핑
                category_filter = category.value if category != Cafe24JobCategory.ALL else None
                page_num = 1
                scraped_count = 0

                while scraped_count < max_jobs:
                    logger.info(f"📄 페이지 {page_num} 스크래핑 중...")

                    # 현재 페이지에서 해당 카테고리 공고 스크래핑
                    page_positions = await self._scrape_page_positions_with_details(
                        page, category_filter, max_jobs - scraped_count
                    )
                    positions.extend(page_positions)
                    scraped_count += len(page_positions)

                    if scraped_count >= max_jobs:
                        break

                    # 다음 페이지로 이동
                    if not await self._goto_next_page(page, page_num + 1):
                        break
                    page_num += 1
                    await page.wait_for_timeout(1000)

            except Exception as e:
                logger.error(f"❌ 스크래핑 실패: {e}")
            finally:
                await browser.close()

        scraped_data = ScrapedData(
            positions=positions,
            scraped_at=datetime.now(),
            source_url=f"{self.BASE_URL}?category={category.value}",
        )

        logger.info(f"✅ 총 {len(positions)}개 {category.value} 포지션 스크래핑 완료")
        return scraped_data

    async def _scrape_page_positions_with_details(
        self,
        page: Page,
        category_filter: Optional[str],
        max_count: int
    ) -> list[JobRequirement]:
        """현재 페이지에서 공고 목록과 상세 정보를 함께 스크래핑

        Args:
            page: Playwright Page 객체
            category_filter: 필터링할 카테고리 (None이면 전체)
            max_count: 최대 스크래핑할 공고 수

        Returns:
            JobRequirement 리스트
        """
        # JavaScript로 현재 페이지의 모든 공고 정보 추출 (상세 정보 포함)
        data = await page.evaluate("""
            (categoryFilter) => {
                const allRows = document.querySelectorAll('table tbody tr');
                const jobs = [];

                for (let i = 0; i < allRows.length; i += 2) {
                    const jobRow = allRows[i];
                    const detailRow = allRows[i + 1];

                    if (!jobRow || !detailRow) continue;
                    if (!detailRow.classList.contains('fieldDetail')) continue;

                    const cells = jobRow.querySelectorAll('td');
                    if (cells.length < 3) continue;

                    const jobCategory = cells[0]?.textContent?.trim();
                    const title = cells[1]?.textContent?.trim();

                    // 카테고리 필터링
                    if (categoryFilter && jobCategory !== categoryFilter) continue;

                    const detailText = detailRow.querySelector('td')?.textContent || '';

                    // 섹션별 파싱
                    const parseSection = (text, sectionName) => {
                        const regex = new RegExp('■\\\\s*' + sectionName + '([\\\\s\\\\S]*?)(?=■|$)');
                        const match = text.match(regex);
                        if (!match) return [];

                        return match[1]
                            .split(/\\n/)
                            .map(s => s.replace(/^\\s*-\\s*/, '').trim())
                            .filter(s => s && s.length > 2 && !s.startsWith('■') && !s.includes('지원하기'));
                    };

                    jobs.push({
                        category: jobCategory,
                        title: title,
                        responsibilities: parseSection(detailText, '업무내용'),
                        requirements: parseSection(detailText, '자격요건'),
                        preferred: parseSection(detailText, '우대요건')
                    });
                }

                return jobs;
            }
        """, category_filter)

        positions = []
        for item in data[:max_count]:
            if not item.get("requirements"):
                continue

            pos_category = self._map_to_position_category(item["category"])

            position = JobRequirement(
                title=item["title"],
                company="카페24",
                requirements=item["requirements"],
                preferred=item.get("preferred", []),
                tech_stack=[],
                responsibilities=item.get("responsibilities", []),
                job_id=f"cafe24_{hash(item['title']) % 100000:05d}",
                category=pos_category,
                scraped_at=datetime.now(),
            )
            positions.append(position)
            logger.info(f"✅ {position.title} 스크래핑 완료")

        return positions

    def _map_to_position_category(self, cafe24_category: str) -> PositionCategory:
        """카페24 카테고리를 PositionCategory로 매핑"""
        mapping = {
            "기획/운영": PositionCategory.OTHER,  # PM/기획은 별도 카테고리
            "개발/시스템": PositionCategory.BACKEND,
            "디자인": PositionCategory.OTHER,
            "마케팅": PositionCategory.OTHER,
            "경영지원": PositionCategory.OTHER,
            "제휴/영업": PositionCategory.OTHER,
            "고객지원": PositionCategory.OTHER,
            "기타": PositionCategory.OTHER,
        }
        return mapping.get(cafe24_category, PositionCategory.OTHER)

    def get_available_categories(self) -> list[Cafe24JobCategory]:
        """스크래핑 가능한 직군 목록 반환"""
        return list(Cafe24JobCategory)

    def save_scraped_data(self, data: ScrapedData) -> None:
        """스크래핑 데이터 저장"""
        with open(self.scraped_data_path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"💾 스크래핑 데이터 저장 완료: {self.scraped_data_path}")

    def load_scraped_data(self) -> Optional[ScrapedData]:
        """저장된 스크래핑 데이터 로드"""
        if not self.scraped_data_path.exists():
            return None

        try:
            with open(self.scraped_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ScrapedData.from_dict(data)
        except Exception as e:
            logger.error(f"❌ 스크래핑 데이터 로드 실패: {e}")
            return None

    def get_content_hash(self) -> Optional[str]:
        """저장된 데이터의 content_hash 반환"""
        data = self.load_scraped_data()
        return data.content_hash if data else None

    def has_changes(self, new_data: ScrapedData) -> bool:
        """데이터 변경 여부 확인"""
        old_hash = self.get_content_hash()
        if old_hash is None:
            return True
        return old_hash != new_data.content_hash


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    scraper = Cafe24JobScraper()

    # 기획/운영 직군 스크래핑 테스트
    print("\n🧪 카페24 기획/운영 직군 동적 스크래핑 테스트")
    data = await scraper.scrape_positions_by_category(
        Cafe24JobCategory.PLANNING,
        headless=True,
        max_jobs=3
    )

    print(f"\n📊 스크래핑 결과: {len(data.positions)}개 포지션")
    for pos in data.positions:
        print(f"  - {pos.title}")
        print(f"    업무: {len(pos.responsibilities)}개 항목")
        print(f"    자격요건: {len(pos.requirements)}개 항목")
        print(f"    우대: {len(pos.preferred)}개 항목")

    scraper.save_scraped_data(data)


if __name__ == "__main__":
    asyncio.run(main())
