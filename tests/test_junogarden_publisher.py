"""JunogardenPublisher 유닛 테스트"""

import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.github.junogarden_publisher import JunogardenPublisher


class TestJunogardenPublisher(unittest.TestCase):
    """JunogardenPublisher 기본 테스트"""

    def setUp(self):
        """테스트 환경 설정"""
        # 임시 디렉토리 생성
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "junogarden-web"

        # 환경 변수 설정
        os.environ["JUNOGARDEN_REPO_PATH"] = str(self.repo_path)
        os.environ["GITHUB_TOKEN"] = "test_token"
        os.environ["GITHUB_REPO_URL"] = "https://github.com/test/repo.git"

    def tearDown(self):
        """테스트 정리"""
        # 임시 디렉토리 삭제
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

        # 환경 변수 정리
        for key in ["JUNOGARDEN_REPO_PATH", "GITHUB_TOKEN", "GITHUB_REPO_URL"]:
            if key in os.environ:
                del os.environ[key]

    def test_init(self):
        """초기화 테스트"""
        publisher = JunogardenPublisher()

        self.assertEqual(publisher.repo_path, self.repo_path)
        self.assertEqual(publisher.github_token, "test_token")
        self.assertEqual(publisher.repo_url, "https://github.com/test/repo.git")

    def test_generate_frontmatter(self):
        """Frontmatter 생성 테스트"""
        publisher = JunogardenPublisher()

        frontmatter = publisher._generate_frontmatter(
            title="테스트 제목",
            date="2025-12-08",
            description="테스트 설명",
            tags=["Python", "Test"]
        )

        self.assertIn('title: "테스트 제목"', frontmatter)
        self.assertIn("date: 2025-12-08", frontmatter)
        self.assertIn('description: "테스트 설명"', frontmatter)
        self.assertIn("tags: ['Python', 'Test']", frontmatter)

    def test_generate_frontmatter_no_tags(self):
        """태그 없는 Frontmatter 생성 테스트"""
        publisher = JunogardenPublisher()

        frontmatter = publisher._generate_frontmatter(
            title="테스트",
            date="2025-12-08",
            description="설명"
        )

        self.assertIn("tags: []", frontmatter)


class TestJunogardenPublisherAsync(unittest.TestCase):
    """JunogardenPublisher 비동기 테스트"""

    def setUp(self):
        """테스트 환경 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "junogarden-web"
        os.environ["JUNOGARDEN_REPO_PATH"] = str(self.repo_path)
        os.environ["GITHUB_TOKEN"] = "test_token"
        os.environ["GITHUB_REPO_URL"] = "https://github.com/test/repo.git"

    def tearDown(self):
        """테스트 정리"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

        for key in ["JUNOGARDEN_REPO_PATH", "GITHUB_TOKEN", "GITHUB_REPO_URL"]:
            if key in os.environ:
                del os.environ[key]

    def test_publish_work_log_creates_file(self):
        """publish_work_log가 파일을 생성하는지 테스트"""
        async def run_test():
            publisher = JunogardenPublisher()

            # Git 명령어 모킹
            with patch.object(publisher, 'ensure_repo', new_callable=AsyncMock) as mock_ensure:
                mock_ensure.return_value = True

                with patch.object(publisher, '_run_git', new_callable=AsyncMock) as mock_git:
                    mock_git.return_value = (True, "")

                    # 저장소 디렉토리 생성
                    self.repo_path.mkdir(parents=True, exist_ok=True)

                    result = await publisher.publish_work_log(
                        date="2025-12-08",
                        content="## 오늘 한 일\n- 테스트",
                        title="2025-12-08 업무일지",
                        tags=["Python"]
                    )

                    self.assertTrue(result["success"])
                    self.assertIn("file_path", result)

                    # 파일이 생성되었는지 확인
                    file_path = self.repo_path / "content" / "work-logs" / "daily" / "2025-12-08.md"
                    self.assertTrue(file_path.exists())

                    # 내용 확인
                    content = file_path.read_text(encoding="utf-8")
                    self.assertIn("2025-12-08 업무일지", content)
                    self.assertIn("## 오늘 한 일", content)

        asyncio.run(run_test())

    def test_get_work_log_count(self):
        """업무일지 개수 조회 테스트"""
        async def run_test():
            publisher = JunogardenPublisher()

            # 디렉토리가 없을 때
            count = await publisher.get_work_log_count()
            self.assertEqual(count, 0)

            # 파일 생성
            work_logs_dir = self.repo_path / "content" / "work-logs" / "daily"
            work_logs_dir.mkdir(parents=True, exist_ok=True)
            (work_logs_dir / "2025-12-01.md").write_text("test1")
            (work_logs_dir / "2025-12-02.md").write_text("test2")
            (work_logs_dir / "2025-12-03.md").write_text("test3")

            count = await publisher.get_work_log_count()
            self.assertEqual(count, 3)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
