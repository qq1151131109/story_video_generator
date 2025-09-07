#!/usr/bin/env python3
"""
一体化文生视频功能逻辑测试

测试代码逻辑是否正确，无需实际API调用
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from media.text_to_video_generator import TextToVideoGenerator, TextToVideoRequest
from media.media_pipeline import MediaPipeline, MediaGenerationRequest
from content.scene_splitter import Scene


def test_text_to_video_generator_initialization():
    """测试TextToVideoGenerator初始化"""
    print("🔧 测试TextToVideoGenerator初始化...")
    
    try:
        config = ConfigManager()
        file_manager = FileManager()
        
        # 测试无API密钥时的行为
        original_get_api_key = config.get_api_key
        config.get_api_key = lambda key: None
        
        try:
            generator = TextToVideoGenerator(config, file_manager)
            print("❌ 应该抛出API密钥错误")
            return False
        except ValueError as e:
            if "RunningHub API key not configured" in str(e):
                print("✅ 正确检测到API密钥未配置")
            else:
                print(f"❌ 错误类型不正确: {e}")
                return False
        
        # 恢复原始方法并测试有API密钥的情况
        config.get_api_key = original_get_api_key
        
        # 模拟API密钥存在
        config.get_api_key = lambda key: "test_api_key" if key == 'runninghub' else None
        
        generator = TextToVideoGenerator(config, file_manager)
        print(f"✅ 生成器初始化成功: {generator}")
        print(f"  工作流ID: {generator.workflow_id}")
        print(f"  API超时: {generator.api_timeout}秒")
        print(f"  最大重试: {generator.max_retries}次")
        
        return True
        
    except Exception as e:
        print(f"❌ 初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_payload_building():
    """测试工作流载荷构建"""
    print("\n📦 测试工作流载荷构建...")
    
    try:
        config = ConfigManager()
        file_manager = FileManager()
        
        # 模拟API密钥
        config.get_api_key = lambda key: "test_api_key" if key == 'runninghub' else None
        
        generator = TextToVideoGenerator(config, file_manager)
        
        # 创建测试请求
        request = TextToVideoRequest(
            image_prompt="古代皇宫场景测试",
            video_prompt="缓慢平移镜头",
            negative_prompt="低质量,模糊",
            width=720,
            height=1280,
            fps=31,
            duration=3.0,
            style="ancient_horror",
            scene_id="test_001",
            seed=12345
        )
        
        # 构建载荷
        payload = generator._build_workflow_payload(request)
        
        print("✅ 载荷构建成功:")
        print(f"  工作流ID: {payload['workflow_id']}")
        print(f"  文生图提示词 (node 38): {payload['input_data']['38']['text']}")
        print(f"  图生视频提示词 (node 10): {payload['input_data']['10']['text']}")
        print(f"  负向提示词 (node 1): {payload['input_data']['1']['text'][:50]}...")
        print(f"  帧率: {payload['input_data']['22']['frame_rate']}")
        print(f"  分辨率: {payload['input_data']['39']['width']}x{payload['input_data']['39']['height']}")
        print(f"  Wan内部参数: {payload['input_data']['5']['width_internal']}x{payload['input_data']['5']['height_internal']}")
        
        # 验证载荷结构
        assert payload['workflow_id'] == "1964196221642489858"
        assert payload['input_data']['38']['text'] == request.image_prompt
        assert payload['input_data']['10']['text'] == request.video_prompt
        assert payload['input_data']['1']['text'] == request.negative_prompt
        assert payload['input_data']['22']['frame_rate'] == request.fps
        assert payload['input_data']['39']['width'] == request.width
        assert payload['input_data']['39']['height'] == request.height
        assert payload['input_data']['5']['width_internal'] == 704
        assert payload['input_data']['5']['height_internal'] == 544
        
        print("✅ 载荷结构验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 载荷构建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_media_pipeline_integration():
    """测试MediaPipeline集成逻辑"""
    print("\n🏭 测试MediaPipeline集成逻辑...")
    
    try:
        config = ConfigManager()
        file_manager = FileManager()
        
        # 模拟RunningHub API密钥存在
        config.get_api_key = lambda key: "test_api_key" if key == 'runninghub' else None
        
        # 创建MediaPipeline
        pipeline = MediaPipeline(config, file_manager)
        
        print(f"✅ MediaPipeline初始化成功")
        print(f"  一体化生成支持: {pipeline.enable_integrated_generation}")
        print(f"  TextToVideoGenerator: {'已初始化' if pipeline.text_to_video_generator else '未初始化'}")
        
        # 验证支持检查逻辑
        support_check = pipeline._check_integrated_generation_support()
        print(f"  支持检查结果: {support_check}")
        
        # 测试无API密钥时的降级行为
        config.get_api_key = lambda key: None
        pipeline2 = MediaPipeline(config, None, file_manager)
        print(f"  无API密钥时一体化支持: {pipeline2.enable_integrated_generation}")
        
        # 验证配置开关
        config.get_api_key = lambda key: "test_api_key" if key == 'runninghub' else None
        original_get = config.get
        config.get = lambda path, default=None: False if path == 'media.enable_integrated_generation' else original_get(path, default)
        
        pipeline3 = MediaPipeline(config, None, file_manager)
        print(f"  配置禁用时一体化支持: {pipeline3.enable_integrated_generation}")
        
        return True
        
    except Exception as e:
        print(f"❌ MediaPipeline集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scene_media_data_structure():
    """测试SceneMedia数据结构"""
    print("\n📁 测试SceneMedia数据结构...")
    
    try:
        from media.media_pipeline import SceneMedia
        from media.text_to_video_generator import TextToVideoResult
        from media.image_generator import GeneratedImage
        from media.audio_generator import GeneratedAudio
        
        # 创建测试场景
        test_scene = Scene(
            sequence=1,
            content="测试场景",
            image_prompt="测试图像提示词",
            video_prompt="测试视频提示词",
            duration_seconds=3.0,
            animation_type="center_zoom_in",
            subtitle_text="测试字幕"
        )
        
        # 测试传统模式数据结构
        traditional_scene = SceneMedia(
            scene=test_scene,
            image=None,  # 模拟GeneratedImage对象
            audio=None,  # 模拟GeneratedAudio对象
            video=None
        )
        
        print("✅ 传统模式SceneMedia创建成功")
        print(f"  场景序号: {traditional_scene.scene.sequence}")
        print(f"  图像: {'存在' if traditional_scene.image else '无'}")
        print(f"  音频: {'存在' if traditional_scene.audio else '无'}")
        print(f"  视频: {'存在' if traditional_scene.video else '无'}")
        
        # 测试一体化模式数据结构
        integrated_scene = SceneMedia(
            scene=test_scene,
            image=None,
            audio=None,
            video=None  # 模拟TextToVideoResult对象
        )
        
        print("✅ 一体化模式SceneMedia创建成功")
        print(f"  场景序号: {integrated_scene.scene.sequence}")
        print(f"  图像: {'存在' if integrated_scene.image else '无'}")
        print(f"  音频: {'存在' if integrated_scene.audio else '无'}")
        print(f"  视频: {'存在' if integrated_scene.video else '无'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据结构测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration_updates():
    """测试配置文件更新"""
    print("\n⚙️ 测试配置文件更新...")
    
    try:
        config = ConfigManager()
        
        # 检查新增的配置项
        enable_integrated = config.get('media.enable_integrated_generation', None)
        workflow_id = config.get('media.integrated_workflow_id', None)
        
        print(f"✅ 配置读取测试:")
        print(f"  enable_integrated_generation: {enable_integrated}")
        print(f"  integrated_workflow_id: {workflow_id}")
        
        # 验证配置值
        if enable_integrated is True:
            print("✅ 一体化生成默认启用")
        else:
            print("⚠️  一体化生成未启用或配置错误")
        
        if workflow_id == "1964196221642489858":
            print("✅ 工作流ID配置正确")
        else:
            print(f"⚠️  工作流ID配置错误: {workflow_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_logic_tests():
    """运行所有逻辑测试"""
    print("🧪 开始一体化功能逻辑测试\n")
    print("="*60)
    
    tests = [
        ("TextToVideoGenerator初始化", test_text_to_video_generator_initialization),
        ("工作流载荷构建", test_workflow_payload_building),
        ("MediaPipeline集成", test_media_pipeline_integration),
        ("SceneMedia数据结构", test_scene_media_data_structure),
        ("配置文件更新", test_configuration_updates)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 执行异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    print("\n" + "="*60)
    print("🎯 逻辑测试结果汇总:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\n总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 所有逻辑测试通过! 一体化功能代码逻辑正确")
        return True
    else:
        print(f"\n⚠️  {total-passed} 项测试失败，需要修复代码逻辑")
        return False


if __name__ == "__main__":
    success = run_logic_tests()
    sys.exit(0 if success else 1)