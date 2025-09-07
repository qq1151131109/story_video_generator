"""
测试配置文件
提供全局fixtures和测试工具
"""
import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List, Optional
from datetime import datetime

# 系统导入
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.enhanced_logger import setup_enhanced_logging
from utils.result_types import Result


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    return {
        "general": {
            "output_dir": "test_output",
            "temp_dir": "test_output/temp",
            "log_level": "DEBUG",
            "max_concurrent_tasks": 2,
            "supported_languages": ["zh", "en", "es"],
            "default_language": "zh"
        },
        "llm": {
            "default": {
                "model": "openai/gpt-3.5-turbo",
                "api_base": "https://api.openai.com/v1",
                "api_key": "test-key",
                "strict_mode": False
            },
            "script_generation": {
                "temperature": 0.8,
                "max_tokens": 1000
            }
        },
        "media": {
            "enable_integrated_generation": False,  # 测试时禁用
            "image": {
                "primary_provider": "mock",
                "resolution": "512x512"
            },
            "audio": {
                "primary_provider": "mock",
                "voice_speed": 1.0
            }
        },
        "video": {
            "resolution": "720x1280",
            "fps": 30,
            "enable_subtitles": True
        },
        "logging": {
            "level": "DEBUG",
            "console_level": "INFO",
            "max_file_size_mb": 1,
            "backup_count": 1,
            "files": {
                "main": {"filename": "test.log", "enabled": True, "level": "DEBUG"},
                "errors": {"filename": "test_errors.log", "enabled": True, "level": "ERROR"}
            }
        }
    }


