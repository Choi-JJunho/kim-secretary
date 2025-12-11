"""토스 채용공고 스크래퍼 (Playwright 기반)"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser

from .models import JobRequirement, ScrapedData, PositionCategory

logger = logging.getLogger(__name__)


class TossJobScraper:
    """토스 채용공고 스크래퍼"""

    BASE_URL = "https://toss.im/career/jobs"
    JOB_DETAIL_URL = "https://toss.im/career/job-detail"

    # Server/Backend 관련 job_id 목록
    SERVER_JOB_IDS = [
        "4071141003",  # Server Developer
        "6085421003",  # Server Developer [Commerce]
        "6052536003",  # Server Developer [Staff]
        "4773428003",  # Server Developer [산업기능요원/전문연구요원]
        "4421106003",  # Node.js Developer
        "4328355003",  # Python Developer
        "5847608003",  # Python Developer [산업기능요원/전문연구요원]
        "7519850003",  # Tech Lead (Server)
    ]

    def __init__(self, data_dir: str = "data/resume_evaluator"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_data_path = self.data_dir / "scraped_positions.json"

    async def scrape_all_server_positions(self, headless: bool = True) -> ScrapedData:
        """모든 Server 포지션 스크래핑

        Args:
            headless: 헤드리스 모드 여부

        Returns:
            ScrapedData: 스크래핑된 데이터
        """
        logger.info("🚀 토스 Server 포지션 스크래핑 시작...")

        positions = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            for job_id in self.SERVER_JOB_IDS:
                try:
                    position = await self._scrape_position(page, job_id)
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
            source_url=self.BASE_URL,
        )

        logger.info(f"✅ 총 {len(positions)}개 포지션 스크래핑 완료")
        return scraped_data

    async def _scrape_position(self, page: Page, job_id: str) -> Optional[JobRequirement]:
        """개별 포지션 상세 페이지 스크래핑

        Args:
            page: Playwright Page 객체
            job_id: 채용공고 ID

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

        return JobRequirement(
            title=data["title"],
            company=data.get("company", "토스"),
            requirements=data.get("requirements", []),
            preferred=data.get("preferred", []),
            tech_stack=data.get("tech_stack", []),
            responsibilities=data.get("responsibilities", []),
            job_id=job_id,
            category=PositionCategory.BACKEND,
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
