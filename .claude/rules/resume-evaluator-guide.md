# 이력서 평가 시스템 개발 가이드

새로운 회사/직군의 이력서 평가 플로우를 개발할 때 참고하는 가이드입니다.

## 개요

이 시스템은 특정 회사의 채용공고를 스크래핑하여 인재상/요구사항을 추출하고, 이를 기반으로 AI가 이력서를 평가하는 워크플로우입니다.

### 플로우
1. **스크래핑**: 채용공고에서 인재상/요구사항 수집
2. **프롬프트 생성**: 인재상 기반 시스템 프롬프트 생성
3. **평가**: AI Agent가 이력서 평가
4. **(선택) 직군 분류**: 이력서를 분석하여 적합한 직군 추천

---

## 현재 지원 회사

| 회사 | 스크래퍼 | 워크플로우 | 특징 |
|------|----------|------------|------|
| 토스 | `TossJobScraper` | `ResumeEvaluationWorkflow` | 직군 자동 분류, 금융 도메인 평가 |
| 카페24 | `Cafe24JobScraper` | `Cafe24EvaluationWorkflow` | PM/기획 직군 특화 |
| 원티드 | `WantedJobScraper` | `WantedEvaluationWorkflow` | 다양한 기업, 기업별/직군별 평가 |

---

## 새 회사 추가 시 필요한 정보

사용자가 다음 정보를 제공해야 합니다:

1. **회사 정보**
   - 회사명 (영문, 한글)
   - 채용 사이트 URL
   - 채용공고 상세 페이지 URL 패턴

2. **직군 정보**
   - 직군 목록 (예: Backend, Frontend, App, DevOps 등)
   - 각 직군별 채용공고 ID 또는 URL 패턴

3. **Slack 채널 정보**
   - 이력서 피드백 채널 ID

4. **HTML 구조** (스크래핑용)
   - 채용공고 페이지의 HTML 샘플
   - 인재상/요구사항/기술스택 섹션의 선택자(selector)

---

## 개발 절차

### Step 1: 직군 Enum 정의 (`models.py`)

```python
# src/resume_evaluator/models.py에 추가

class {Company}JobCategory(str, Enum):
    """회사명 채용 직군 카테고리"""
    BACKEND = "Backend"
    FRONTEND = "Frontend"
    APP = "App"
    # ... 채용 사이트의 직군 필터 기준으로 추가

# 직군 매핑 (필요 시)
{COMPANY}_TO_POSITION_MAPPING = {
    {Company}JobCategory.BACKEND: PositionCategory.BACKEND,
    {Company}JobCategory.FRONTEND: PositionCategory.FRONTEND,
    # ...
}
```

### Step 2: 스크래퍼 구현 (`scraper_{company}.py`)

새 파일 `src/resume_evaluator/scraper_{company}.py` 생성:

```python
"""회사명 채용공고 스크래퍼 (Playwright 기반)"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page
from .models import JobRequirement, ScrapedData, {Company}JobCategory

logger = logging.getLogger(__name__)


class {Company}JobScraper:
    """회사명 채용공고 스크래퍼"""

    BASE_URL = "https://careers.{company}.com"

    def __init__(self, data_dir: str = "data/resume_evaluator/{company}"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_data_path = self.data_dir / "scraped_positions.json"

    async def scrape_positions_by_category(
        self,
        category: {Company}JobCategory,
        headless: bool = True,
        max_jobs: int = 10
    ) -> ScrapedData:
        """특정 직군의 포지션 스크래핑"""
        positions = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            try:
                # 채용 목록 페이지로 이동
                await page.goto(self.BASE_URL)
                await page.wait_for_timeout(2000)

                # TODO: 회사 페이지 구조에 맞게 구현
                # 1. 직군 필터 적용
                # 2. 공고 목록 추출
                # 3. 각 공고 상세 페이지 스크래핑

            except Exception as e:
                logger.error(f"스크래핑 실패: {e}")
            finally:
                await browser.close()

        return ScrapedData(
            positions=positions,
            scraped_at=datetime.now(),
            source_url=f"{self.BASE_URL}?category={category.value}",
        )

    def save_scraped_data(self, data: ScrapedData) -> None:
        """스크래핑 데이터 저장"""
        with open(self.scraped_data_path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)

    def load_scraped_data(self) -> Optional[ScrapedData]:
        """저장된 스크래핑 데이터 로드"""
        if not self.scraped_data_path.exists():
            return None
        try:
            with open(self.scraped_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ScrapedData.from_dict(data)
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
            return None
```

### Step 3: 프롬프트 생성기 (`prompt_generator_{company}.py`)

```python
"""회사명 전용 프롬프트 생성기"""

from .prompt_generator import PromptGenerator
from .models import ScrapedData, GeneratedPrompt


class {Company}PromptGenerator(PromptGenerator):
    """회사명 전용 프롬프트 생성기"""

    def __init__(self, data_dir: str = "data/resume_evaluator/{company}"):
        super().__init__(data_dir)

    def _build_prompt(self, ...):
        # 회사 특성에 맞게 평가 기준 커스터마이징
        # 예: 금융 → 이커머스 도메인 평가
        # 예: 기술 스택 우선순위 조정
        pass
```

### Step 4: 워크플로우 통합 (`workflow_{company}.py`)

