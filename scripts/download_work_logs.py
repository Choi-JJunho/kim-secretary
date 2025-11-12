"""Notion 업무일지를 로컬로 다운로드하는 스크립트"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.notion.client import NotionClient
from src.common.notion_utils import extract_page_content

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# KST timezone
KST = pytz.timezone('Asia/Seoul')


async def download_work_logs(
    database_id: str,
    output_dir: str = "./work_logs_export",
    format: str = "markdown",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
  """
  Notion 업무일지를 로컬로 다운로드

  Args:
      database_id: Notion 데이터베이스 ID
      output_dir: 저장할 디렉토리 경로
      format: 출력 형식 (markdown, json, both)
      start_date: 시작일 (YYYY-MM-DD), None이면 전체
      end_date: 종료일 (YYYY-MM-DD), None이면 전체
  """
  try:
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"📂 출력 디렉토리: {output_path.absolute()}")
    logger.info(f"📝 출력 형식: {format}")

    # Initialize Notion client
    client = NotionClient()

    # Build filter
    filter_params = None
    if start_date or end_date:
      conditions = []
      if start_date:
        conditions.append({
          "property": "작성일",
          "date": {"on_or_after": start_date}
        })
      if end_date:
        conditions.append({
          "property": "작성일",
          "date": {"on_or_before": end_date}
        })

      if len(conditions) == 1:
        filter_params = conditions[0]
      else:
        filter_params = {"and": conditions}

    # Query database
    logger.info(f"🔍 업무일지 조회 중... (DB: {database_id})")
    pages = await client.query_database(
        database_id=database_id,
        filter_params=filter_params,
        sorts=[{"property": "작성일", "direction": "ascending"}]
    )

    if not pages:
      logger.info("📭 조회된 업무일지가 없습니다.")
      return

    logger.info(f"✅ 총 {len(pages)}개의 업무일지 발견")

    # Download each page
    downloaded = 0
    failed = 0

    for i, page in enumerate(pages, 1):
      page_id = page["id"]
      properties = page.get("properties", {})

      # Extract metadata
      title_prop = properties.get("title") or properties.get("Title") or properties.get("제목", {})
      title = ""
      if title_prop.get("title"):
        title = "".join([t.get("plain_text", "") for t in title_prop["title"]])

      date_prop = properties.get("작성일", {})
      date = ""
      if date_prop.get("date"):
        date = date_prop["date"].get("start", "")

      logger.info(f"📄 [{i}/{len(pages)}] {date} - {title[:50]}...")

      try:
        # Get page content
        content = await extract_page_content(client, page_id, format="markdown")

        # Prepare metadata
        metadata = {
          "page_id": page_id,
          "title": title,
          "date": date,
          "url": f"https://notion.so/{page_id.replace('-', '')}",
          "downloaded_at": datetime.now(KST).isoformat(),
        }

        # Extract additional properties
        for prop_name, prop_value in properties.items():
          if prop_name in ["title", "Title", "제목", "작성일"]:
            continue

          prop_type = prop_value.get("type")

          if prop_type == "select":
            select_value = prop_value.get("select")
            if select_value:
              metadata[prop_name] = select_value.get("name", "")

          elif prop_type == "multi_select":
            multi_select_values = prop_value.get("multi_select", [])
            metadata[prop_name] = [v.get("name", "") for v in multi_select_values]

          elif prop_type == "rich_text":
            rich_text = prop_value.get("rich_text", [])
            metadata[prop_name] = "".join([t.get("plain_text", "") for t in rich_text])

        # Create filename
        safe_date = date.replace("-", "") if date else "unknown"
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))[:50]
        safe_title = safe_title.strip() or "untitled"
        base_filename = f"{safe_date}_{safe_title}"

        # Save markdown
        if format in ["markdown", "both"]:
          md_file = output_path / f"{base_filename}.md"
          with open(md_file, "w", encoding="utf-8") as f:
            # Write frontmatter
            f.write("---\n")
            f.write(f"title: {title}\n")
            f.write(f"date: {date}\n")
            f.write(f"page_id: {page_id}\n")
            f.write(f"url: {metadata['url']}\n")
            f.write("---\n\n")
            # Write content
            f.write(content)
          logger.info(f"  ✅ 마크다운 저장: {md_file.name}")

        # Save JSON
        if format in ["json", "both"]:
          json_file = output_path / f"{base_filename}.json"
          with open(json_file, "w", encoding="utf-8") as f:
            json.dump({
              "metadata": metadata,
              "content": content,
              "properties": properties
            }, f, ensure_ascii=False, indent=2)
          logger.info(f"  ✅ JSON 저장: {json_file.name}")

        downloaded += 1

      except Exception as e:
        logger.error(f"  ❌ 다운로드 실패: {e}")
        failed += 1

    # Save index
    logger.info("\n📑 인덱스 파일 생성 중...")
    index = {
      "total": len(pages),
      "downloaded": downloaded,
      "failed": failed,
      "download_date": datetime.now(KST).isoformat(),
      "database_id": database_id,
      "date_range": {
        "start": start_date,
        "end": end_date
      },
      "pages": []
    }

    for page in pages:
      page_id = page["id"]
      properties = page.get("properties", {})

      title_prop = properties.get("title") or properties.get("Title") or properties.get("제목", {})
      title = ""
      if title_prop.get("title"):
        title = "".join([t.get("plain_text", "") for t in title_prop["title"]])

      date_prop = properties.get("작성일", {})
      date = ""
      if date_prop.get("date"):
        date = date_prop["date"].get("start", "")

      index["pages"].append({
        "page_id": page_id,
        "title": title,
        "date": date,
        "url": f"https://notion.so/{page_id.replace('-', '')}"
      })

    index_file = output_path / "index.json"
    with open(index_file, "w", encoding="utf-8") as f:
      json.dump(index, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 인덱스 저장: {index_file.name}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ 다운로드 완료!")
    print("=" * 80)
    print(f"\n📊 총 업무일지: {len(pages)}개")
    print(f"✅ 다운로드 성공: {downloaded}개")
    print(f"❌ 다운로드 실패: {failed}개")
    print(f"📂 저장 위치: {output_path.absolute()}")
    print(f"📝 출력 형식: {format}")
    print("\n" + "=" * 80 + "\n")

  except Exception as e:
    logger.error(f"❌ 다운로드 실패: {e}", exc_info=True)


async def main():
  """메인 함수"""
  try:
    load_dotenv()

    # Get DB IDs from environment
    user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")

    if not user_db_mapping_str or user_db_mapping_str == "{}":
      logger.error("❌ NOTION_USER_DATABASE_MAPPING 환경 변수가 설정되지 않았습니다!")
      logger.info("환경 변수 형식:")
      logger.info('{"USER_ID":{"alias":"홍길동","work_log_db":"DB_ID"}}')
      return

    try:
      user_db_mapping = json.loads(user_db_mapping_str)
    except json.JSONDecodeError as e:
      logger.error(f"❌ JSON 파싱 실패: {e}")
      return

    # Get first user's DB IDs
    if not user_db_mapping:
      logger.error("❌ 데이터베이스 매핑이 비어있습니다!")
      return

    user_id = list(user_db_mapping.keys())[0]
    user_dbs = user_db_mapping[user_id]

    user_alias = user_dbs.get("alias", "이름없음")
    work_log_db_id = user_dbs.get("work_log_db")

    if not work_log_db_id:
      logger.error("❌ work_log_db ID가 설정되지 않았습니다!")
      return

    logger.info(f"✅ DB 설정 확인 완료")
    logger.info(f"  User: {user_alias} ({user_id})")
    logger.info(f"  Work Log DB: {work_log_db_id}")

    # Check if running interactively
    is_interactive = sys.stdin.isatty()

    print("\n" + "=" * 80)
    print("Notion 업무일지 다운로드")
    print("=" * 80)

    if is_interactive:
      # Interactive mode
      output_dir = input("\n저장 디렉토리 (기본값: ./work_logs_export): ").strip() or "./work_logs_export"

      print("\n출력 형식 선택:")
      print("  1. markdown - 마크다운 파일로 저장")
      print("  2. json - JSON 파일로 저장 (메타데이터 포함)")
      print("  3. both - 마크다운 + JSON 모두 저장")
      format_choice = input("선택 (기본값: markdown): ").strip() or "1"

      format_map = {"1": "markdown", "2": "json", "3": "both"}
      format = format_map.get(format_choice, "markdown")

      print("\n날짜 범위 선택 (전체 다운로드하려면 Enter):")
      start_date = input("시작일 (YYYY-MM-DD): ").strip() or None
      end_date = input("종료일 (YYYY-MM-DD): ").strip() or None

    else:
      # Non-interactive mode: use command-line args
      output_dir = sys.argv[1] if len(sys.argv) > 1 else "./work_logs_export"
      format = sys.argv[2] if len(sys.argv) > 2 else "markdown"
      start_date = sys.argv[3] if len(sys.argv) > 3 else None
      end_date = sys.argv[4] if len(sys.argv) > 4 else None

      logger.info(f"🤖 Non-interactive mode detected")
      logger.info(f"  출력 디렉토리: {output_dir}")
      logger.info(f"  출력 형식: {format}")
      if start_date:
        logger.info(f"  시작일: {start_date}")
      if end_date:
        logger.info(f"  종료일: {end_date}")

    print("\n" + "=" * 80)
    logger.info(f"🚀 다운로드 시작")
    print("=" * 80 + "\n")

    # Download
    await download_work_logs(
        database_id=work_log_db_id,
        output_dir=output_dir,
        format=format,
        start_date=start_date,
        end_date=end_date
    )

  except Exception as e:
    logger.error(f"❌ 실행 실패: {e}", exc_info=True)


if __name__ == "__main__":
  asyncio.run(main())
