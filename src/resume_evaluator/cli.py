"""CLI 인터페이스"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .workflow import ResumeEvaluationWorkflow, WorkflowConfig


def setup_logging(verbose: bool = False) -> None:
    """로깅 설정"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_parser() -> argparse.ArgumentParser:
    """CLI 파서 생성"""
    parser = argparse.ArgumentParser(
        prog="resume-evaluator",
        description="토스 Backend 포지션 이력서 평가 AI Agent",
    )

    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # scrape 명령어
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="토스 채용공고에서 인재상 스크래핑"
    )
    scrape_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="기존 데이터가 있어도 강제로 스크래핑"
    )
    scrape_parser.add_argument(
        "--no-headless",
        action="store_true",
        help="브라우저 표시 (디버깅용)"
    )

    # generate 명령어
    generate_parser = subparsers.add_parser(
        "generate",
        help="시스템 프롬프트 생성"
    )
    generate_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="데이터 변경 없어도 강제 재생성"
    )
    generate_parser.add_argument(
        "--position", "-p",
        default="Backend",
        help="타겟 포지션 (기본: Backend)"
    )

    # evaluate 명령어
    eval_parser = subparsers.add_parser(
        "evaluate",
        help="이력서 평가"
    )
    eval_parser.add_argument(
        "resume",
        help="이력서 파일 경로 (PDF, MD, TXT, JSON)"
    )
    eval_parser.add_argument(
        "--position", "-p",
        default="Server Developer",
        help="지원 포지션 (기본: Server Developer)"
    )
    eval_parser.add_argument(
        "--provider",
        choices=["claude", "gemini", "ollama"],
        default="claude",
        help="AI 제공자 (기본: claude)"
    )
    eval_parser.add_argument(
        "--output", "-o",
        help="결과 저장 파일 (JSON)"
    )
    eval_parser.add_argument(
        "--raw",
        action="store_true",
        help="원본 AI 응답 포함"
    )

    # status 명령어
    status_parser = subparsers.add_parser(
        "status",
        help="워크플로우 상태 확인"
    )

    # init 명령어
    init_parser = subparsers.add_parser(
        "init",
        help="워크플로우 전체 초기화 (스크래핑 + 프롬프트 생성)"
    )
    init_parser.add_argument(
        "--force-scrape",
        action="store_true",
        help="강제 스크래핑"
    )
    init_parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="강제 프롬프트 재생성"
    )
    init_parser.add_argument(
        "--no-headless",
        action="store_true",
        help="브라우저 표시 (디버깅용)"
    )

    # 공통 옵션
    parser.add_argument(
        "--data-dir",
        default="data/resume_evaluator",
        help="데이터 디렉토리 (기본: data/resume_evaluator)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력"
    )

    return parser


async def cmd_scrape(args: argparse.Namespace) -> int:
    """scrape 명령어 실행"""
    from .scraper import TossJobScraper

    scraper = TossJobScraper(data_dir=args.data_dir)

    # 기존 데이터 확인
    if not args.force:
        existing = scraper.load_scraped_data()
        if existing:
            print(f"📦 기존 스크래핑 데이터 존재:")
            print(f"   - 포지션 수: {len(existing.positions)}개")
            print(f"   - 스크래핑 시간: {existing.scraped_at}")
            print(f"   - 해시: {existing.content_hash}")
            print("\n💡 강제 스크래핑: --force 옵션 사용")
            return 0

    # 스크래핑 실행
    headless = not args.no_headless
    data = await scraper.scrape_all_server_positions(headless=headless)
    scraper.save_scraped_data(data)

    print(f"\n✅ 스크래핑 완료:")
    print(f"   - 포지션 수: {len(data.positions)}개")
    for pos in data.positions:
        print(f"     • {pos.title} ({pos.company}) - 인재상 {len(pos.requirements)}개")

    return 0


async def cmd_generate(args: argparse.Namespace) -> int:
    """generate 명령어 실행"""
    from .scraper import TossJobScraper
    from .prompt_generator import PromptGenerator

    scraper = TossJobScraper(data_dir=args.data_dir)
    generator = PromptGenerator(data_dir=args.data_dir)

    # 스크래핑 데이터 로드
    scraped_data = scraper.load_scraped_data()
    if not scraped_data:
        print("❌ 스크래핑 데이터가 없습니다. 먼저 'scrape' 명령을 실행하세요.")
        return 1

    # 재생성 필요 여부 확인
    if not args.force:
        if not generator.needs_regeneration(scraped_data.content_hash):
            existing = generator.load_prompt()
            if existing:
                print(f"📦 기존 시스템 프롬프트 존재 (변경 없음):")
                print(f"   - 생성 시간: {existing.generated_at}")
                print(f"   - 프롬프트 길이: {len(existing.prompt)}자")
                print("\n💡 강제 재생성: --force 옵션 사용")
                return 0

    # 프롬프트 생성
    prompt = generator.generate_system_prompt(
        scraped_data=scraped_data,
        target_position=args.position
    )
    generator.save_prompt(prompt)

    print(f"\n✅ 시스템 프롬프트 생성 완료:")
    print(f"   - 타겟 포지션: {args.position}")
    print(f"   - 프롬프트 길이: {len(prompt.prompt)}자")
    print(f"   - 소스 해시: {prompt.source_hash}")

    return 0