```python
"""회사명 이력서 평가 워크플로우"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import ScrapedData, GeneratedPrompt, EvaluationResult, {Company}JobCategory
from .scraper_{company} import {Company}JobScraper
from .prompt_generator_{company} import {Company}PromptGenerator
from .evaluator import ResumeEvaluator


@dataclass
class {Company}WorkflowConfig:
    """워크플로우 설정"""
    data_dir: str = "data/resume_evaluator/{company}"
    ai_provider: str = "claude"
    headless: bool = True
    force_scrape: bool = False
    force_regenerate: bool = False


class {Company}EvaluationWorkflow:
    """회사명 이력서 평가 워크플로우"""

    def __init__(self, config: Optional[{Company}WorkflowConfig] = None):
        self.config = config or {Company}WorkflowConfig()
        self.data_dir = Path(self.config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 컴포넌트 초기화
        self.scraper = {Company}JobScraper(data_dir=self.config.data_dir)
        self.prompt_generator = {Company}PromptGenerator(data_dir=self.config.data_dir)
        self.evaluator = ResumeEvaluator(
            ai_provider=self.config.ai_provider,
            data_dir=self.config.data_dir
        )

        self._initialized = False

    async def initialize(self) -> bool:
        """워크플로우 초기화"""
        # 스크래핑 + 프롬프트 생성
        pass

    async def evaluate_resume_file(self, file_path: str) -> EvaluationResult:
        """이력서 평가"""
        pass
```

### Step 5: exports 추가 (`__init__.py`)

```python
# src/resume_evaluator/__init__.py에 추가

from .scraper_{company} import {Company}JobScraper
from .prompt_generator_{company} import {Company}PromptGenerator
from .workflow_{company} import {Company}WorkflowConfig, {Company}EvaluationWorkflow

__all__ = [
    # ... 기존 exports ...
    "{Company}JobScraper",
    "{Company}PromptGenerator",
    "{Company}WorkflowConfig",
    "{Company}EvaluationWorkflow",
]
```

### Step 6: Slack 핸들러 연동 (`resume_handler.py`)

```python
# 환경변수 추가
{COMPANY}_RESUME_FEEDBACK_CHANNEL_ID = os.getenv("{COMPANY}_RESUME_FEEDBACK_CHANNEL_ID")

# 채널별 회사 매핑
CHANNEL_COMPANY_MAP = {
    SLACK_RESUME_FEEDBACK_CHANNEL_ID: "toss",
    {COMPANY}_RESUME_FEEDBACK_CHANNEL_ID: "{company}",
}
```

### Step 7: 환경변수 추가

`.env` 파일에 추가:
```
{COMPANY}_RESUME_FEEDBACK_CHANNEL_ID=C0XXXXXXX
```

`docker-compose.yml`에 볼륨 마운트 추가:
```yaml
volumes:
  - /root/kim-secretary-data/resume_evaluator/{company}:/app/data/resume_evaluator/{company}:rw
```

---

## 핵심 데이터 모델

```python
@dataclass
class JobRequirement:
    title: str
    company: str
    requirements: list[str]    # 인재상/자격요건
    preferred: list[str]       # 우대사항
    tech_stack: list[str]      # 기술스택
    responsibilities: list[str]  # 주요업무
    job_id: str
    detail_url: str            # 상세 페이지 URL
    category: PositionCategory
    scraped_at: datetime

@dataclass
class ScrapedData:
    positions: list[JobRequirement]
    scraped_at: datetime
    source_url: str
    content_hash: str  # 변경 감지용 (자동 계산)

@dataclass
class EvaluationResult:
    total_score: int  # 0-100
    grade: EvaluationGrade  # S/A/B/C/D
    technical_skills_score: int  # 40점 만점
    problem_solving_score: int   # 25점 만점
    soft_skills_score: int       # 20점 만점
    domain_fit_score: int        # 15점 만점
    strengths: list[str]
    weaknesses: list[str]
    recommended_positions: list[str]
    interview_questions: list[str]
    summary: str
```

---

## 스크래핑 시 주의사항

1. **Rate Limiting**: 요청 사이 1초 이상 대기 (`await asyncio.sleep(1)`)
2. **Headless 모드**: 프로덕션에서는 `headless=True`
3. **캐싱**: `content_hash`로 변경 감지, 불필요한 재스크래핑 방지
4. **에러 처리**: try-except로 개별 공고 실패 시 계속 진행
5. **페이지네이션/무한스크롤**: 사이트 구조에 맞게 구현

---

## 평가 기준 (기본)

| 영역 | 배점 |
|------|------|
| 핵심 기술 역량 | 40점 |
| 문제 해결 능력 | 25점 |
| 소프트 스킬 | 20점 |
| 도메인 적합성 | 15점 |

등급 기준:
- S (90-100): 즉시 채용 권장
- A (75-89): 적극 면접 권장
- B (60-74): 면접 진행 권장
- C (45-59): 조건부 면접 고려
- D (0-44): 채용 보류 권장

---

## 체크리스트

새 회사 추가 시:

- [ ] `models.py`에 `{Company}JobCategory` Enum 추가
- [ ] `scraper_{company}.py` 스크래퍼 구현
- [ ] `prompt_generator_{company}.py` 프롬프트 생성기 구현
- [ ] `workflow_{company}.py` 워크플로우 구현
- [ ] `__init__.py` exports 추가
- [ ] `resume_handler.py` Slack 핸들러 연동
- [ ] `.env`에 채널 ID 환경변수 추가
- [ ] `docker-compose.yml`에 볼륨 마운트 추가
- [ ] 테스트 스크립트 작성 (`scripts/test_{company}_eval.py`)
- [ ] Python 문법 검사 (`python3 -m py_compile src/resume_evaluator/*.py`)
