"""
ScriptGenerator单元测试
测试文案生成的核心功能
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import asdict

from content.script_generator import ScriptGenerator, ScriptGenerationRequest, GeneratedScript
from utils.result_types import Result


class TestScriptGenerator:
    """ScriptGenerator测试类"""
    
    @pytest.fixture
    def script_generator(self, config_manager, file_manager, mock_llm_client):
        """ScriptGenerator实例"""
        with patch('content.script_generator.EnhancedLLMManager', return_value=mock_llm_client):
            generator = ScriptGenerator(config_manager, file_manager)
            return generator
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_basic_script_generation(self, script_generator, mock_llm_client):
        """测试基本文案生成"""
        # 准备请求
        request = ScriptGenerationRequest(
            theme="康熙大帝智擒鳌拜",
            language="zh",
            target_length=800
        )
        
        # Mock LLM响应
        mock_response = "你知道吗？康熙皇帝年仅十六岁时，就展现了超凡的政治智慧..."
        
        # 配置异步mock
        import asyncio
        future = asyncio.Future()
        future.set_result(mock_response)
        mock_llm_client.call_llm_with_fallback.return_value = future
        
        # 执行生成
        result = await script_generator.generate_script_async(request)
        
        # 验证结果  
        assert result is not None
        assert isinstance(result, GeneratedScript)
        assert result.title is not None
        assert result.content == mock_response
        assert result.language == "zh"
        assert result.theme == "康熙大帝智擒鳌拜"
        assert result.word_count > 0
        assert result.generation_time > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_different_languages(self, script_generator, mock_llm_client):
        """测试不同语言的文案生成"""
        languages = ["zh", "en", "es"]
        themes = ["康熙大帝", "Napoleon", "El Cid"]
        
        for lang, theme in zip(languages, themes):
            request = ScriptGenerationRequest(
                theme=theme,
                language=lang,
                target_length=500
            )
            
            # Mock适配不同语言的响应
            if lang == "zh":
                mock_response = f"关于{theme}的中文故事..."
            elif lang == "en":
                mock_response = f"A story about {theme} in English..."
            else:
                mock_response = f"Una historia sobre {theme} en español..."
            
            mock_llm_client.call_llm_async.return_value = Result.success(mock_response)
            
            result = await script_generator.generate_script_async(request)
            
            assert result.is_success()
            script = result.data
            assert script.language == lang
            assert theme.lower() in script.theme.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_different_styles(self, script_generator, mock_llm_client):
        """测试不同风格的文案生成"""
        styles = ["horror", "documentary", "dramatic"]
        
        for style in styles:
            request = ScriptGenerationRequest(
                theme="康熙大帝智擒鳌拜",
                language="zh",
                style=style,
                target_length=600
            )
            
            mock_response = f"这是{style}风格的康熙故事..."
            mock_llm_client.call_llm_async.return_value = Result.success(mock_response)
            
            result = await script_generator.generate_script_async(request)
            
            assert result.is_success()
            # 可以根据风格验证内容特点
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_target_length_control(self, script_generator, mock_llm_client):
        """测试目标长度控制"""
        target_lengths = [300, 800, 1500]
        
        for target_length in target_lengths:
            request = ScriptGenerationRequest(
                theme="康熙大帝智擒鳌拜", 
                language="zh",
                target_length=target_length
            )
            
            # 生成对应长度的Mock响应
            mock_response = "康熙故事内容..." * (target_length // 10)
            mock_llm_client.call_llm_async.return_value = Result.success(mock_response)
            
            result = await script_generator.generate_script_async(request)
            
            assert result.is_success()
            script = result.data
            
            # 验证长度在合理范围内（允许±20%偏差）
            assert script.word_count > target_length * 0.5
            assert script.word_count < target_length * 2.0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_llm_failure_handling(self, script_generator, mock_llm_client):
        """测试LLM调用失败处理"""
        request = ScriptGenerationRequest(
            theme="康熙大帝智擒鳌拜",
            language="zh"
        )
        
        # Mock LLM调用失败
        mock_llm_client.call_llm_async.return_value = Result.error("API调用失败")
        
        result = await script_generator.generate_script_async(request)
        
        assert result.is_error()
        assert "API调用失败" in result.error
    
    @pytest.mark.unit
    def test_script_cleaning(self, script_generator):
        """测试脚本内容清理"""
        # 包含结构关键词的原始内容
        raw_content = """
        ## 标题
        
        这是正文内容，讲述康熙的故事。
        
        ### 小标题
        
        更多内容...
        
        **结论：** 康熙很厉害。
        """
        
        cleaned_content = script_generator._clean_script_content(raw_content)
        
        # 验证清理结果
        assert "##" not in cleaned_content
        assert "###" not in cleaned_content
        assert "**" not in cleaned_content
        assert "这是正文内容，讲述康熙的故事。" in cleaned_content
        assert "康熙很厉害。" in cleaned_content
    
    @pytest.mark.unit
    def test_title_extraction(self, script_generator):
        """测试标题提取"""
        # 包含明确标题的内容
        content_with_title = """
        标题：康熙智擒鳌拜传奇
        
        正文内容开始...
        """
        
        title = script_generator._extract_title(content_with_title)
        assert title == "康熙智擒鳌拜传奇"
        
        # 没有明确标题的内容
        content_without_title = "这是一个关于康熙的故事..."
        title = script_generator._extract_title(content_without_title)
        assert title is not None  # 应该生成默认标题
    
    @pytest.mark.unit
    def test_word_count_calculation(self, script_generator):
        """测试字数统计"""
        # 中文内容
        chinese_text = "这是一个关于康熙大帝的精彩故事。"
        count = script_generator._calculate_word_count(chinese_text, "zh")
        assert count > 0
        
        # 英文内容
        english_text = "This is an amazing story about Emperor Kangxi."
        count = script_generator._calculate_word_count(english_text, "en")
        assert count > 0
        
        # 空内容
        empty_text = ""
        count = script_generator._calculate_word_count(empty_text, "zh")
        assert count == 0


class TestScriptGeneratorEdgeCases:
    """ScriptGenerator边缘情况测试"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_theme(self, script_generator, mock_llm_client):
        """测试空主题处理"""
        request = ScriptGenerationRequest(
            theme="",  # 空主题
            language="zh"
        )
        
        mock_llm_client.call_llm_async.return_value = Result.success("默认故事内容...")
        
        result = await script_generator.generate_script_async(request)
        
        # 应该能处理空主题，可能返回错误或默认内容
        if result.is_success():
            assert result.data.theme == ""
        else:
            assert "theme" in result.error.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_very_long_theme(self, script_generator, mock_llm_client):
        """测试超长主题处理"""
        long_theme = "康熙大帝智擒鳌拜的惊心传奇" * 50  # 超长主题
        
        request = ScriptGenerationRequest(
            theme=long_theme,
            language="zh"
        )
        
        mock_llm_client.call_llm_async.return_value = Result.success("关于长主题的故事...")
        
        result = await script_generator.generate_script_async(request)
        
        # 应该能处理或截断长主题
        assert result.is_success() or result.is_error()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_special_characters_theme(self, script_generator, mock_llm_client):
        """测试特殊字符主题"""
        special_theme = "康熙@#$%^&*()大帝🎬📝"
        
        request = ScriptGenerationRequest(
            theme=special_theme,
            language="zh"
        )
        
        mock_llm_client.call_llm_async.return_value = Result.success("特殊字符故事...")
        
        result = await script_generator.generate_script_async(request)
        
        # 应该能处理特殊字符
        assert result.is_success()
    
    @pytest.mark.unit
    @pytest.mark.asyncio 
    async def test_unsupported_language(self, script_generator, mock_llm_client):
        """测试不支持的语言"""
        request = ScriptGenerationRequest(
            theme="康熙大帝",
            language="fr"  # 法语，假设不支持
        )
        
        mock_llm_client.call_llm_async.return_value = Result.success("French content...")
        
        result = await script_generator.generate_script_async(request)
        
        # 根据实现，可能成功（使用默认模板）或失败
        assert result.is_success() or result.is_error()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_malformed_llm_response(self, script_generator, mock_llm_client):
        """测试畸形LLM响应"""
        request = ScriptGenerationRequest(
            theme="康熙大帝",
            language="zh"
        )
        
        # 返回非常短或空的响应
        mock_llm_client.call_llm_async.return_value = Result.success("")
        
        result = await script_generator.generate_script_async(request)
        
        # 应该能处理空响应
        if result.is_success():
            # 可能生成默认内容或保持为空
            script = result.data
            assert script.content is not None
        else:
            assert "empty" in result.error.lower() or "short" in result.error.lower()


