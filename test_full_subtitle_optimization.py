#!/usr/bin/env python3
"""
完整的字幕优化系统测试
"""
import sys
sys.path.append('/home/shenglin/Desktop/story_video_generator')

import asyncio
from content.scene_splitter import SceneSplitter, SceneSplitRequest
from video.subtitle_engine import SubtitleEngine, SubtitleRequest
from core.config_manager import ConfigManager
from utils.file_manager import FileManager

async def test_full_subtitle_optimization():
    """测试完整的字幕优化流程"""
    print("🎬 完整字幕优化系统测试")
    print("=" * 70)
    
    # 初始化
    config = ConfigManager()
    file_manager = FileManager(config.get('general', {}).get('output_dir', 'output'))
    scene_splitter = SceneSplitter(config, None, None)
    subtitle_engine = SubtitleEngine(config, file_manager)
    
    # 测试文案 - 包含已知的超长场景
    test_script = """你是万历年的新科进士，初授浙江钱塘县令，辖区豪绅垄断漕运，上级知府暗中索贿。才到任三天，师爷就递来账本，低声说"郭尚书家三公子强占民田，苦主悬梁自尽"。你拍案要查，当夜书房窗棂突然射进一支毒箭。"""
    
    print("🔍 阶段1: 场景分割测试")
    print("-" * 40)
    
    scene_request = SceneSplitRequest(
        script_content=test_script,
        language="zh",
        use_coze_rules=True
    )
    
    scene_result = await scene_splitter.split_scenes_async(scene_request)
    
    print(f"场景分割结果: {len(scene_result.scenes)}个场景")
    for i, scene in enumerate(scene_result.scenes, 1):
        length = len(scene.content)
        status = "🔴 超长" if length > 25 else "🟡 偏长" if length > 20 else "🟢 合适"
        print(f"  场景{i}: {length}字符 {status} | {scene.content}")
    
    print()
    
    print("🔍 阶段2: 字幕分割测试")
    print("-" * 40)
    
    for i, scene in enumerate(scene_result.scenes, 1):
        print(f"场景{i}字幕处理:")
        print(f"  原文: {scene.content} ({len(scene.content)}字符)")
        
        # 使用字幕引擎处理
        subtitle_request = SubtitleRequest(
            text=scene.content,
            duration=scene.duration_seconds,
            language="zh",
            max_chars_per_line=10  # 使用新的限制
        )
        
        subtitle_result = subtitle_engine.process_subtitles(subtitle_request)
        
        if subtitle_result.success:
            print(f"  分割为{len(subtitle_result.segments)}个字幕段:")
            for j, segment in enumerate(subtitle_result.segments, 1):
                pixel_width = 0
                try:
                    from utils.subtitle_utils import SubtitleUtils
                    pixel_width = SubtitleUtils.calculate_pixel_width(segment.text, 48)
                except:
                    pixel_width = len(segment.text) * 48
                
                width_status = "✅" if pixel_width <= 580 else "❌"
                print(f"    {j}: {segment.text} | {len(segment.text)}字符 | {pixel_width}px {width_status}")
        else:
            print(f"  ❌ 处理失败: {subtitle_result.error_message}")
        
        print()

if __name__ == "__main__":
    asyncio.run(test_full_subtitle_optimization())