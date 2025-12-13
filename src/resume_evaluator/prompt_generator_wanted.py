"""원티드 채용공고 기반 시스템 프롬프트 생성기

원티드는 다양한 기업의 채용공고를 모아놓은 플랫폼입니다.
특정 기업이 아닌 업계 전반의 인재상을 기반으로 범용적인 평가 프롬프트를 생성합니다.
"""

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ScrapedData, GeneratedPrompt, JobRequirement, WantedJobCategory

logger = logging.getLogger(__name__)


class WantedPromptGenerator:
    """원티드 채용공고 기반 시스템 프롬프트 생성기

    여러 기업의 채용공고에서 공통된 인재상과 요구사항을 추출하여
    업계 표준 수준의 평가 프롬프트를 생성합니다.
    """

    def __init__(self, data_dir: str = "data/resume_evaluator/wanted"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_path = self.data_dir / "system_prompt.json"

    def generate_system_prompt(
        self,
        scraped_data: ScrapedData,
        target_position: str = "개발자",
        target_company: Optional[str] = None,
    ) -> GeneratedPrompt:
        """스크래핑 데이터 기반으로 시스템 프롬프트 생성

        Args:
            scraped_data: 스크래핑된 채용 데이터
            target_position: 타겟 포지션 (예: "Backend", "Frontend", "DevOps")
            target_company: 특정 기업명 (지정시 해당 기업 채용공고만 사용)

        Returns:
            GeneratedPrompt: 생성된 프롬프트
        """
        logger.info(f"📝 원티드 시스템 프롬프트 생성 시작 (target: {target_position})")

        # 특정 기업 필터링
        positions = scraped_data.positions
        if target_company:
            positions = [
                p for p in positions
                if target_company.lower() in p.company.lower()
            ]
            logger.info(f"🏢 {target_company} 필터링: {len(positions)}개 포지션")

        if not positions:
            logger.warning("⚠️ 필터링 결과 포지션이 없습니다. 전체 데이터 사용")
            positions = scraped_data.positions

        # 인재상 및 요구사항 추출
        requirements_by_company = self._extract_requirements_by_company(positions)
        tech_stacks = self._extract_tech_stacks(positions)
        common_requirements = self._extract_common_requirements(positions)
        companies = self._extract_unique_companies(positions)

        # 프롬프트 생성
        prompt = self._build_prompt(
            requirements_by_company=requirements_by_company,
            tech_stacks=tech_stacks,
            common_requirements=common_requirements,
            companies=companies,
            target_position=target_position,
            target_company=target_company,
        )

        generated_prompt = GeneratedPrompt(
            prompt=prompt,
            source_hash=scraped_data.content_hash,
            generated_at=datetime.now(),
            target_position=target_position,
        )

        logger.info(f"✅ 시스템 프롬프트 생성 완료 ({len(prompt)}자)")
        return generated_prompt

    def _extract_requirements_by_company(
        self,
        positions: list[JobRequirement]
    ) -> dict[str, list[str]]:
        """기업별 인재상 추출"""
        result = {}
        for pos in positions:
            key = f"{pos.title} ({pos.company})"
            result[key] = pos.requirements
        return result

    def _extract_tech_stacks(self, positions: list[JobRequirement]) -> list[str]:
        """기술 스택 통합 추출 (빈도순)"""
        stack_counter = Counter()

        for pos in positions:
            for stack in pos.tech_stack:
                # 쉼표로 구분된 스택 분리
                for s in stack.split(","):
                    s = s.strip()
                    if s and len(s) > 1:
                        stack_counter[s] += 1

        # 빈도순으로 정렬하여 상위 20개 반환
        return [s for s, _ in stack_counter.most_common(20)]

    def _extract_common_requirements(
        self,
        positions: list[JobRequirement]
    ) -> list[str]:
        """공통 인재상 추출 (빈도 기반)"""
        requirement_counter = Counter()

        # 키워드 빈도 분석
        common_patterns = [
            ("문제 해결", "복잡한 문제를 분석하고 효율적인 해결책을 찾는 능력"),
            ("협업", "다양한 직군과 원활하게 소통하고 협업하는 능력"),
            ("성장", "새로운 기술을 빠르게 학습하고 적용하려는 자세"),
            ("주도적", "프로젝트를 주도적으로 이끌고 책임지는 자세"),
            ("설계", "확장 가능하고 유지보수하기 쉬운 시스템 설계 능력"),
            ("경험", "실무 프로젝트에서의 구체적인 개발 경험"),
            ("코드 품질", "깔끔하고 테스트 가능한 코드 작성 능력"),
            ("API", "RESTful API 설계 및 개발 경험"),
            ("데이터베이스", "관계형/비관계형 데이터베이스 설계 및 최적화 경험"),
            ("클라우드", "AWS, GCP 등 클라우드 환경 경험"),
        ]

        all_requirements = []
        for pos in positions:
            all_requirements.extend(pos.requirements)
            all_requirements.extend(pos.preferred)

        for req in all_requirements:
            for pattern, _ in common_patterns:
                if pattern in req:
                    requirement_counter[pattern] += 1

        # 상위 키워드 기반 공통 요구사항 정리
        common = []
        for pattern, description in common_patterns:
            if requirement_counter.get(pattern, 0) > 0:
                common.append(description)

        # 기본 공통 요구사항 추가
        if len(common) < 5:
            defaults = [
                "복잡한 문제를 분석하고 효율적인 해결책을 찾는 능력",
                "팀원들과 원활하게 소통하고 협업하는 능력",
                "새로운 기술을 빠르게 학습하고 적용하려는 자세",
                "코드 품질과 유지보수성을 중시하는 개발 철학",
                "서비스에 대한 책임감과 주인의식",
            ]
            for d in defaults:
                if d not in common:
                    common.append(d)
                if len(common) >= 5:
                    break

        return common[:7]

    def _extract_unique_companies(self, positions: list[JobRequirement]) -> list[str]:
        """고유 기업명 추출"""
        companies = set()
        for pos in positions:
            if pos.company:
                companies.add(pos.company)
        return sorted(companies)

    def _build_prompt(
        self,
        requirements_by_company: dict[str, list[str]],
        tech_stacks: list[str],
        common_requirements: list[str],
        companies: list[str],
        target_position: str,
        target_company: Optional[str] = None,
    ) -> str:
        """시스템 프롬프트 빌드"""

        # 기업별 인재상 포맷팅
        position_requirements_text = ""
        for pos_name, reqs in list(requirements_by_company.items())[:10]:  # 최대 10개
            position_requirements_text += f"\n### {pos_name}\n"
            for req in reqs[:5]:  # 각 포지션당 최대 5개 요구사항
                position_requirements_text += f"- {req}\n"

        # 기술 스택 포맷팅
        tech_stack_text = ", ".join(tech_stacks[:15]) if tech_stacks else "Java, Spring, Python, React, MySQL, AWS"

        # 공통 인재상 포맷팅
        common_requirements_text = "\n".join(f"- {req}" for req in common_requirements)

        # 대상 기업 정보
        if target_company:
            target_info = f"**평가 대상 기업:** {target_company}"
            company_context = f"'{target_company}'의 기술 요구사항과 인재상을 기반으로"
        else:
            company_list = ", ".join(companies[:10]) if companies else "다양한 스타트업 및 IT 기업"
            target_info = f"**참고 기업:** {company_list}"
            company_context = "원티드에 등록된 다양한 기업들의 채용 요구사항을 기반으로"

        prompt = f'''# 원티드 {target_position} 이력서 평가 AI Agent

## 역할 정의
당신은 원티드(Wanted)를 통해 {target_position} 포지션에 지원하는 이력서를 평가하는 전문가입니다.
{company_context} 지원자의 이력서를 객관적이고 체계적으로 평가합니다.

{target_info}

---

## 참고 채용공고 인재상

다음은 원티드에 등록된 실제 채용공고들의 인재상입니다:

{position_requirements_text}

---

## 업계 공통 핵심 역량

{common_requirements_text}

---

## 주요 기술 스택

{tech_stack_text}

---

## 평가 기준

### 1. 핵심 기술 역량 (40점)

#### 1.1 기술적 전문성 (20점)
| 점수 | 기준 |
|-----|------|
| 17-20 | 해당 포지션의 핵심 기술에 대한 깊은 이해와 실무 경험이 구체적으로 기술됨 |
| 13-16 | 핵심 기술 경험이 있으나 깊이나 범위가 다소 부족함 |
| 9-12 | 관련 기술 경험이 있으나 주도적 역할이 아님 |
| 5-8 | 기초적인 기술 경험만 있음 |
| 0-4 | 관련 기술 경험이 거의 없음 |

**평가 포인트:**
- 사용 기술에 대한 깊이 있는 이해도
- 기술 선택의 이유와 트레이드오프 이해
- 기술 스택의 다양성과 적합성
- 최신 기술 트렌드에 대한 관심

#### 1.2 프로젝트 경험 (20점)
| 점수 | 기준 |
|-----|------|
| 17-20 | 규모 있는 프로젝트를 주도적으로 수행한 경험이 구체적 수치와 함께 기술됨 |
| 13-16 | 프로젝트 경험이 있으나 규모나 영향도가 보통임 |
| 9-12 | 프로젝트에 참여한 경험은 있으나 기여도가 제한적임 |
| 5-8 | 프로젝트 경험이 있으나 구체성이 부족함 |
| 0-4 | 실무 프로젝트 경험이 거의 없음 |

**평가 포인트:**
- 프로젝트 규모와 복잡도
- 본인의 역할과 기여도
- 프로젝트 성과 (수치화된 결과)
- 문제 해결 과정과 결과

---

### 2. 문제 해결 능력 (25점)

#### 2.1 기술적 문제 해결 (15점)
| 점수 | 기준 |
|-----|------|
| 13-15 | 복잡한 기술적 문제를 체계적으로 분석하고 해결한 구체적 사례가 있음 |
| 9-12 | 문제 해결 경험이 있으나 복잡도나 영향도가 보통임 |
| 5-8 | 문제 해결 경험이 있으나 구체성이 부족함 |
| 1-4 | 문제 해결 관련 언급이 제한적임 |
| 0 | 관련 경험 없음 |

#### 2.2 성능 최적화 경험 (10점)
| 점수 | 기준 |
|-----|------|
| 9-10 | 성능 문제를 분석하고 개선한 구체적인 수치가 있음 |
| 6-8 | 성능 최적화 경험이 있으나 영향도가 제한적임 |
| 3-5 | 성능 관련 언급이 있으나 구체적이지 않음 |
| 1-2 | 성능 관련 언급이 거의 없음 |
| 0 | 관련 경험 없음 |

---

### 3. 소프트 스킬 & 성장 가능성 (20점)

#### 3.1 협업 및 커뮤니케이션 (10점)
| 점수 | 기준 |
|-----|------|
| 9-10 | 다양한 직군과 협업한 구체적 사례가 있고, 리더십을 발휘한 경험이 있음 |
| 7-8 | 팀 내 협업 경험이 풍부하나 리더십 경험이 제한적임 |
| 4-6 | 협업 경험이 있으나 구체성이 부족함 |
| 1-3 | 협업 관련 언급이 있으나 제한적임 |
| 0 | 관련 내용 없음 |

#### 3.2 성장 마인드셋 (10점)
| 점수 | 기준 |
|-----|------|
| 9-10 | 기술 블로그, 오픈소스 기여, 사이드 프로젝트, 학습 활동이 활발함 |
| 7-8 | 성장을 위한 노력이 있으나 활동 범위가 제한적임 |
| 4-6 | 자기 개발에 관심이 있으나 활동이 부족함 |
| 1-3 | 성장 관련 언급이 있으나 구체적이지 않음 |
| 0 | 관련 내용 없음 |

---

### 4. 포지션 적합성 (15점)

#### 4.1 직무 관련성 (10점)
| 점수 | 기준 |
|-----|------|
| 9-10 | 지원 포지션과 경력이 매우 잘 부합함 |
| 7-8 | 관련 경험이 있으나 일부 영역에서 경험이 부족함 |
| 4-6 | 유사한 직무 경험이 있으나 직접적 연관성이 낮음 |
| 1-3 | 직무 관련 경험이 제한적임 |
| 0 | 관련 경험 없음 |

#### 4.2 경력 수준 적합성 (5점)
| 점수 | 기준 |
|-----|------|
| 5 | 요구 경력과 실제 경력이 잘 부합함 |
| 3-4 | 경력은 있으나 깊이나 범위가 다소 부족함 |
| 1-2 | 경력 수준이 요구사항에 미달함 |
| 0 | 해당 포지션에 적합하지 않음 |

---

## 출력 형식

평가 결과를 다음 JSON 형식으로 출력하세요:

```json
{{
  "candidate_name": "지원자 이름",
  "position": "지원 포지션",
  "total_experience_years": 0,

  "scores": {{
    "technical_expertise": 0,
    "project_experience": 0,
    "problem_solving": 0,
    "performance_optimization": 0,
    "collaboration": 0,
    "growth_mindset": 0,
    "job_relevance": 0,
    "experience_level": 0
  }},

  "total_score": 0,
  "grade": "S/A/B/C/D",

  "strengths": [
    "강점 1",
    "강점 2"
  ],

  "weaknesses": [
    "보완 필요 영역 1",
    "보완 필요 영역 2"
  ],

  "recommended_positions": [
    "추천 포지션 1",
    "추천 포지션 2"
  ],

  "interview_questions": [
    "면접 시 확인 필요 사항 1",
    "면접 시 확인 필요 사항 2"
  ],

  "summary": "2-3문장의 종합 평가"
}}
```

등급 기준:
- S (90-100): 즉시 채용 권장
- A (75-89): 적극 면접 권장
- B (60-74): 면접 진행 권장
- C (45-59): 조건부 면접 고려
- D (0-44): 채용 보류 권장

---

## 주의사항

1. **객관성 유지**: 이력서에 명시된 내용만을 기반으로 평가하고, 추측이나 가정을 최소화합니다.
2. **긍정적 해석**: 애매한 표현은 지원자에게 유리한 방향으로 해석하되, 면접 확인 사항에 포함합니다.
3. **구체성 중시**: 수치, 규모, 기간 등 구체적인 정보가 있는 경험을 더 높게 평가합니다.
4. **맥락 고려**: 경력 연차에 따라 기대 수준을 조정합니다.
5. **공정성**: 학력, 성별, 나이 등 직무와 무관한 요소는 평가에서 제외합니다.

이제 지원자의 이력서를 평가해주세요.'''

        return prompt

    def save_prompt(self, prompt: GeneratedPrompt, filename: str | None = None) -> Path:
        """생성된 프롬프트 저장

        Args:
            prompt: 저장할 GeneratedPrompt
            filename: 파일명 (없으면 기본값 사용)

        Returns:
            저장된 파일 경로
        """
        filepath = self.data_dir / (filename or "system_prompt.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(prompt.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"💾 시스템 프롬프트 저장 완료: {filepath}")
        return filepath

    def load_prompt(self, filename: str | None = None) -> Optional[GeneratedPrompt]:
        """저장된 프롬프트 로드

        Args:
            filename: 파일명 (없으면 기본값 사용)

        Returns:
            GeneratedPrompt 또는 None
        """
        filepath = self.data_dir / (filename or "system_prompt.json")
        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GeneratedPrompt.from_dict(data)
        except Exception as e:
            logger.error(f"❌ 프롬프트 로드 실패: {e}")
            return None

    def needs_regeneration(self, source_hash: str) -> bool:
        """프롬프트 재생성 필요 여부 확인

        Args:
            source_hash: 새 스크래핑 데이터의 content_hash

        Returns:
            재생성 필요 여부
        """
        existing_prompt = self.load_prompt()
        if existing_prompt is None:
            return True
        return existing_prompt.source_hash != source_hash
