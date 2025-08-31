#!/usr/bin/env python3
"""
快速视频生成测试 - 测试修复后的同步功能
"""

import asyncio
import sys
from pathlib import Path
import time

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from load_env import load_env_file
load_env_file()

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from content.script_generator import ScriptGenerator, ScriptGenerationRequest
from content.scene_splitter import SceneSplitter, SceneSplitRequest
from media.image_generator import ImageGenerator, ImageGenerationRequest
from media.audio_generator import AudioGenerator, AudioGenerationRequest
from video.subtitle_processor import SubtitleProcessor, SubtitleRequest, SubtitleSegment
from full_video_demo import VideoComposer

async def main():
    """快速测试主函数"""
    print("🎯 快速视频生成测试")
    print("=" * 50)
    
    # 初始化组件
    config = ConfigManager()
    cache = CacheManager()
    file_manager = FileManager()
    setup_logging()
    
    audio_generator = AudioGenerator(config, cache, file_manager)
    subtitle_processor = SubtitleProcessor(config, file_manager)
    video_composer = VideoComposer(config, file_manager)
    
    # 简化内容
    test_text = "秦始皇焚书坑儒，这是中国历史上的重大事件。"
    
    print("🔊 生成音频...")
    audio_request = AudioGenerationRequest(
        text=test_text,
        language="zh",
        speed=1.0
    )
    
    try:
        audio_result = await audio_generator.generate_audio_async(audio_request)
        print(f"✅ 音频生成成功: {audio_result.duration_seconds:.2f}秒")
        
        # 生成字幕
        print("📝 生成字幕...")
        subtitle_segments = []
        
        if audio_result.subtitles:
            print(f"✅ 使用TTS字幕: {len(audio_result.subtitles)}段")
            for audio_sub in audio_result.subtitles:
                subtitle_segments.append(SubtitleSegment(
                    text=audio_sub.text,
                    start_time=audio_sub.start_time,
                    end_time=audio_sub.end_time,
                    duration=audio_sub.duration
                ))
        else:
            print("⚠️  使用时长分割字幕")
            subtitle_request = SubtitleRequest(
                text=test_text,
                scene_duration=audio_result.duration_seconds,
                language="zh",
                max_line_length=20
            )
            subtitle_segments = subtitle_processor.process_subtitle(subtitle_request)
        
        # 保存字幕文件
        subtitle_file = file_manager.get_output_path('subtitles', 'quick_test.srt')
        subtitle_processor.save_subtitle_file(subtitle_segments, subtitle_file)
        print(f"✅ 字幕保存: {Path(subtitle_file).name}")
        
        # 创建简单场景
        from content.scene_splitter import Scene
        
        scene = Scene(
            sequence=1,
            content=test_text,
            subtitle_text=test_text,
            duration_seconds=audio_result.duration_seconds,
            image_prompt="古代中国秦朝宫殿，恢宏壮观",
            animation_type="zoom_in"
        )
        
        # 跳过图像生成，直接使用黑色背景测试
        print("⚠️  跳过图像生成，使用黑色背景")
        images = [None]
        
        # 生成视频
        print("🎞️ 合成视频...")
        timestamp = int(time.time())
        output_video = file_manager.get_output_path('videos', f'quick_test_{timestamp}.mp4')
        
        print(f"🔍 音频文件路径: {audio_result.file_path}")
        
        final_video = video_composer.create_video(
            scenes=[scene],
            images=images,
            audio_file=audio_result.file_path,
            subtitle_file=subtitle_file,
            output_path=output_video,
            audio_duration=audio_result.duration_seconds
        )
        
        if final_video:
            print(f"🎉 视频生成成功!")
            print(f"📹 文件: {Path(final_video).name}")
            print(f"📁 路径: {final_video}")
            
            # 显示视频信息
            import subprocess
            import json
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(final_video)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                duration = float(info['format']['duration'])
                file_size = int(info['format']['size']) / 1024 / 1024
                
                for stream in info['streams']:
                    if stream['codec_type'] == 'video':
                        width = stream.get('width')
                        height = stream.get('height')
                        print(f"⏱️ 时长: {duration:.1f}秒")
                        print(f"📺 分辨率: {width}x{height}")
                        print(f"💾 大小: {file_size:.1f}MB")
                        break
            
            return True
        else:
            print("❌ 视频合成失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)