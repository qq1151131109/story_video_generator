#!/usr/bin/env python3
"""
图生视频功能测试脚本
测试新增的图生视频功能和自适应分辨率系统
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.load_env import load_env_file
from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from media.image_generator import ImageGenerator, ImageGenerationRequest
from media.image_to_video_generator import ImageToVideoGenerator, ImageToVideoRequest
from video.video_composer import VideoComposer
from content.scene_splitter import Scene

async def test_adaptive_resolution():
    """测试自适应分辨率功能"""
    print("🔍 测试自适应分辨率系统...")
    
    # 加载环境和配置
    load_env_file()
    config = ConfigManager()
    file_manager = FileManager()
    
    # 创建图像生成器
    image_generator = ImageGenerator(config, None, file_manager)
    
    # 测试不同策略的分辨率
    strategies = ['traditional', 'image_to_video', 'hybrid']
    
    for strategy in strategies:
        width, height = image_generator.get_adaptive_resolution(strategy)
        print(f"  {strategy}: {width}x{height}")
    
    print("✅ 自适应分辨率测试完成\n")

async def test_image_to_video_generation():
    """测试图生视频生成功能"""
    print("🎬 测试图生视频生成...")
    
    # 加载环境和配置
    load_env_file()
    config = ConfigManager()
    file_manager = FileManager()
    
    # 检查API密钥
    api_key = config.get_api_key('runninghub')
    if not api_key:
        print("❌ RunningHub API密钥未配置，跳过图生视频测试")
        return
    
    # 创建图生视频生成器
    i2v_generator = ImageToVideoGenerator(config, file_manager)
    
    # 检查是否有测试图片
    test_image_dir = Path("output/images")
    if not test_image_dir.exists():
        print("❌ 没有找到测试图片目录，跳过图生视频测试")
        return
    
    # 查找最新的图片文件
    image_files = list(test_image_dir.glob("*.png"))
    if not image_files:
        print("❌ 没有找到测试图片，请先生成一些图片")
        return
    
    # 使用最新的图片
    test_image = max(image_files, key=lambda x: x.stat().st_mtime)
    print(f"  使用测试图片: {test_image.name}")
    
    # 创建测试请求
    test_request = ImageToVideoRequest(
        image_path=str(test_image),
        desc_prompt="古代皇帝坐在龙椅上，威严庄重，古代宫殿背景，昏暗灯光",
        duration_seconds=3.0,
        width=720,
        height=1280
    )
    
    try:
        # 生成图生视频
        print("  上传图片并生成视频...")
        result = await i2v_generator.generate_video_async(test_request)
        
        print(f"✅ 图生视频生成成功:")
        print(f"  视频路径: {result.video_path}")
        print(f"  帧数: {result.frames}")
        print(f"  文件大小: {result.file_size/1024/1024:.1f}MB")
        print(f"  生成时间: {result.generation_time:.1f}s")
        
    except Exception as e:
        print(f"❌ 图生视频生成失败: {e}")
    
    print()

async def test_dual_mode_video_composer():
    """测试双模式视频合成器"""
    print("🎭 测试双模式视频合成...")
    
    # 加载环境和配置
    load_env_file()
    config = ConfigManager()
    file_manager = FileManager()
    
    # 创建测试场景
    test_scenes = [
        Scene(
            sequence=1,
            content="古代皇帝登基大典，百官朝拜",
            image_prompt="Ancient emperor's coronation ceremony, officials bowing, majestic palace hall, ancient horror style, traditional clothing, high contrast, low saturation colors",
            duration_seconds=3.0,
            animation_type="智能选择",
            subtitle_text="古代皇帝登基大典，百官朝拜"
        ),
        Scene(
            sequence=2, 
            content="大军出征，铁骑如云",
            image_prompt="Massive ancient army marching, cavalry like clouds, battlefield scene, ancient horror style, dramatic lighting, high contrast",
            duration_seconds=3.0,
            animation_type="智能选择",
            subtitle_text="大军出征，铁骑如云"
        )
    ]
    
    # 创建视频合成器
    video_composer = VideoComposer(config, file_manager)
    
    # 直接测试场景选择逻辑
    for i, scene in enumerate(test_scenes):
        # 测试混合模式下的智能选择
        use_i2v = video_composer._should_use_i2v_for_scene(scene, i)
        print(f"  场景{i+1}: {'图生视频' if use_i2v else '传统动画'}")
        print(f"    内容: {scene.content}")
        print(f"    原因: {'包含人物表情/动作' if use_i2v else '场景/风景内容'}")
    
    print("✅ 双模式测试完成\n")

async def test_scene_content_analysis():
    """测试场景内容智能分析"""
    print("🧠 测试场景内容智能分析...")
    
    load_env_file()
    config = ConfigManager()
    file_manager = FileManager()
    
    i2v_generator = ImageToVideoGenerator(config, file_manager)
    
    # 测试场景内容
    test_contents = [
        "古代皇帝威严地坐在龙椅上",  # 应该选择图生视频（人物特写）
        "大军在广阔的平原上行军",      # 应该选择传统动画（大场景）
        "将军的表情严肃而坚定",        # 应该选择图生视频（表情特写）
        "夕阳西下，古城墙剪影",        # 应该选择传统动画（风景）
        "The emperor's facial expression shows determination",  # 英文表情描述
    ]
    
    for content in test_contents:
        should_use = i2v_generator.should_use_i2v(content)
        print(f"  '{content[:30]}...': {'图生视频' if should_use else '传统动画'}")
    
    print("✅ 场景内容分析测试完成\n")

def print_configuration_summary():
    """打印配置摘要"""
    print("⚙️ 图生视频配置摘要:")
    
    load_env_file()
    config = ConfigManager()
    
    # 视频配置
    video_config = config.get('video', {})
    animation_strategy = video_config.get('animation_strategy', 'traditional')
    i2v_config = video_config.get('image_to_video', {})
    
    print(f"  动画策略: {animation_strategy}")
    print(f"  图生视频启用: {i2v_config.get('enabled', False)}")
    print(f"  工作流ID: {i2v_config.get('workflow_id', 'N/A')}")
    print(f"  FPS: {i2v_config.get('fps', 16)}")
    print(f"  降级到传统动画: {i2v_config.get('fallback_to_traditional', True)}")
    
    # 图像配置
    image_config = config.get('media.image', {})
    resolution_mode = image_config.get('resolution_mode', 'fixed')
    traditional_res = image_config.get('traditional_resolution', 'N/A')
    i2v_res = image_config.get('i2v_resolution', 'N/A')
    
    print(f"  分辨率模式: {resolution_mode}")
    print(f"  传统动画分辨率: {traditional_res}")
    print(f"  图生视频分辨率: {i2v_res}")
    
    # API密钥状态
    api_key = config.get_api_key('runninghub')
    print(f"  RunningHub API: {'已配置' if api_key else '未配置'}")
    
    print()

async def main():
    """主测试函数"""
    print("🚀 图生视频功能测试开始\n")
    
    # 设置日志
    setup_logging()
    
    try:
        # 打印配置摘要
        print_configuration_summary()
        
        # 运行各项测试
        await test_adaptive_resolution()
        await test_scene_content_analysis()
        await test_dual_mode_video_composer()
        await test_image_to_video_generation()
        
        print("🎉 所有测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())