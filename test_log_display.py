#!/usr/bin/env python3
"""
测试新的日志文件位置显示功能
演示生成完成后如何显示详细日志文件位置
"""

import sys
sys.path.append('.')

from pathlib import Path
from services.story_video_service import StoryVideoService
from utils.logger import setup_logging

def test_log_display_functionality():
    """测试日志显示功能"""
    
    # 初始化服务和日志
    service = StoryVideoService()
    
    # 创建模拟的结果对象
    class MockResult:
        def __init__(self, processing_time=15.3):
            self.total_processing_time = processing_time
    
    content_result = MockResult(12.5)
    media_result = MockResult(8.8)
    
    # 模拟文件路径
    video_path = "output/videos/test_story_20250907.mp4" 
    content_files = {
        'summary': 'output/scripts/test_story_script.txt',
        'scenes': 'output/scenes/test_story_scenes.json'
    }
    media_files = {
        'manifest': 'output/manifests/test_story_manifest.json',
        'audio': 'output/audio/test_story_audio.wav'
    }
    
    # 确保日志目录存在并创建一些测试日志文件
    log_dir = Path("output/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建测试日志文件（模拟真实日志内容）
    test_logs = {
        "story_generator.log": """2025-09-07 22:15:00 | INFO | story_generator | 🚀 开始生成故事：测试故事
2025-09-07 22:15:05 | INFO | story_generator.content | ✅ 内容生成完成 - 输出长度: 688字符
2025-09-07 22:15:10 | INFO | story_generator.media | 🎵 音频生成完成 - 时长: 25.3s
2025-09-07 22:15:30 | INFO | story_generator.video | 🎬 视频合成完成 - 文件大小: 15.2MB
2025-09-07 22:15:35 | INFO | story_generator | ✅ 故事视频生成完成！""",
        
        "detailed.log": """2025-09-07 22:15:00 | DEBUG | story_generator | 🔍 [DEBUG] 详细调试 - 配置加载完成
2025-09-07 22:15:01 | DEBUG | story_generator.content | 🔍 [API] 请求参数 - 模型: deepseek-chat-v3.1, 温度: 0.8
2025-09-07 22:15:02 | DEBUG | story_generator.content | 🔍 [PARSE] 响应解析 - 原始长度: 1200字符""",
        
        "errors.log": """2025-09-07 22:15:15 | ERROR | story_generator.media | ❌ RunningHub任务失败 - task_id: test123, 原因: 内容过滤""",
        
        "performance.log": """2025-09-07 22:15:35 | INFO | story_generator | 📊 性能统计 - 总耗时: 35.2s, 内存峰值: 256MB"""
    }
    
    # 写入测试日志文件
    for log_file, content in test_logs.items():
        log_path = log_dir / log_file
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    # 创建一个模拟的视频文件（空文件）
    video_file = Path(video_path)
    video_file.parent.mkdir(parents=True, exist_ok=True)
    with open(video_file, 'w') as f:
        f.write("# 模拟视频文件 - 用于测试文件大小显示")
    
    print("🧪 测试新的日志显示功能...")
    print("-" * 50)
    
    # 调用改进后的完成总结方法
    service.log_completion_summary(
        content_result=content_result,
        media_result=media_result,
        video_path=video_path,
        content_files=content_files,
        media_files=media_files
    )
    
    print("\n✅ 日志显示功能测试完成！")
    print("现在当您生成故事视频时，系统会在完成后自动显示：")
    print("  - 📹 最终视频文件位置和大小")
    print("  - 📋 所有详细日志文件位置和大小")
    print("  - 🔍 查看日志的具体命令")

if __name__ == "__main__":
    test_log_display_functionality()