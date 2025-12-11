"""이력서 평가 워크플로우 모듈

토스 Backend 포지션의 인재상을 스크래핑하고,
이를 기반으로 이력서를 평가하는 AI Agent 시스템입니다.

워크플로우:
1. 스크래핑: 토스 채용공고에서 인재상 수집
2. 프롬프트 생성: 인재상 기반 시스템 프롬프트 생성 (변경 시에만)
3. 평가: AI Agent가 이력서 평가

사용 예시:
    >>> from src.resume_evaluator import ResumeEvaluationWorkflow, WorkflowConfig
    >>>
    >>> config = WorkflowConfig(ai_provider="claude")
    >>> workflow = ResumeEvaluationWorkflow(config)
    >>> await workflow.initialize()
    >>> result = await workflow.evaluate_resume_file("resume.pdf")
    >>> print(workflow.format_result(result))

CLI 사용:
    $ python -m src.resume_evaluator.cli init        # 초기화
    $ python -m src.resume_evaluator.cli evaluate resume.pdf  # 평가
    $ python -m src.resume_evaluator.cli status      # 상태 확인
"""

from .models import (
    PositionCategory,
    EvaluationGrade,
    JobRequirement,
    ScrapedData,
    GeneratedPrompt,
    EvaluationResult,
)
from .scraper import TossJobScraper
from .prompt_generator import PromptGenerator
from .evaluator import ResumeEvaluator
from .workflow import (
    WorkflowConfig,
    ResumeEvaluationWorkflow,
    run_workflow,
)

__all__ = [
    # Models
    "PositionCategory",
    "EvaluationGrade",
    "JobRequirement",
    "ScrapedData",
    "GeneratedPrompt",
    "EvaluationResult",
    # Components
    "TossJobScraper",
    "PromptGenerator",
    "ResumeEvaluator",
    # Workflow
    "WorkflowConfig",
    "ResumeEvaluationWorkflow",
    "run_workflow",
]
