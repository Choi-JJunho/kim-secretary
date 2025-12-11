"""이력서 기반 직군 분류기"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..ai import generate_with_gemini_fallback
from .models import TossJobCategory

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """직군 분류 결과"""
    primary_category: TossJobCategory
    secondary_categories: list[TossJobCategory]
    confidence: float  # 0.0 ~ 1.0
    reasoning: str
    skills_detected: list[str]
    experience_years: Optional[int]
    ai_model: str


# 직군별 키워드 매핑 (AI 분류 전 사전 필터링용)
CATEGORY_KEYWORDS = {
    TossJobCategory.BACKEND: [
        "backend", "server", "api", "java", "kotlin", "spring", "node.js",
        "python", "go", "golang", "mysql", "postgresql", "redis", "kafka",
        "microservice", "rest", "grpc", "백엔드", "서버", "데이터베이스",
    ],
    TossJobCategory.FRONTEND: [
        "frontend", "react", "vue", "angular", "javascript", "typescript",
        "html", "css", "web", "프론트엔드", "웹", "ui/ux",
    ],
    TossJobCategory.APP: [
        "ios", "android", "swift", "kotlin", "flutter", "react native",
        "mobile", "앱", "모바일", "application",
    ],
    TossJobCategory.DEVICE: [
        "embedded", "firmware", "iot", "hardware", "device", "driver",
        "임베디드", "펌웨어", "하드웨어", "디바이스",
    ],
    TossJobCategory.FULLSTACK: [
        "fullstack", "full-stack", "full stack", "풀스택",
    ],
    TossJobCategory.INFRA: [
        "devops", "infrastructure", "aws", "gcp", "azure", "kubernetes",
        "docker", "terraform", "ci/cd", "sre", "인프라", "클라우드",
    ],
    TossJobCategory.QA: [
        "qa", "quality", "test", "testing", "automation test",
        "품질", "테스트", "자동화",
    ],
}


class JobClassifier:
    """이력서 기반 직군 분류기"""

    CLASSIFICATION_PROMPT = """당신은 채용 전문가입니다. 주어진 이력서를 분석하여 가장 적합한 토스 채용 직군을 분류해주세요.

## 토스 채용 직군 목록
- Backend: 서버 개발, API 설계, 데이터베이스, Java/Kotlin/Python/Go 등
- App: iOS/Android 앱 개발, Swift/Kotlin/Flutter/React Native 등
- Device: 임베디드, 펌웨어, IoT, 하드웨어 제어 등
- Frontend: 웹 프론트엔드, React/Vue/Angular, JavaScript/TypeScript 등
- Full Stack: 프론트엔드와 백엔드 모두 가능한 개발자
- Infra: DevOps, SRE, 클라우드(AWS/GCP/Azure), Kubernetes 등
- QA: 품질 보증, 테스트 자동화, 테스트 설계 등

## 분류 기준
1. 주요 기술 스택과 경험을 기반으로 1순위 직군을 결정
2. 추가로 적합할 수 있는 직군이 있다면 2순위로 추천
3. 확신도(confidence)는 0.0~1.0 사이로 표현
4. 경력 연차도 추정해주세요

## 출력 형식 (JSON)
```json
{
    "primary_category": "Backend",
    "secondary_categories": ["Full Stack"],
    "confidence": 0.85,
    "reasoning": "Java/Spring 기반 서버 개발 경력 5년, MSA 설계 경험 다수...",
    "skills_detected": ["Java", "Spring Boot", "Kubernetes", "MySQL"],
    "experience_years": 5
}
```

## 주의사항
- 직군명은 정확히 다음 중 하나로: Backend, App, Device, Frontend, Full Stack, Infra, QA
- 경력이 부족하거나 불분명한 경우 experience_years는 null로
- 여러 분야에 걸쳐 있으면 secondary_categories에 추가"""

    def __init__(self, ai_provider: str = "claude"):
        """
        Args:
            ai_provider: AI 제공자 (claude, gemini)
        """
        self.ai_provider = ai_provider

    async def classify(self, resume_text: str) -> ClassificationResult:
        """이력서를 분석하여 직군 분류

        Args:
            resume_text: 이력서 텍스트

        Returns:
            ClassificationResult: 분류 결과
        """
        logger.info("🔍 이력서 직군 분류 시작...")

        # 키워드 기반 사전 분석 (참고용)
        keyword_hints = self._analyze_keywords(resume_text.lower())
        logger.debug(f"키워드 분석 힌트: {keyword_hints}")

        # AI 분류
        user_prompt = f"""다음 이력서를 분석하여 가장 적합한 토스 채용 직군을 분류해주세요.

## 이력서 내용

{resume_text}

---

