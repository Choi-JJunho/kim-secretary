"""Notion API 직접 테스트"""

import asyncio
import json
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

async def test_database_api():
    api_key = os.getenv("NOTION_API_KEY")
    db_id = "29ab3645-abb5-80ea-9bb1-dcb7310735c7"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # 1. GET database
    print("=" * 80)
    print("1. GET /v1/databases/{database_id}")
    print("=" * 80)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.notion.com/v1/databases/{db_id}",
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # properties 키 확인
        if "properties" in data:
            print(f"\n✅ properties 키 존재: {len(data['properties'])}개")
        else:
            print(f"\n❌ properties 키 없음!")
            print(f"응답 키 목록: {list(data.keys())}")

        # 2. PATCH database - 속성 추가 시도
        print("\n" + "=" * 80)
        print("2. PATCH /v1/databases/{database_id} - 속성 추가")
        print("=" * 80)

        update_data = {
            "properties": {
                "테스트속성": {
                    "rich_text": {}
                }
            }
        }

        print("전송 데이터:")
        print(json.dumps(update_data, indent=2, ensure_ascii=False))

        patch_response = await client.patch(
            f"https://api.notion.com/v1/databases/{db_id}",
            headers=headers,
            json=update_data
        )

        print(f"\nStatus: {patch_response.status_code}")
        patch_data = patch_response.json()
        print(json.dumps(patch_data, indent=2, ensure_ascii=False))

        if "properties" in patch_data:
            print(f"\n✅ PATCH 후 properties: {len(patch_data['properties'])}개")
            for prop_name in patch_data['properties'].keys():
                print(f"  - {prop_name}")
        else:
            print(f"\n❌ PATCH 후에도 properties 없음!")

asyncio.run(test_database_api())
