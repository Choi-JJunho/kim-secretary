"""데이터베이스 속성 검사 스크립트"""

import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.notion.client import NotionClient


async def inspect_database(db_id: str):
  """데이터베이스 속성 검사"""
  client = NotionClient()

  print(f"\n{'='*80}")
  print(f"데이터베이스 검사: {db_id}")
  print(f"{'='*80}\n")

  db_info = await client.get_database(db_id)

  print(f"Database Title: {db_info.get('title', [{}])[0].get('plain_text', 'N/A')}")
  print(f"Object Type: {db_info.get('object', 'N/A')}")

  # Print raw properties structure for debugging
  print(f"\nRaw response keys: {list(db_info.keys())}")

  # Check if this is a database view
  data_sources = db_info.get('data_sources', [])
  if data_sources:
    print(f"\n⚠️ This is a DATABASE VIEW!")
    print(f"Data sources: {len(data_sources)}")
    for i, source in enumerate(data_sources, 1):
      print(f"  Source {i}: {json.dumps(source, indent=4)}")

  print(f"\nProperties:")
  print("-" * 80)

  properties = db_info.get('properties', {})

  if not properties:
    print("⚠️ No properties found!")
  else:
    for prop_name, prop_data in properties.items():
      prop_type = prop_data.get('type', 'unknown')
      print(f"  {prop_name:30s} : {prop_type:15s}")
      if prop_type == 'title':
        print(f"    └─ ⭐ TITLE PROPERTY")

  print("-" * 80)
  print(f"Total properties: {len(properties)}")
  print()


async def main():
  load_dotenv()

  user_db_mapping_str = os.getenv("NOTION_USER_DATABASE_MAPPING", "{}")
  user_db_mapping = json.loads(user_db_mapping_str)

  if not user_db_mapping:
    print("❌ No database mapping found!")
    return

  user_id = list(user_db_mapping.keys())[0]
  user_dbs = user_db_mapping[user_id]

  monthly_report_db_id = user_dbs.get("monthly_report_db")
  weekly_report_db_id = user_dbs.get("weekly_report_db")

  # Also check source databases
  monthly_source_db_id = "29ab3645-abb5-80c8-86d6-000b5a450b39"
  weekly_source_db_id = "29ab3645-abb5-8002-88aa-000bfe8fe658"

  print("=" * 80)
  print("VIEWS:")
  print("=" * 80)

  if monthly_report_db_id:
    await inspect_database(monthly_report_db_id)

  if weekly_report_db_id:
    await inspect_database(weekly_report_db_id)

  print("\n" + "=" * 80)
  print("SOURCE DATABASES:")
  print("=" * 80)

  await inspect_database(monthly_source_db_id)
  await inspect_database(weekly_source_db_id)


if __name__ == "__main__":
  asyncio.run(main())