위의 분류 기준에 따라 JSON 형식으로 결과를 출력해주세요."""

        try:
            response, used_provider = await generate_with_gemini_fallback(
                provider_type=self.ai_provider,
                prompt=user_prompt,
                system_prompt=self.CLASSIFICATION_PROMPT,
            )
            logger.info(f"✅ AI 분류 완료 (provider: {used_provider})")
        except Exception as e:
            logger.error(f"❌ AI 분류 실패: {e}")
            # 폴백: 키워드 기반 분류
            return self._fallback_classification(keyword_hints, str(e))

        # 응답 파싱
        result = self._parse_response(response, used_provider)
        return result

    def _analyze_keywords(self, text: str) -> dict[TossJobCategory, int]:
        """키워드 기반 사전 분석

        Args:
            text: 이력서 텍스트 (소문자)

        Returns:
            카테고리별 매칭 키워드 수
        """
        results = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text)
            if count > 0:
                results[category] = count
        return results

    def _parse_response(self, response: str, provider: str) -> ClassificationResult:
        """AI 응답 파싱

        Args:
            response: AI 응답 텍스트
            provider: 사용된 AI 제공자

        Returns:
            ClassificationResult: 파싱된 분류 결과
        """
        # JSON 추출
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning("⚠️ JSON 응답을 찾을 수 없습니다.")
                return self._create_default_result(response, provider)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON 파싱 실패: {e}")
            return self._create_default_result(response, provider)

        # 카테고리 파싱
        primary_str = data.get("primary_category", "Backend")
        primary_category = self._str_to_category(primary_str)

        secondary_strs = data.get("secondary_categories", [])
        secondary_categories = [
            self._str_to_category(s) for s in secondary_strs
            if self._str_to_category(s) is not None
        ]

        return ClassificationResult(
            primary_category=primary_category or TossJobCategory.BACKEND,
            secondary_categories=secondary_categories,
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
            skills_detected=data.get("skills_detected", []),
            experience_years=data.get("experience_years"),
            ai_model=provider,
        )

    def _str_to_category(self, s: str) -> Optional[TossJobCategory]:
        """문자열을 TossJobCategory로 변환"""
        mapping = {
            "backend": TossJobCategory.BACKEND,
            "app": TossJobCategory.APP,
            "device": TossJobCategory.DEVICE,
            "frontend": TossJobCategory.FRONTEND,
            "full stack": TossJobCategory.FULLSTACK,
            "fullstack": TossJobCategory.FULLSTACK,
            "infra": TossJobCategory.INFRA,
            "qa": TossJobCategory.QA,
        }
        return mapping.get(s.lower().strip())

    def _create_default_result(self, response: str, provider: str) -> ClassificationResult:
        """기본 분류 결과 생성"""
        return ClassificationResult(
            primary_category=TossJobCategory.BACKEND,
            secondary_categories=[],
            confidence=0.3,
            reasoning="AI 응답 파싱 실패로 기본값 사용",
            skills_detected=[],
            experience_years=None,
            ai_model=provider,
        )

    def _fallback_classification(
        self,
        keyword_hints: dict[TossJobCategory, int],
        error_msg: str
    ) -> ClassificationResult:
        """키워드 기반 폴백 분류"""
        if not keyword_hints:
            return ClassificationResult(
                primary_category=TossJobCategory.BACKEND,
                secondary_categories=[],
                confidence=0.2,
                reasoning=f"AI 분류 실패 ({error_msg}). 키워드 매칭 없음.",
                skills_detected=[],
                experience_years=None,
                ai_model="keyword_fallback",
            )

        # 가장 많이 매칭된 카테고리
        sorted_hints = sorted(keyword_hints.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_hints[0][0]
        secondary = [cat for cat, _ in sorted_hints[1:3]]

        return ClassificationResult(
            primary_category=primary,
            secondary_categories=secondary,
            confidence=0.4,
            reasoning=f"AI 분류 실패 ({error_msg}). 키워드 기반 분류 사용.",
            skills_detected=[],
            experience_years=None,
            ai_model="keyword_fallback",
        )

    def read_pdf(self, file_path: str) -> str:
        """PDF 파일에서 텍스트 추출

        Args:
            file_path: PDF 파일 경로

        Returns:
            추출된 텍스트
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            raise ImportError("PDF 파일을 읽으려면 pypdf 패키지가 필요합니다: pip install pypdf")

    async def classify_from_file(self, file_path: str) -> ClassificationResult:
        """파일에서 이력서를 읽어 분류

        Args:
            file_path: 이력서 파일 경로

        Returns:
            ClassificationResult: 분류 결과
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            text = self.read_pdf(file_path)
        elif suffix in [".md", ".txt"]:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {suffix}")

        return await self.classify(text)
