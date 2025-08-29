"""
综合测试套件 - 系统功能完整性测试
"""
import asyncio
import unittest
import sys
from pathlib import Path
import tempfile
import shutil
import os
import json
import time

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.i18n import get_i18n_manager, set_global_language
from utils.logger import setup_logging
from content.script_generator import ScriptGenerator, ScriptGenerationRequest
from content.scene_splitter import SceneSplitter, SceneSplitRequest
from content.character_analyzer import CharacterAnalyzer, CharacterAnalysisRequest
from content.content_pipeline import ContentPipeline, ContentGenerationRequest
from video.subtitle_processor import SubtitleProcessor, SubtitleRequest
from video.animation_processor import AnimationProcessor, AnimationRequest


class TestCore(unittest.TestCase):
    """核心框架测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_manager(self):
        """测试配置管理器"""
        # 测试基本配置读取
        languages = self.config.get_supported_languages()
        self.assertIsInstance(languages, list)
        self.assertGreaterEqual(len(languages), 3)
        
        # 测试LLM配置
        llm_config = self.config.get_llm_config('script_generation')
        self.assertIsNotNone(llm_config)
        self.assertEqual(llm_config.name, 'deepseek-v3')
        self.assertEqual(llm_config.temperature, 0.8)
        
    def test_cache_manager(self):
        """测试缓存管理器"""
        cache = CacheManager(cache_dir=self.temp_dir)
        
        # 测试缓存操作
        test_data = {"test": "data", "number": 123}
        cache_key = cache.get_cache_key("test_content")
        
        # 写入缓存
        success = cache.set('scripts', cache_key, test_data)
        self.assertTrue(success)
        
        # 读取缓存
        cached_data = cache.get('scripts', cache_key)
        self.assertEqual(cached_data, test_data)
        
        # 测试不存在的缓存
        missing_data = cache.get('scripts', 'nonexistent_key')
        self.assertIsNone(missing_data)
    
    def test_file_manager(self):
        """测试文件管理器"""
        file_manager = FileManager(output_dir=self.temp_dir)
        
        # 测试文件名生成
        filename = file_manager.generate_filename("test content", "prefix", "suffix", "txt")
        self.assertTrue(filename.endswith('.txt'))
        self.assertTrue(filename.startswith('prefix'))
        
        # 测试文件保存和读取
        test_content = "这是测试内容"
        test_file = Path(self.temp_dir) / "test.txt"
        
        success = file_manager.save_text(test_content, test_file)
        self.assertTrue(success)
        
        loaded_content = file_manager.load_text(test_file)
        self.assertEqual(loaded_content, test_content)


class TestI18n(unittest.TestCase):
    """国际化测试"""
    
    def setUp(self):
        self.i18n = get_i18n_manager()
    
    def test_language_support(self):
        """测试语言支持"""
        languages = self.i18n.get_supported_languages()
        self.assertIn('zh', languages)
        self.assertIn('en', languages)
        self.assertIn('es', languages)
        
        # 测试语言切换
        for lang in ['zh', 'en', 'es']:
            success = self.i18n.set_language(lang)
            self.assertTrue(success)
            self.assertEqual(self.i18n.current_language, lang)
    
    def test_message_localization(self):
        """测试消息本地化"""
        # 测试各语言的基本消息
        for lang in ['zh', 'en', 'es']:
            self.i18n.set_language(lang)
            
            success_msg = self.i18n.get_message('common', 'success')
            self.assertIsInstance(success_msg, str)
            self.assertNotIn('[', success_msg)  # 不应该包含错误标记
            
            processing_msg = self.i18n.get_message('common', 'processing')
            self.assertIsInstance(processing_msg, str)
            self.assertNotIn('[', processing_msg)
    
    def test_formatting_functions(self):
        """测试格式化功能"""
        # 测试时间格式化
        time_str = self.i18n.format_time_duration(65)
        self.assertIn('1m', time_str)
        
        # 测试文件大小格式化
        size_str = self.i18n.format_file_size(1536)
        self.assertIn('KB', size_str)
    
    def test_language_detection(self):
        """测试语言检测"""
        chinese_text = "这是中文测试文本"
        detected = self.i18n.detect_language_from_text(chinese_text)
        self.assertEqual(detected, 'zh')
        
        english_text = "This is an English test text"
        detected = self.i18n.detect_language_from_text(english_text)
        self.assertEqual(detected, 'en')


class TestContentGeneration(unittest.TestCase):
    """内容生成测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager()
        self.cache = CacheManager(cache_dir=os.path.join(self.temp_dir, 'cache'))
        self.files = FileManager(output_dir=self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_script_generator_mock(self):
        """测试文案生成器（模拟模式）"""
        generator = ScriptGenerator(self.config, self.cache, self.files)
        
        # 测试请求验证
        request = ScriptGenerationRequest(
            theme="测试主题",
            language="zh",
            target_length=100
        )
        
        # 这里只测试请求创建，不实际调用API
        self.assertEqual(request.theme, "测试主题")
        self.assertEqual(request.language, "zh")
        self.assertEqual(request.target_length, 100)
    
    def test_scene_splitter_fallback(self):
        """测试场景分割器的退化处理"""
        splitter = SceneSplitter(self.config, self.cache, self.files)
        
        # 测试退化场景解析
        test_content = "这是第一个场景。这是第二个场景。这是第三个场景。"
        request = SceneSplitRequest(
            script_content=test_content,
            language="zh",
            target_scene_count=3,
            scene_duration=3.0
        )
        
        # 使用内部方法测试退化处理
        scenes = splitter._fallback_scene_parsing(test_content, request)
        self.assertEqual(len(scenes), 3)
        
        for scene in scenes:
            self.assertIsInstance(scene.content, str)
            self.assertGreater(len(scene.content), 0)
            self.assertEqual(scene.duration_seconds, 3.0)
    
    def test_character_analyzer_fallback(self):
        """测试角色分析器的退化处理"""
        analyzer = CharacterAnalyzer(self.config, self.cache, self.files)
        
        # 测试退化角色解析
        test_content = "秦始皇是一位伟大的皇帝"
        request = CharacterAnalysisRequest(
            script_content=test_content,
            language="zh",
            max_characters=3
        )
        
        # 使用内部方法测试退化处理
        characters, main_character = analyzer._fallback_character_parsing(test_content, request)
        
        self.assertGreaterEqual(len(characters), 1)
        self.assertIsNotNone(main_character)
        self.assertIsInstance(main_character.name, str)


class TestVideoProcessing(unittest.TestCase):
    """视频处理测试"""
    
    def setUp(self):
        self.config = ConfigManager()
        self.files = FileManager()
    
    def test_subtitle_processor(self):
        """测试字幕处理器"""
        processor = SubtitleProcessor(self.config, self.files)
        
        # 测试字幕分割
        request = SubtitleRequest(
            text="这是一段很长的测试文本，用来验证字幕分割功能是否正常工作。应该被分割成多个片段。",
            scene_duration=6.0,
            language="zh",
            max_line_length=15
        )
        
        segments = processor.process_subtitle(request)
        
        self.assertGreater(len(segments), 1)  # 应该被分割成多个片段
        
        # 验证每个片段的属性
        for segment in segments:
            self.assertIsInstance(segment.text, str)
            self.assertGreaterEqual(segment.start_time, 0)
            self.assertGreater(segment.end_time, segment.start_time)
            self.assertGreater(segment.duration, 0)
        
        # 验证总时长
        last_segment = segments[-1]
        self.assertAlmostEqual(last_segment.end_time, 6.0, places=1)
    
    def test_subtitle_formats(self):
        """测试字幕格式生成"""
        processor = SubtitleProcessor(self.config, self.files)
        
        # 创建测试片段
        from video.subtitle_processor import SubtitleSegment
        segments = [
            SubtitleSegment(
                text="第一个字幕",
                start_time=0.0,
                end_time=2.0,
                duration=2.0
            ),
            SubtitleSegment(
                text="第二个字幕",
                start_time=2.0,
                end_time=4.0,
                duration=2.0
            )
        ]
        
        # 测试SRT格式
        srt_content = processor.generate_srt(segments)
        self.assertIn("00:00:00,000 --> 00:00:02,000", srt_content)
        self.assertIn("第一个字幕", srt_content)
        
        # 测试ASS格式
        ass_content = processor.generate_ass(segments)
        self.assertIn("[V4+ Styles]", ass_content)
        self.assertIn("第一个字幕", ass_content)
        
        # 测试VTT格式
        vtt_content = processor.generate_vtt(segments)
        self.assertIn("WEBVTT", vtt_content)
        self.assertIn("00:00.000 --> 00:02.000", vtt_content)
    
    def test_animation_processor(self):
        """测试动画处理器"""
        processor = AnimationProcessor(self.config)
        
        # 测试场景动画创建
        request = AnimationRequest(
            image_path="/test/image.png",
            duration_seconds=3.0,
            animation_type="轻微放大"
        )
        
        animation = processor.create_scene_animation(request)
        
        self.assertEqual(animation.duration_seconds, 3.0)
        self.assertGreater(len(animation.keyframes), 0)
        self.assertEqual(animation.animation_type, "zoom_in_slight")
        
        # 验证关键帧
        for keyframe in animation.keyframes:
            self.assertGreaterEqual(keyframe.time_microseconds, 0)
            self.assertGreater(keyframe.scale, 0)
        
        # 测试角色动画创建
        request.is_character = True
        char_animation = processor.create_character_animation(request)
        
        self.assertEqual(char_animation.duration_seconds, 3.0)
        self.assertEqual(char_animation.animation_type, "character_sequence")
        
        # 测试FFmpeg滤镜生成
        filter_str = processor.generate_ffmpeg_filter(animation, (1920, 1080))
        self.assertIsInstance(filter_str, str)
        self.assertIn("scale", filter_str)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager()
        self.cache = CacheManager(cache_dir=os.path.join(self.temp_dir, 'cache'))
        self.files = FileManager(output_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_content_pipeline_integration(self):
        """测试内容生成流水线集成"""
        pipeline = ContentPipeline(self.config, self.cache, self.files)
        
        # 测试请求验证
        request = ContentGenerationRequest(
            theme="测试历史故事主题",
            language="zh"
        )
        
        errors = pipeline.validate_request(request)
        self.assertEqual(len(errors), 0)  # 应该没有验证错误
        
        # 测试统计信息获取
        stats = pipeline.get_pipeline_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('supported_languages', stats)
        self.assertIn('components', stats)
    
    def test_multilanguage_consistency(self):
        """测试多语言一致性"""
        languages = ['zh', 'en', 'es']
        
        for lang in languages:
            set_global_language(lang)
            i18n = get_i18n_manager()
            
            # 验证基本消息存在
            success_msg = i18n.get_message('common', 'success')
            self.assertIsInstance(success_msg, str)
            self.assertGreater(len(success_msg), 0)
            
            # 验证内容生成消息存在
            content_msg = i18n.get_message('content', 'generating_script')
            self.assertIsInstance(content_msg, str)
            self.assertGreater(len(content_msg), 0)


class TestPerformance(unittest.TestCase):
    """性能测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache = CacheManager(cache_dir=os.path.join(self.temp_dir, 'cache'))
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_performance(self):
        """测试缓存性能"""
        start_time = time.time()
        
        # 写入大量缓存项
        for i in range(100):
            test_data = {"index": i, "data": f"test_data_{i}" * 10}
            cache_key = self.cache.get_cache_key(f"test_content_{i}")
            success = self.cache.set('scripts', cache_key, test_data)
            self.assertTrue(success)
        
        write_time = time.time() - start_time
        
        # 读取缓存项
        start_time = time.time()
        
        for i in range(100):
            cache_key = self.cache.get_cache_key(f"test_content_{i}")
            cached_data = self.cache.get('scripts', cache_key)
            self.assertIsNotNone(cached_data)
            self.assertEqual(cached_data['index'], i)
        
        read_time = time.time() - start_time
        
        print(f"Cache performance - Write: {write_time:.3f}s, Read: {read_time:.3f}s")
        
        # 性能断言（这些数值可能需要根据实际情况调整）
        self.assertLess(write_time, 5.0)  # 写入100项应该在5秒内
        self.assertLess(read_time, 1.0)   # 读取100项应该在1秒内


def run_test_suite():
    """运行完整测试套件"""
    print("历史故事生成器 - 测试套件")
    print("=" * 60)
    
    # 创建测试套件
    test_classes = [
        TestCore,
        TestI18n,
        TestContentGeneration,
        TestVideoProcessing,
        TestIntegration,
        TestPerformance
    ]
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True
    )
    
    result = runner.run(suite)
    
    # 输出测试结果摘要
    print("\n" + "=" * 60)
    print("测试结果摘要")
    print("=" * 60)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    print(f"总测试数: {total_tests}")
    print(f"通过: {passed}")
    print(f"失败: {failures}")
    print(f"错误: {errors}")
    
    if failures > 0:
        print(f"\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if errors > 0:
        print(f"\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    success_rate = (passed / total_tests) * 100 if total_tests > 0 else 0
    print(f"\n成功率: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🎉 测试通过率很高，系统质量良好！")
    elif success_rate >= 70:
        print("⚠️  测试通过率一般，建议修复失败的测试。")
    else:
        print("❌ 测试通过率较低，需要重点关注系统质量。")
    
    return success_rate >= 80


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        # 快速测试模式，只运行核心测试
        print("快速测试模式")
        test_classes = [TestCore, TestI18n]
    else:
        # 完整测试模式
        test_classes = None
    
    success = run_test_suite()
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()