async def cmd_evaluate(args: argparse.Namespace) -> int:
    """evaluate 명령어 실행"""
    # 이력서 파일 확인
    resume_path = Path(args.resume)
    if not resume_path.exists():
        print(f"❌ 이력서 파일을 찾을 수 없습니다: {resume_path}")
        return 1

    # 워크플로우 설정
    config = WorkflowConfig(
        data_dir=args.data_dir,
        ai_provider=args.provider,
    )

    workflow = ResumeEvaluationWorkflow(config)

    # 초기화 (프롬프트 로드)
    try:
        workflow.evaluator.load_system_prompt_from_file()
    except FileNotFoundError:
        print("❌ 시스템 프롬프트가 없습니다. 먼저 'init' 명령을 실행하세요.")
        return 1

    workflow._initialized = True

    # 평가 실행
    print(f"🔍 이력서 평가 중: {resume_path}")
    print(f"   - 포지션: {args.position}")
    print(f"   - AI: {args.provider}")
    print()

    result = await workflow.evaluate_resume_file(str(resume_path), args.position)

    # 결과 출력
    print(workflow.format_result(result))

    # 결과 저장
    if args.output:
        output_data = result.to_dict()
        if args.raw:
            output_data["raw_response"] = result.raw_response

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"💾 결과 저장: {args.output}")

    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    """status 명령어 실행"""
    from .scraper import TossJobScraper
    from .prompt_generator import PromptGenerator

    data_dir = Path(args.data_dir)

    print("📊 워크플로우 상태")
    print("=" * 50)
    print(f"데이터 디렉토리: {data_dir}")
    print()

    # 스크래핑 데이터 상태
    scraper = TossJobScraper(data_dir=args.data_dir)
    scraped_data = scraper.load_scraped_data()

    print("📡 스크래핑 데이터:")
    if scraped_data:
        print(f"   ✅ 존재함")
        print(f"   - 포지션 수: {len(scraped_data.positions)}개")
        print(f"   - 스크래핑 시간: {scraped_data.scraped_at}")
        print(f"   - 콘텐츠 해시: {scraped_data.content_hash}")
    else:
        print("   ❌ 없음")
    print()

    # 프롬프트 상태
    generator = PromptGenerator(data_dir=args.data_dir)
    prompt = generator.load_prompt()

    print("📝 시스템 프롬프트:")
    if prompt:
        print(f"   ✅ 존재함")
        print(f"   - 생성 시간: {prompt.generated_at}")
        print(f"   - 타겟 포지션: {prompt.target_position}")
        print(f"   - 프롬프트 길이: {len(prompt.prompt)}자")
        print(f"   - 소스 해시: {prompt.source_hash}")

        # 해시 불일치 확인
        if scraped_data and prompt.source_hash != scraped_data.content_hash:
            print("   ⚠️ 경고: 스크래핑 데이터와 해시가 일치하지 않습니다. 프롬프트 재생성이 필요할 수 있습니다.")
    else:
        print("   ❌ 없음")

    return 0


async def cmd_init(args: argparse.Namespace) -> int:
    """init 명령어 실행"""
    config = WorkflowConfig(
        data_dir=args.data_dir,
        force_scrape=args.force_scrape,
        force_regenerate=args.force_regenerate,
        headless=not args.no_headless,
    )

    workflow = ResumeEvaluationWorkflow(config)

    print("🚀 워크플로우 초기화 시작...")
    success = await workflow.initialize()

    if success:
        print("\n✅ 워크플로우 초기화 완료!")
        status = workflow.get_status()
        print(f"\n📊 상태:")
        print(f"   - 스크래핑 포지션: {status.get('scraped_data', {}).get('positions_count', 0)}개")
        print(f"   - 프롬프트 길이: {status.get('generated_prompt', {}).get('prompt_length', 0)}자")
        return 0
    else:
        print("\n❌ 워크플로우 초기화 실패")
        return 1


def main() -> int:
    """CLI 메인 함수"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    setup_logging(args.verbose)

    # 명령어 실행
    commands = {
        "scrape": cmd_scrape,
        "generate": cmd_generate,
        "evaluate": cmd_evaluate,
        "status": cmd_status,
        "init": cmd_init,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return asyncio.run(cmd_func(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
