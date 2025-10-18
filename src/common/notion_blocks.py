"""Notion 블록 유틸리티: 텍스트 청크 분할 및 배치 추가"""

from typing import List, Dict, Any

# 안전 마진을 둔 청크 크기 (Notion rich_text 단일 content 최대 2000자 제한)
CHUNK_SIZE = 1900

# 한 번의 append 호출에 포함할 최대 블록 수 (Notion 권장 한도 100)
BATCH_SIZE = 100


def chunk_text(text: str, max_len: int = CHUNK_SIZE) -> List[str]:
  """긴 텍스트를 max_len 길이로 고정 분할

  - 단어 경계 고려 없이 단순 분할 (안정성 우선)
  - Notion API의 2000자 제한을 넘지 않도록 기본값 1900자로 분할
  """
  if not text:
    return []
  return [text[i:i + max_len] for i in range(0, len(text), max_len)]


def build_ai_feedback_blocks(feedback: str) -> List[Dict[str, Any]]:
  """AI 피드백 블록 구성: 구분선 + 헤더 + 본문(청크 단위)"""
  header_blocks: List[Dict[str, Any]] = [
    {
      "object": "block",
      "type": "divider",
      "divider": {}
    },
    {
      "object": "block",
      "type": "heading_2",
      "heading_2": {
        "rich_text": [
          {
            "type": "text",
            "text": {"content": "🤖 AI 피드백"}
          }
        ]
      }
    },
  ]

  paragraph_blocks: List[Dict[str, Any]] = [
    {
      "object": "block",
      "type": "paragraph",
      "paragraph": {
        "rich_text": [
          {
            "type": "text",
            "text": {"content": chunk}
          }
        ]
      }
    }
    for chunk in chunk_text(feedback, CHUNK_SIZE)
  ]

  return header_blocks + paragraph_blocks


async def append_blocks_batched(notion_async_client, page_id: str, blocks: List[Dict[str, Any]], batch_size: int = BATCH_SIZE) -> None:
  """블록을 batch_size 단위로 잘라 순차적으로 append 호출"""
  for i in range(0, len(blocks), batch_size):
    batch = blocks[i:i + batch_size]
    await notion_async_client.blocks.children.append(
        block_id=page_id,
        children=batch
    )