@pytest.fixture
def temp_dir():
    """临时目录fixture"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def config_manager(test_config, temp_dir):
    """配置管理器fixture"""
    with patch.object(ConfigManager, '_load_main_config') as mock_load:
        mock_load.return_value = test_config
        config = ConfigManager()
        config.config = test_config
        # 设置测试输出目录
        config.config['general']['output_dir'] = str(temp_dir)
        yield config


@pytest.fixture
def file_manager(config_manager):
    """文件管理器fixture"""
    output_dir = config_manager.get('general.output_dir', 'output')
    return FileManager(output_dir)


@pytest.fixture
def logger_manager(config_manager):
    """日志管理器fixture"""
    return setup_enhanced_logging(config_manager.config)


@pytest.fixture
def sample_themes():
    """测试主题数据"""
    return {
        "chinese": [
            "康熙大帝智擒鳌拜的惊心传奇",
            "秦始皇统一六国的历史壮举",
            "唐玄宗开元盛世的辉煌"
        ],
        "english": [
            "The Fall of the Roman Empire",
            "Napoleon's Last Battle at Waterloo",
            "The Rise of Alexander the Great"
        ],
        "spanish": [
            "La conquista de América",
            "El Cid Campeador",
            "La Reconquista española"
        ],
        "edge_cases": [
            "",  # 空主题
            "a",  # 单字符
            "这是一个非常非常非常长的主题" * 10,  # 超长主题
            "特殊字符!@#$%^&*()",  # 特殊字符
            "🎬📝🎭🎪🎨",  # emoji
        ]
    }


@pytest.fixture
def mock_api_responses():
    """Mock API响应数据"""
    return {
        "openai_chat_completion": {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "这是一个关于康熙智擒鳌拜的精彩历史故事..."
                },
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200}
        },
        "runninghub_image": {
            "success": True,
            "data": {
                "task_id": "test-task-123",
                "status": "completed",
                "result_url": "https://example.com/test-image.jpg"
            }
        },
        "minimax_audio": {
            "success": True,
            "data": {
                "audio_url": "https://example.com/test-audio.mp3",
                "duration": 10.5,
                "subtitles": [
                    {"start": 0.0, "end": 5.0, "text": "你知道吗？"},
                    {"start": 5.0, "end": 10.0, "text": "康熙是如何智擒鳌拜的？"}
                ]
            }
        }
    }


@pytest.fixture
def mock_file_content():
    """Mock文件内容"""
    return {
        "test_image.jpg": b"fake_image_data",
        "test_audio.mp3": b"fake_audio_data",
        "test_video.mp4": b"fake_video_data",
        "test_subtitle.srt": "1\n00:00:00,000 --> 00:00:05,000\n你知道吗？\n\n2\n00:00:05,000 --> 00:00:10,000\n康熙是如何智擒鳌拜的？"
    }


class MockAPIClient:
    """Mock API客户端"""
    
    def __init__(self, responses: Dict[str, Any]):
        self.responses = responses
        self.call_count = 0
        self.last_request = None
    
    async def chat_completions_create(self, **kwargs):
        """Mock OpenAI聊天完成"""
        self.call_count += 1
        self.last_request = kwargs
        
        # 模拟延迟
        await asyncio.sleep(0.1)
        
        # 根据输入返回不同响应
        if "script" in str(kwargs.get('messages', '')).lower():
            return Mock(**self.responses['openai_chat_completion'])
        else:
            response = self.responses['openai_chat_completion'].copy()
            response['choices'][0]['message']['content'] = "Mock response"
            return Mock(**response)
    
    async def post_json(self, url: str, data: Dict[str, Any]):
        """Mock HTTP POST请求"""
        self.call_count += 1
        self.last_request = {"url": url, "data": data}
        
        await asyncio.sleep(0.1)
        
        if "runninghub" in url:
            return self.responses['runninghub_image']
        elif "minimax" in url:
            return self.responses['minimax_audio']
        else:
            return {"success": True, "data": {}}


@pytest.fixture
def mock_api_client(mock_api_responses):
    """Mock API客户端fixture"""
    return MockAPIClient(mock_api_responses)


@pytest.fixture
def mock_llm_client(mock_api_client):
    """Mock LLM客户端"""
    with patch('utils.llm_client_manager.LLMClientManager') as mock_class:
        mock_instance = Mock()
        mock_instance.get_client = Mock(return_value=mock_api_client)
        mock_instance.call_llm_async = AsyncMock(
            return_value=Result.success("Mock LLM response")
        )
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture  
def mock_file_operations(mock_file_content, temp_dir):
    """Mock文件操作"""
    files = {}
    
    def mock_download(url: str, filepath: Path) -> bool:
        """模拟文件下载"""
        filename = filepath.name
        if filename in mock_file_content:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(mock_file_content[filename])
            files[str(filepath)] = mock_file_content[filename]
            return True
        return False
    
    def mock_exists(filepath: Path) -> bool:
        """模拟文件存在检查"""
        return str(filepath) in files or filepath.exists()
    
    with patch('utils.file_manager.download_file', side_effect=mock_download), \
         patch.object(Path, 'exists', side_effect=mock_exists):
        yield files


@pytest.fixture
def performance_tracker():
    """性能追踪器"""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = {}
            self.start_times = {}
        
        def start(self, operation: str):
            self.start_times[operation] = datetime.now()
        
        def end(self, operation: str):
            if operation in self.start_times:
                duration = (datetime.now() - self.start_times[operation]).total_seconds()
                self.metrics[operation] = duration
                del self.start_times[operation]
                return duration
            return 0
        
        def get_metrics(self) -> Dict[str, float]:
            return self.metrics.copy()
    
    return PerformanceTracker()


# 跳过条件fixtures
@pytest.fixture
def skip_if_no_api():
    """如果没有API密钥则跳过测试"""
    import os
    if not os.getenv('OPENROUTER_API_KEY'):
        pytest.skip("No API key available")


@pytest.fixture
def skip_if_slow(request):
    """跳过慢速测试的标记"""
    if request.config.getoption("--fast-only"):
        if request.node.get_closest_marker('slow'):
            pytest.skip("Skipping slow test in fast mode")


# 参数化fixtures
@pytest.fixture(params=["zh", "en", "es"])
def language(request):
    """参数化语言fixture"""
    return request.param


@pytest.fixture(params=["康熙大帝", "Napoleon", "El Cid"])
def theme_by_language(request, language):
    """根据语言参数化主题"""
    themes = {
        "zh": "康熙大帝智擒鳌拜",
        "en": "Napoleon's Waterloo", 
        "es": "El Cid Campeador"
    }
    return themes.get(language, themes["zh"])


# 清理fixtures
@pytest.fixture(autouse=True)
def cleanup_temp_files(temp_dir):
    """自动清理临时文件"""
    yield
    # 测试结束后清理
    import shutil
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass  # 忽略清理失败


# pytest钩子函数
def pytest_configure(config):
    """pytest配置钩子"""
    # 添加自定义标记
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")


def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption(
        "--fast-only", action="store_true", default=False,
        help="只运行快速测试"
    )
    parser.addoption(
        "--api-tests", action="store_true", default=False,
        help="运行需要API密钥的测试"
    )
    parser.addoption(
        "--performance", action="store_true", default=False,
        help="运行性能测试"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    if config.getoption("--fast-only"):
        # 跳过慢速测试
        skip_slow = pytest.mark.skip(reason="Skipping slow test in fast mode")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    
    if not config.getoption("--api-tests"):
        # 跳过API测试
        skip_api = pytest.mark.skip(reason="API tests disabled")
        for item in items:
            if "api" in item.keywords:
                item.add_marker(skip_api)


@pytest.fixture
def assert_performance():
    """性能断言辅助函数"""
    def _assert_performance(actual_time: float, expected_max: float, operation: str):
        assert actual_time <= expected_max, (
            f"{operation} took {actual_time:.2f}s, "
            f"expected <= {expected_max:.2f}s"
        )
    return _assert_performance


@pytest.fixture 
def assert_memory():
    """内存断言辅助函数"""
    def _assert_memory(max_mb: float, operation: str):
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        assert memory_mb <= max_mb, (
            f"{operation} used {memory_mb:.1f}MB memory, "
            f"expected <= {max_mb:.1f}MB"
        )
    return _assert_memory