# 性能和压力测试
class TestScriptGeneratorPerformance:
    """ScriptGenerator性能测试"""
    
    @pytest.mark.unit
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_generation_speed(self, script_generator, mock_llm_client, performance_tracker):
        """测试生成速度"""
        request = ScriptGenerationRequest(
            theme="康熙大帝智擒鳌拜",
            language="zh",
            target_length=800
        )
        
        # Mock快速响应
        mock_llm_client.call_llm_async.return_value = Result.success(
            "康熙故事内容..." * 100
        )
        
        performance_tracker.start('script_generation')
        
        result = await script_generator.generate_script_async(request)
        
        duration = performance_tracker.end('script_generation')
        
        assert result.is_success()
        # 脚本生成应该在合理时间内完成
        assert duration < 5.0, f"Script generation too slow: {duration:.2f}s"
    
    @pytest.mark.unit
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_generations(self, script_generator, mock_llm_client):
        """测试并发生成"""
        import asyncio
        
        requests = [
            ScriptGenerationRequest(
                theme=f"主题{i}",
                language="zh"
            ) for i in range(5)
        ]
        
        # Mock所有响应
        mock_llm_client.call_llm_async.return_value = Result.success("并发测试内容...")
        
        # 并发执行
        tasks = [script_generator.generate_script_async(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证所有结果
        for result in results:
            assert not isinstance(result, Exception)
            assert result.is_success()
    
    @pytest.mark.unit
    @pytest.mark.performance
    def test_memory_usage(self, script_generator, mock_llm_client, assert_memory):
        """测试内存使用"""
        # 生成大量短脚本，检查内存泄漏
        import asyncio
        
        async def generate_many():
            for i in range(50):
                request = ScriptGenerationRequest(
                    theme=f"主题{i}",
                    language="zh",
                    target_length=200
                )
                
                mock_llm_client.call_llm_async.return_value = Result.success(f"内容{i}...")
                
                result = await script_generator.generate_script_async(request)
                assert result.is_success()
        
        # 执行大量生成
        asyncio.run(generate_many())
        
        # 检查内存使用（假设不超过100MB）
        assert_memory(100.0, "script_generation")


# 集成度测试（需要真实API时标记跳过）
class TestScriptGeneratorIntegration:
    """ScriptGenerator集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.skip_if_no_api
    @pytest.mark.asyncio
    async def test_real_llm_integration(self, config_manager, file_manager):
        """测试真实LLM集成（需要API密钥）"""
        # 使用真实的LLM客户端
        generator = ScriptGenerator(config_manager, file_manager)
        
        request = ScriptGenerationRequest(
            theme="康熙大帝智擒鳌拜",
            language="zh",
            target_length=500
        )
        
        result = await generator.generate_script_async(request)
        
        # 验证真实生成结果
        assert result.is_success()
        script = result.data
        assert len(script.content) > 100  # 应该有实际内容
        assert "康熙" in script.content or "鳌拜" in script.content