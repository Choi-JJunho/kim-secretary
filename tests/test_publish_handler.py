"""publish_handler 유닛 테스트"""

import unittest

from src.commands.publish_handler import (
    parse_publish_message,
    extract_title_from_page,
    extract_tags_from_page,
    extract_date_from_page,
)


class TestParsePublishMessage(unittest.TestCase):
    """parse_publish_message 함수 테스트"""

    def test_valid_message(self):
        """유효한 메시지 파싱"""
        message = '{"action":"publish_work_log","date":"2025-12-08","page_id":"abc123","user_id":"U12345678","update_portfolio":true}'

        result = parse_publish_message(message)

        self.assertIsNotNone(result)
        self.assertEqual(result["date"], "2025-12-08")
        self.assertEqual(result["page_id"], "abc123")
        self.assertEqual(result["user_id"], "U12345678")
        self.assertTrue(result["update_portfolio"])

    def test_minimal_message(self):
        """최소 필드만 있는 메시지"""
        message = '{"action":"publish_work_log","page_id":"abc123"}'

        result = parse_publish_message(message)

        self.assertIsNotNone(result)
        self.assertEqual(result["page_id"], "abc123")
        self.assertIsNone(result["date"])
        self.assertIsNone(result["user_id"])
        self.assertFalse(result["update_portfolio"])

    def test_wrong_action(self):
        """다른 action인 경우"""
        message = '{"action":"work_log_feedback","date":"2025-12-08"}'

        result = parse_publish_message(message)

        self.assertIsNone(result)

    def test_invalid_json(self):
        """잘못된 JSON"""
        message = "not json"

        result = parse_publish_message(message)

        self.assertIsNone(result)

    def test_empty_message(self):
        """빈 메시지"""
        result = parse_publish_message("")

        self.assertIsNone(result)


class TestExtractTitleFromPage(unittest.TestCase):
    """extract_title_from_page 함수 테스트"""

    def test_korean_title_property(self):
        """'제목' 속성에서 제목 추출"""
        page = {
            "properties": {
                "제목": {
                    "type": "title",
                    "title": [{"plain_text": "테스트 제목"}]
                }
            }
        }

        result = extract_title_from_page(page)

        self.assertEqual(result, "테스트 제목")

    def test_english_title_property(self):
        """'Title' 속성에서 제목 추출"""
        page = {
            "properties": {
                "Title": {
                    "type": "title",
                    "title": [{"plain_text": "Test Title"}]
                }
            }
        }

        result = extract_title_from_page(page)

        self.assertEqual(result, "Test Title")

    def test_multiple_text_parts(self):
        """여러 텍스트 조각으로 구성된 제목"""
        page = {
            "properties": {
                "제목": {
                    "type": "title",
                    "title": [
                        {"plain_text": "Part 1 "},
                        {"plain_text": "Part 2"}
                    ]
                }
            }
        }

        result = extract_title_from_page(page)

        self.assertEqual(result, "Part 1 Part 2")

    def test_no_title_property(self):
        """title 속성이 없는 경우"""
        page = {
            "properties": {
                "Description": {
                    "type": "rich_text",
                    "rich_text": []
                }
            }
        }

        result = extract_title_from_page(page)

        self.assertEqual(result, "")


class TestExtractTagsFromPage(unittest.TestCase):
    """extract_tags_from_page 함수 테스트"""

    def test_multi_select_tags(self):
        """multi_select 태그 추출"""
        page = {
            "properties": {
                "기술스택": {
                    "type": "multi_select",
                    "multi_select": [
                        {"name": "Python"},
                        {"name": "Docker"},
                        {"name": "Kubernetes"}
                    ]
                }
            }
        }

        result = extract_tags_from_page(page)

        self.assertEqual(result, ["Python", "Docker", "Kubernetes"])

    def test_english_tags_property(self):
        """'Tags' 속성에서 추출"""
        page = {
            "properties": {
                "Tags": {
                    "type": "multi_select",
                    "multi_select": [
                        {"name": "backend"},
                        {"name": "api"}
                    ]
                }
            }
        }

        result = extract_tags_from_page(page)

        self.assertEqual(result, ["backend", "api"])

    def test_select_tag(self):
        """단일 select 태그"""
        page = {
            "properties": {
                "태그": {
                    "type": "select",
                    "select": {"name": "Important"}
                }
            }
        }

        result = extract_tags_from_page(page)

        self.assertEqual(result, ["Important"])

    def test_no_tags(self):
        """태그가 없는 경우"""
        page = {
            "properties": {}
        }

        result = extract_tags_from_page(page)

        self.assertEqual(result, [])


class TestExtractDateFromPage(unittest.TestCase):
    """extract_date_from_page 함수 테스트"""

    def test_korean_date_property(self):
        """'작성일' 속성에서 날짜 추출"""
        page = {
            "properties": {
                "작성일": {
                    "type": "date",
                    "date": {"start": "2025-12-08T09:00:00.000+09:00"}
                }
            }
        }

        result = extract_date_from_page(page, "2025-01-01")

        self.assertEqual(result, "2025-12-08")

    def test_english_date_property(self):
        """'Date' 속성에서 날짜 추출"""
        page = {
            "properties": {
                "Date": {
                    "type": "date",
                    "date": {"start": "2025-12-15"}
                }
            }
        }

        result = extract_date_from_page(page, "2025-01-01")

        self.assertEqual(result, "2025-12-15")

    def test_fallback_date(self):
        """날짜 속성이 없을 때 fallback 사용"""
        page = {
            "properties": {}
        }

        result = extract_date_from_page(page, "2025-01-01")

        self.assertEqual(result, "2025-01-01")

    def test_null_date(self):
        """date가 null인 경우"""
        page = {
            "properties": {
                "작성일": {
                    "type": "date",
                    "date": None
                }
            }
        }

        result = extract_date_from_page(page, "2025-01-01")

        self.assertEqual(result, "2025-01-01")


if __name__ == "__main__":
    unittest.main()
