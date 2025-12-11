"""토스 채용공고 스크래퍼 (Playwright 기반)"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser

from .models import JobRequirement, ScrapedData, PositionCategory, TossJobCategory

logger = logging.getLogger(__name__)


class TossJobScraper:
    """토스 채용공고 스크래퍼"""

    BASE_URL = "https://toss.im/career/jobs"
    JOB_DETAIL_URL = "https://toss.im/career/job-detail"

    # 직군별 job_id 매핑 (토스 채용페이지 기준)
    JOB_IDS_BY_CATEGORY: dict[TossJobCategory, list[str]] = {
        TossJobCategory.BACKEND: [
            "4071141003",  # Server Developer
            "6085421003",  # Server Developer [Commerce]
            "6052536003",  # Server Developer [Staff]
            "4773428003",  # Server Developer [산업기능요원/전문연구요원]
            "4421106003",  # Node.js Developer
            "4328355003",  # Python Developer
            "5847608003",  # Python Developer [산업기능요원/전문연구요원]
            "7519850003",  # Tech Lead (Server)
        ],
        TossJobCategory.APP: [
            "4071139003",  # iOS Developer
            "4071140003",  # Android Developer
            "6052541003",  # iOS Developer [Staff]
            "6052540003",  # Android Developer [Staff]
        ],
        TossJobCategory.FRONTEND: [
            "4071138003",  # Frontend Developer
            "6052539003",  # Frontend Developer [Staff]
        ],
        TossJobCategory.FULLSTACK: [
            "4348815003",  # Full Stack Developer
        ],
        TossJobCategory.INFRA: [
            "4071142003",  # DevOps Engineer
            "4348818003",  # SRE
            "6052542003",  # DevOps Engineer [Staff]
        ],
        TossJobCategory.QA: [
            "4348820003",  # QA Engineer
            "6052543003",  # QA Engineer [Staff]
        ],
        TossJobCategory.DEVICE: [
            "4348817003",  # Embedded Developer
        ],
    }

    # Server/Backend 관련 job_id 목록 (레거시 호환)
    SERVER_JOB_IDS = JOB_IDS_BY_CATEGORY[TossJobCategory.BACKEND]

    def __init__(self, data_dir: str = "data/resume_evaluator"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_data_path = self.data_dir / "scraped_positions.json"

    async def scrape_positions_by_category(
        self,
        category: TossJobCategory,
        headless: bool = True
    ) -> ScrapedData:
        """특정 직군의 포지션 스크래핑

        Args:
            category: 직군 카테고리
            headless: 헤드리스 모드 여부

        Returns:
            ScrapedData: 스크래핑된 데이터
        """
        job_ids = self.JOB_IDS_BY_CATEGORY.get(category, [])
        if not job_ids:
            logger.warning(f"⚠️ {category.value} 직군의 job_id가 없습니다.")
            return ScrapedData(positions=[], source_url=self.BASE_URL)

        logger.info(f"🚀 토스 {category.value} 포지션 스크래핑 시작... ({len(job_ids)}개)")

        positions = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            for job_id in job_ids:
                try:
                    position = await self._scrape_position(page, job_id, category)
                    if position:
                        positions.append(position)
                        logger.info(f"✅ {position.title} ({position.company}) 스크래핑 완료")
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"❌ job_id={job_id} 스크래핑 실패: {e}")

            await browser.close()

        scraped_data = ScrapedData(
            positions=positions,
            scraped_at=datetime.now(),
            source_url=f"{self.BASE_URL}?category={category.value}",
        )

        logger.info(f"✅ 총 {len(positions)}개 {category.value} 포지션 스크래핑 완료")
        return scraped_data

    async def scrape_all_server_positions(self, headless: bool = True) -> ScrapedData:
        """모든 Server 포지션 스크래핑 (레거시 호환)

        Args:
            headless: 헤드리스 모드 여부

        Returns:
            ScrapedData: 스크래핑된 데이터
        """
        return await self.scrape_positions_by_category(TossJobCategory.BACKEND, headless)

    def get_available_categories(self) -> list[TossJobCategory]:
        """스크래핑 가능한 직군 목록 반환"""
        return [cat for cat in TossJobCategory if cat in self.JOB_IDS_BY_CATEGORY]

    def get_job_url(self, job_id: str) -> str:
        """job_id로 채용공고 URL 생성"""
        return f"{self.JOB_DETAIL_URL}?job_id={job_id}"

    def get_first_job_url_for_category(self, category: TossJobCategory) -> Optional[str]:
        """직군의 첫 번째 채용공고 URL 반환"""
        job_ids = self.JOB_IDS_BY_CATEGORY.get(category, [])
        if not job_ids:
            return None
        return self.get_job_url(job_ids[0])

    async def _scrape_position(
        self,
        page: Page,
        job_id: str,
        category: Optional[TossJobCategory] = None
    ) -> Optional[JobRequirement]:
        """개별 포지션 상세 페이지 스크래핑

        Args:
            page: Playwright Page 객체
            job_id: 채용공고 ID
            category: 직군 카테고리 (optional)

        Returns:
            JobRequirement 또는 None
        """
        url = f"{self.JOB_DETAIL_URL}?job_id={job_id}"
        logger.debug(f"📄 스크래핑: {url}")

        await page.goto(url)
        await page.wait_for_timeout(3000)  # 페이지 로딩 대기

        # "공고 보기" 버튼이 있으면 클릭 (여러 계열사가 묶인 경우)
        try:
            view_button = page.locator('button:has-text("공고 보기")').first
            if await view_button.is_visible():
                await page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            if (btn.textContent.includes('공고 보기')) {
                                btn.click();
                                break;
                            }
                        }
                    }
                """)
                await page.wait_for_timeout(2000)
        except Exception:
            pass  # 버튼이 없는 경우 무시

        # 페이지에서 데이터 추출
        data = await page.evaluate("""
            () => {
                const result = {
                    title: document.querySelector('h1')?.textContent?.trim() || '',
                    company: '',
                    requirements: [],
                    preferred: [],
                    tech_stack: [],
                    responsibilities: [],
                };

                // 회사 정보 추출
                const h5 = document.querySelector('h5');
                if (h5) {
                    result.company = h5.textContent?.trim() || '';
                }

                // 섹션별 데이터 추출
                const paragraphs = document.querySelectorAll('p');

                for (const p of paragraphs) {
                    const text = p.textContent?.trim() || '';
                    let sibling = p.nextElementSibling;

                    // 인재상 / 자격요건
                    if (text.includes('이런 분과 함께하고 싶어요') || text.includes('이런 분을 찾고 있어요')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.requirements.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }

                    // 우대사항
                    if (text.includes('이런 분이면 더 좋아요') || text.includes('우대')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.preferred.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }

                    // 기술 스택
                    if (text.includes('사용하는 기술') || text.includes('기술 스택')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.tech_stack.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }

                    // 주요 업무
                    if (text.includes('합류하면 함께') || text.includes('주요 업무')) {
                        while (sibling && sibling.tagName === 'UL') {
                            const items = sibling.querySelectorAll('li');
                            items.forEach(item => {
                                const itemText = item.textContent?.trim()?.replace(/^•\\s*/, '');
                                if (itemText) result.responsibilities.push(itemText);
                            });
                            sibling = sibling.nextElementSibling;
                        }
                    }
                }

                return result;
            }
        """)

        if not data.get("title") or not data.get("requirements"):
            logger.warning(f"⚠️ job_id={job_id}: 필수 데이터 누락")
            return None

        # TossJobCategory -> PositionCategory 매핑
        from .models import TOSS_TO_POSITION_MAPPING
        position_category = TOSS_TO_POSITION_MAPPING.get(
            category, PositionCategory.BACKEND
        ) if category else PositionCategory.BACKEND

        return JobRequirement(
            title=data["title"],
            company=data.get("company", "토스"),
            requirements=data.get("requirements", []),
            preferred=data.get("preferred", []),
            tech_stack=data.get("tech_stack", []),
            responsibilities=data.get("responsibilities", []),
            job_id=job_id,
            category=position_category,
            scraped_at=datetime.now(),
        )

    def save_scraped_data(self, data: ScrapedData) -> None:
        """스크래핑 데이터 저장

        Args:
            data: 저장할 ScrapedData
        """
        with open(self.scraped_data_path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"💾 스크래핑 데이터 저장 완료: {self.scraped_data_path}")

    def load_scraped_data(self) -> Optional[ScrapedData]:
        """저장된 스크래핑 데이터 로드

        Returns:
            ScrapedData 또는 None
        """
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
        """저장된 데이터의 content_hash 반환

        Returns:
            content_hash 또는 None
        """
        data = self.load_scraped_data()
        return data.content_hash if data else None

    def has_changes(self, new_data: ScrapedData) -> bool:
        """데이터 변경 여부 확인

        Args:
            new_data: 새로 스크래핑한 데이터

        Returns:
            변경 여부
        """
        old_hash = self.get_content_hash()
        if old_hash is None:
            return True
        return old_hash != new_data.content_hash


async def main():
    """테스트용 메인 함수"""
    logging.basicConfig(level=logging.INFO)

    scraper = TossJobScraper()
    data = await scraper.scrape_all_server_positions(headless=True)

    print(f"\n📊 스크래핑 결과: {len(data.positions)}개 포지션")
    for pos in data.positions:
        print(f"  - {pos.title} ({pos.company})")
        print(f"    인재상: {len(pos.requirements)}개 항목")

    scraper.save_scraped_data(data)


if __name__ == "__main__":
    asyncio.run(main())
