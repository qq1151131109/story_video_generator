#!/usr/bin/env python3
"""
一体化文生视频功能测试脚本

测试新的TextToVideoGenerator以及集成到MediaPipeline的功能
验证新工作流ID 1964196221642489858 的正确性
"""

import asyncio
import sys
import time
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from media.text_to_video_generator import TextToVideoGenerator, TextToVideoRequest
from media.media_pipeline import MediaPipeline, MediaGenerationRequest
from content.scene_splitter import Scene


async def test_text_to_video_generator():
    """测试TextToVideoGenerator单独功能"""
    print("🎬 测试TextToVideoGenerator...")
    
    try:
        # 初始化组件
        config = ConfigManager()
        file_manager = FileManager()
        
        # 检查API密钥
        api_key = config.get_api_key('runninghub')
        if not api_key:
            print("❌ RunningHub API密钥未配置，请设置RUNNINGHUB_API_KEY环境变量")
            return False
        
        print(f"✅ RunningHub API密钥已配置: {api_key[:20]}...")
        
        # 创建生成器
        generator = TextToVideoGenerator(config, None, file_manager)
        print(f"✅ 生成器初始化成功: {generator}")
        
        # 创建测试请求
        request = TextToVideoRequest(
            image_prompt="古代中国皇宫内，金碧辉煌的大殿中，穿着龙袍的皇帝端坐在龙椅上，威严肃穆",
            video_prompt="庄严肃穆的皇帝，缓慢的镜头推进",
            negative_prompt="blurry, low quality, distorted, bad anatomy",
            width=720,
            height=1280,
            fps=31,
            duration=3.0,
            style="ancient_horror",
            scene_id="test_integrated_001"
        )
        
        print(f"🚀 开始生成文生视频...")
        print(f"  文生图提示词: {request.image_prompt}")
        print(f"  图生视频提示词: {request.video_prompt}")
        print(f"  分辨率: {request.width}x{request.height}@{request.fps}fps")
        print(f"  时长: {request.duration}秒")
        
        start_time = time.time()
        
        # 执行生成
        result = await generator.generate_video_async(request)
        
        elapsed = time.time() - start_time
        
        print(f"✅ 文生视频生成成功!")
        print(f"  文件路径: {result.video_path}")
        print(f"  文件大小: {result.file_size/1024:.1f}KB")
        print(f"  实际分辨率: {result.width}x{result.height}")
        print(f"  实际帧率: {result.fps}fps")
        print(f"  实际时长: {result.duration:.1f}秒")
        print(f"  任务ID: {result.task_id}")
        print(f"  生成耗时: {elapsed:.2f}秒")
        
        # 验证文件是否存在
        video_file = Path(result.video_path)
        if video_file.exists():
            print(f"✅ 视频文件验证通过: {video_file}")
            return True
        else:
            print(f"❌ 视频文件不存在: {video_file}")
            return False
    
    except Exception as e:
        print(f"❌ TextToVideoGenerator测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integrated_media_pipeline():
    """测试集成到MediaPipeline的功能"""
    print("\n🏭 测试集成MediaPipeline...")
    
    try:
        # 初始化组件
        config = ConfigManager()
        file_manager = FileManager()
        
        # 创建媒体流水线
        pipeline = MediaPipeline(config, None, file_manager)
        print(f"✅ MediaPipeline初始化成功: {pipeline}")
        print(f"  一体化生成支持: {pipeline.enable_integrated_generation}")
        
        # 创建测试场景
        test_scenes = [
            Scene(
                sequence=1,
                content="皇帝登基大典，文武百官齐聚，场面庄重壮观",
                image_prompt="古代中国皇宫大殿，皇帝登基仪式，文武百官跪拜，金碧辉煌，庄严肃穆",
                video_prompt="slow camera push, majestic presence, solemn atmosphere",
                duration_seconds=3.0,
                animation_type="center_zoom_in",
                subtitle_text="皇帝登基大典，文武百官齐聚，场面庄重壮观"
            ),
            Scene(
                sequence=2,
                content="深夜宫廷，红烛摇曳，皇帝独自沉思朝政",
                image_prompt="深夜古代宫廷书房，红烛烛光摇曳，皇帝穿龙袍独坐思考，古典氛围",
                video_prompt="gentle zoom in, flickering candlelight, contemplative mood",
                duration_seconds=3.0,
                animation_type="move_left",
                subtitle_text="深夜宫廷，红烛摇曳，皇帝独自沉思朝政"
            )
        ]
        
        # 创建媒体生成请求
        media_request = MediaGenerationRequest(
            scenes=test_scenes,
            characters=[],  # 暂不测试角色
            main_character=None,
            language="zh",
            script_title="测试一体化文生视频",
            full_script="测试脚本内容"
        )
        
        print(f"🚀 开始一体化媒体生成...")
        print(f"  场景数量: {len(test_scenes)}")
        print(f"  生成模式: {'一体化文生视频' if pipeline.enable_integrated_generation else '传统分离模式'}")
        
        start_time = time.time()
        
        # 执行媒体生成
        result = await pipeline.generate_media_async(media_request)
        
        elapsed = time.time() - start_time
        
        print(f"✅ 媒体生成完成!")
        print(f"  总耗时: {elapsed:.2f}秒")
        print(f"  场景媒体数量: {len(result.scene_media)}")
        
        # 验证结果
        success_count = 0
        for i, scene_media in enumerate(result.scene_media):
            print(f"\n  场景 {i+1}:")
            if scene_media.video:  # 一体化模式
                print(f"    视频文件: {scene_media.video.video_path}")
                print(f"    视频大小: {scene_media.video.file_size/1024:.1f}KB")
                print(f"    分辨率: {scene_media.video.width}x{scene_media.video.height}")
                print(f"    时长: {scene_media.video.duration:.1f}秒")
                success_count += 1
            elif scene_media.image:  # 传统模式
                print(f"    图像文件: {scene_media.image.file_path}")
                print(f"    图像大小: {scene_media.image.file_size/1024:.1f}KB")
                success_count += 1
            else:
                print(f"    ❌ 无媒体内容")
        
        print(f"\n✅ 成功生成 {success_count}/{len(test_scenes)} 个场景媒体")
        return success_count == len(test_scenes)
    
    except Exception as e:
        print(f"❌ MediaPipeline集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_batch_generation():
    """测试批量生成功能"""
    print("\n🔄 测试批量生成...")
    
    try:
        config = ConfigManager()
        file_manager = FileManager()
        generator = TextToVideoGenerator(config, None, file_manager)
        
        # 创建多个测试请求
        requests = [
            TextToVideoRequest(
                image_prompt=f"古代战争场景{i+1}：士兵们冲锋陷阵，刀光剑影",
                video_prompt=f"激烈的战斗动作，快速镜头切换",
                width=720,
                height=1280,
                fps=31,
                duration=3.0,
                scene_id=f"batch_test_{i+1}"
            )
            for i in range(3)
        ]
        
        print(f"🚀 开始批量生成 {len(requests)} 个视频...")
        
        start_time = time.time()
        
        # 执行批量生成
        results = await generator.batch_generate_videos(requests, max_concurrent=2)
        
        elapsed = time.time() - start_time
        
        print(f"✅ 批量生成完成!")
        print(f"  成功数量: {len(results)}/{len(requests)}")
        print(f"  总耗时: {elapsed:.2f}秒")
        print(f"  平均耗时: {elapsed/len(results):.2f}秒/视频")
        
        # 验证结果
        for i, result in enumerate(results):
            print(f"  视频 {i+1}: {Path(result.video_path).name} ({result.file_size/1024:.1f}KB)")
        
        return len(results) == len(requests)
    
    except Exception as e:
        print(f"❌ 批量生成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """运行所有测试"""
    print("🧪 开始一体化文生视频功能测试\n")
    print("="*60)
    
    test_results = []
    
    # 测试1: TextToVideoGenerator单独功能
    result1 = await test_text_to_video_generator()
    test_results.append(("TextToVideoGenerator单独测试", result1))
    
    # 测试2: MediaPipeline集成功能
    result2 = await test_integrated_media_pipeline()
    test_results.append(("MediaPipeline集成测试", result2))
    
    # 测试3: 批量生成功能
    result3 = await test_batch_generation()
    test_results.append(("批量生成测试", result3))
    
    # 汇总结果
    print("\n" + "="*60)
    print("🎯 测试结果汇总:")
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(test_results)
    print(f"\n总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过! 一体化文生视频功能正常工作")
        return True
    else:
        print(f"\n⚠️  {total-passed} 项测试失败，请检查配置和API连接")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一体化文生视频功能测试")
    parser.add_argument("--single", action="store_true", help="只测试单个生成器")
    parser.add_argument("--pipeline", action="store_true", help="只测试媒体流水线")
    parser.add_argument("--batch", action="store_true", help="只测试批量生成")
    
    args = parser.parse_args()
    
    async def main():
        if args.single:
            success = await test_text_to_video_generator()
        elif args.pipeline:
            success = await test_integrated_media_pipeline()
        elif args.batch:
            success = await test_batch_generation()
        else:
            success = await run_all_tests()
        
        sys.exit(0 if success else 1)
    
    asyncio.run(main())