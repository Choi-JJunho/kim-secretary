"""모든 속성을 한 번에 추가"""

import asyncio
import json
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

async def add_all_properties():
    api_key = os.getenv("NOTION_API_KEY")
    db_id = "29ab3645-abb5-80ea-9bb1-dcb7310735c7"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # 모든 속성 정의
    all_properties = {
        "이름": {
            "name": "주차"  # title 속성 이름 변경
        },
        "시작일": {
            "date": {}
        },
        "종료일": {
            "date": {}
        },
        "요약": {
            "rich_text": {}
        },
        "주요성과": {
            "rich_text": {}
        },
        "사용기술": {
            "multi_select": {
                "options": [
                    {"name": "Python", "color": "blue"},
                    {"name": "JavaScript", "color": "yellow"},
                    {"name": "TypeScript", "color": "blue"},
                    {"name": "React", "color": "blue"},
                    {"name": "FastAPI", "color": "green"},
                    {"name": "Django", "color": "green"},
                    {"name": "PostgreSQL", "color": "blue"},
                    {"name": "Redis", "color": "red"},
                    {"name": "Docker", "color": "blue"},
                    {"name": "AWS", "color": "orange"},
                    {"name": "Git", "color": "gray"}
                ]
            }
        },
        "배운점": {
            "rich_text": {}
        },
        "개선점": {
            "rich_text": {}
        },
        "성과카테고리": {
            "multi_select": {
                "options": [
                    {"name": "개발", "color": "blue"},
                    {"name": "리더십", "color": "purple"},
                    {"name": "협업", "color": "green"},
                    {"name": "문제해결", "color": "red"},
                    {"name": "학습", "color": "yellow"},
                    {"name": "코드리뷰", "color": "pink"},
                    {"name": "멘토링", "color": "orange"},
                    {"name": "문서화", "color": "gray"}
                ]
            }
        },
        "이력서반영": {
            "checkbox": {}
        },
        "AI 생성 완료": {
            "select": {
                "options": [
                    {"name": "완료", "color": "green"},
                    {"name": "미완료", "color": "gray"}
                ]
            }
        }
    }

    print("=" * 80)
    print("주간 리포트 DB 속성 추가")
    print("=" * 80)
    print(f"Database ID: {db_id}")
    print(f"추가할 속성 개수: {len(all_properties)}")
    print()

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"https://api.notion.com/v1/databases/{db_id}",
            headers=headers,
            json={"properties": all_properties},
            timeout=30.0
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            properties = data.get("properties", {})

            print(f"\n✅ 성공! 현재 총 속성: {len(properties)}개")
            print("\n속성 목록:")
            for prop_name, prop_data in properties.items():
                prop_type = prop_data.get("type")
                print(f"  ✓ {prop_name} ({prop_type})")

            # 성공 메시지
            print("\n" + "=" * 80)
            print("🎉 주간 리포트 DB 초기화 완료!")
            print("=" * 80)
            print("\nNotion에서 확인하세요:")
            print(f"https://www.notion.so/{db_id.replace('-', '')}")

        else:
            print(f"\n❌ 실패")
            print(response.text)

asyncio.run(add_all_properties())
