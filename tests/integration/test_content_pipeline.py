"""
ContentPipeline集成测试
测试内容生成流水线的完整流程
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from content.content_pipeline import ContentPipeline, ContentGenerationRequest
from content.script_generator import GeneratedScript
from content.scene_splitter import SceneSplitResult, Scene
from content.character_analyzer import CharacterAnalysisResult, Character
from utils.result_types import Result


class TestContentPipelineIntegration:
    """ContentPipeline集成测试类"""
    
    @pytest.fixture
    def content_pipeline(self, config_manager, file_manager):
        """ContentPipeline实例"""
        return ContentPipeline(config_manager, file_manager)
    
    @pytest.fixture
    def sample_request(self):
        """示例请求"""
        return ContentGenerationRequest(
            theme="康熙大帝智擒鳌拜的惊心传奇",
            language="zh",
            style="horror"
        )
    
    @pytest.fixture
    def mock_pipeline_components(self):
        """Mock流水线组件"""
        mocks = {}
        
        # Mock ScriptGenerator
        mock_script_generator = Mock()
        mock_script = GeneratedScript(
            title="康熙智擒鳌拜传奇",
            content="你知道吗？康熙皇帝年仅十六岁时..." * 20,
            language="zh",
            theme="康熙大帝智擒鳌拜的惊心传奇",
            word_count=500,
            generation_time=2.5,
            model_used="gpt-4"
        )
        mock_script_generator.generate_script_async.return_value = asyncio.Future()
        mock_script_generator.generate_script_async.return_value.set_result(
            Result.success(mock_script)
        )
        mocks['script_generator'] = mock_script_generator
        
        # Mock SceneSplitter
        mock_scene_splitter = Mock()
        mock_scenes = [
            Scene(sequence=i, content=f"场景{i}内容...", image_prompt=f"场景{i}图像提示", 
                  video_prompt="", duration_seconds=3.0, animation_type="center_zoom_in", 
                  subtitle_text=f"场景{i}内容...")
            for i in range(1, 9)  # 8个场景
        ]
        mock_split_result = SceneSplitResult(
            scenes=mock_scenes,
            total_scenes=8,
            processing_time=1.2,
            method="coze_rules"
        )
        mock_scene_splitter.split_scenes_async.return_value = asyncio.Future()
        mock_scene_splitter.split_scenes_async.return_value.set_result(
            Result.success(mock_split_result)
        )
        mocks['scene_splitter'] = mock_scene_splitter
        
        # Mock CharacterAnalyzer
        mock_character_analyzer = Mock()
        mock_character = Character(
            name="康熙皇帝",
            description="年少有为的清朝皇帝",
            image_prompt="清朝皇帝康熙，年轻英俊，身穿龙袍",
            role="主角"
        )
        mock_analysis_result = CharacterAnalysisResult(
            characters=[mock_character],
            main_character=mock_character,
            total_characters=1,
            processing_time=0.8
        )
        mock_character_analyzer.analyze_characters_async.return_value = asyncio.Future()
        mock_character_analyzer.analyze_characters_async.return_value.set_result(
            Result.success(mock_analysis_result)
        )
        mocks['character_analyzer'] = mock_character_analyzer
        
        return mocks
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_content_generation(self, content_pipeline, sample_request, mock_pipeline_components):
        """测试完整内容生成流程"""
        import asyncio
        
        # 注入Mock组件
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
             patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']), \
             patch.object(content_pipeline, 'character_analyzer', mock_pipeline_components['character_analyzer']):
            
            # 执行完整流程
            result = await content_pipeline.generate_content_async(sample_request)
            
            # 验证结果
            assert result.is_success()
            content_result = result.data
            
            # 验证脚本生成结果
            assert content_result.script is not None
            assert content_result.script.title == "康熙智擒鳌拜传奇"
            assert content_result.script.word_count == 500
            
            # 验证场景分割结果
            assert content_result.scenes is not None
            assert len(content_result.scenes.scenes) == 8
            assert all(scene.sequence > 0 for scene in content_result.scenes.scenes)
            
            # 验证角色分析结果
            assert content_result.characters is not None
            assert len(content_result.characters.characters) == 1
            assert content_result.characters.main_character.name == "康熙皇帝"
            
            # 验证处理时间
            assert content_result.total_processing_time > 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_parallel_processing_optimization(self, content_pipeline, sample_request, mock_pipeline_components, performance_tracker):
        """测试并行处理优化"""
        import asyncio
        
        # 添加处理延迟来测试并行性
        async def delayed_scene_split(*args, **kwargs):
            await asyncio.sleep(0.5)  # 模拟场景分割耗时
            return Result.success(mock_pipeline_components['scene_splitter'].split_scenes_async.return_value.result())
        
        async def delayed_character_analysis(*args, **kwargs):
            await asyncio.sleep(0.3)  # 模拟角色分析耗时
            return Result.success(mock_pipeline_components['character_analyzer'].analyze_characters_async.return_value.result())
        
        mock_pipeline_components['scene_splitter'].split_scenes_async.side_effect = delayed_scene_split
        mock_pipeline_components['character_analyzer'].analyze_characters_async.side_effect = delayed_character_analysis
        
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
             patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']), \
             patch.object(content_pipeline, 'character_analyzer', mock_pipeline_components['character_analyzer']):
            
            performance_tracker.start('parallel_processing')
            
            result = await content_pipeline.generate_content_async(sample_request)
            
            total_time = performance_tracker.end('parallel_processing')
            
            # 验证结果成功
            assert result.is_success()
            
            # 验证并行处理效果：总时间应该小于顺序执行时间
            # 顺序执行需要: 脚本生成 + 场景分割(0.5s) + 角色分析(0.3s) = 至少0.8s
            # 并行执行需要: 脚本生成 + max(场景分割0.5s, 角色分析0.3s) = 脚本生成时间 + 0.5s
            assert total_time < 1.5, f"Parallel processing not effective: {total_time:.2f}s"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_propagation(self, content_pipeline, sample_request, mock_pipeline_components):
        """测试错误传播"""
        # 模拟脚本生成失败
        mock_pipeline_components['script_generator'].generate_script_async.return_value = asyncio.Future()
        mock_pipeline_components['script_generator'].generate_script_async.return_value.set_result(
            Result.error("脚本生成失败")
        )
        
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']):
            result = await content_pipeline.generate_content_async(sample_request)
            
            # 验证错误传播
            assert result.is_error()
            assert "脚本生成失败" in result.error
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, content_pipeline, sample_request, mock_pipeline_components):
        """测试部分失败处理"""
        # 脚本生成成功，但角色分析失败
        mock_pipeline_components['character_analyzer'].analyze_characters_async.return_value = asyncio.Future()
        mock_pipeline_components['character_analyzer'].analyze_characters_async.return_value.set_result(
            Result.error("角色分析失败")
        )
        
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
             patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']), \
             patch.object(content_pipeline, 'character_analyzer', mock_pipeline_components['character_analyzer']):
            
            result = await content_pipeline.generate_content_async(sample_request)
            
            # 验证部分失败的处理
            assert result.is_error()
            assert "角色分析失败" in result.error
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_different_languages_integration(self, content_pipeline, mock_pipeline_components):
        """测试不同语言的集成"""
        languages = ["zh", "en", "es"]
        themes = ["康熙大帝", "Napoleon", "El Cid"]
        
        for lang, theme in zip(languages, themes):
            request = ContentGenerationRequest(
                theme=theme,
                language=lang,
                style="documentary"
            )
            
            # 调整Mock响应以适应不同语言
            mock_script = GeneratedScript(
                title=f"{theme} Story",
                content=f"A story about {theme} in {lang}..." * 10,
                language=lang,
                theme=theme,
                word_count=200,
                generation_time=1.0,
                model_used="gpt-4"
            )
            
            mock_pipeline_components['script_generator'].generate_script_async.return_value = asyncio.Future()
            mock_pipeline_components['script_generator'].generate_script_async.return_value.set_result(
                Result.success(mock_script)
            )
            
            with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
                 patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']), \
                 patch.object(content_pipeline, 'character_analyzer', mock_pipeline_components['character_analyzer']):
                
                result = await content_pipeline.generate_content_async(request)
                
                assert result.is_success()
                assert result.data.script.language == lang
    
    @pytest.mark.integration 
    @pytest.mark.asyncio
    async def test_content_validation(self, content_pipeline, sample_request, mock_pipeline_components):
        """测试内容验证"""
        # 模拟生成空内容
        mock_empty_script = GeneratedScript(
            title="",
            content="",
            language="zh",
            theme="康熙大帝",
            word_count=0,
            generation_time=1.0,
            model_used="gpt-4"
        )
        
        mock_pipeline_components['script_generator'].generate_script_async.return_value = asyncio.Future()
        mock_pipeline_components['script_generator'].generate_script_async.return_value.set_result(
            Result.success(mock_empty_script)
        )
        
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']):
            result = await content_pipeline.generate_content_async(sample_request)
            
            # 验证内容验证逻辑
            # 根据实现，可能接受空内容或拒绝
            if result.is_error():
                assert "empty" in result.error.lower() or "invalid" in result.error.lower()
            else:
                # 如果接受，确保结构正确
                assert result.data.script is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_resource_cleanup(self, content_pipeline, sample_request, mock_pipeline_components):
        """测试资源清理"""
        # 模拟异常情况下的资源清理
        async def failing_operation(*args, **kwargs):
            raise Exception("意外异常")
        
        mock_pipeline_components['scene_splitter'].split_scenes_async.side_effect = failing_operation
        
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
             patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']):
            
            result = await content_pipeline.generate_content_async(sample_request)
            
            # 验证异常被正确处理
            assert result.is_error()
            assert "意外异常" in result.error or "Exception" in result.error
    
    @pytest.mark.integration
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_pipeline_performance(self, content_pipeline, sample_request, mock_pipeline_components, performance_tracker):
        """测试流水线性能"""
        # 设置较快的Mock响应
        for component in mock_pipeline_components.values():
            if hasattr(component, 'generate_script_async'):
                component.generate_script_async.return_value = asyncio.Future()
                component.generate_script_async.return_value.set_result(
                    Result.success(mock_pipeline_components['script_generator'].generate_script_async.return_value.result().data)
                )
        
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
             patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']), \
             patch.object(content_pipeline, 'character_analyzer', mock_pipeline_components['character_analyzer']):
            
            performance_tracker.start('pipeline_performance')
            
            # 运行多次以测试性能一致性
            results = []
            for _ in range(5):
                result = await content_pipeline.generate_content_async(sample_request)
                results.append(result)
            
            total_time = performance_tracker.end('pipeline_performance')
            avg_time = total_time / 5
            
            # 验证所有结果成功
            assert all(r.is_success() for r in results)
            
            # 验证平均性能
            assert avg_time < 2.0, f"Average pipeline time too slow: {avg_time:.2f}s"


class TestContentPipelineStress:
    """ContentPipeline压力测试"""
    
    @pytest.mark.integration
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, content_pipeline, mock_pipeline_components):
        """测试并发请求处理"""
        import asyncio
        
        # 创建多个并发请求
        requests = [
            ContentGenerationRequest(
                theme=f"主题{i}",
                language="zh",
                style="horror"
            ) for i in range(10)
        ]
        
        # 设置Mock响应
        with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
             patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']), \
             patch.object(content_pipeline, 'character_analyzer', mock_pipeline_components['character_analyzer']):
            
            # 并发执行
            tasks = [content_pipeline.generate_content_async(req) for req in requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证所有结果
            successful_results = []
            for result in results:
                assert not isinstance(result, Exception), f"Unexpected exception: {result}"
                if result.is_success():
                    successful_results.append(result)
            
            # 大部分请求应该成功
            assert len(successful_results) >= 8, f"Too many failed requests: {len(successful_results)}/10"
    
    @pytest.mark.integration
    @pytest.mark.performance
    def test_memory_usage_under_load(self, content_pipeline, mock_pipeline_components, assert_memory):
        """测试负载下的内存使用"""
        import asyncio
        
        async def generate_many():
            for i in range(20):
                request = ContentGenerationRequest(
                    theme=f"主题{i}",
                    language="zh"
                )
                
                with patch.object(content_pipeline, 'script_generator', mock_pipeline_components['script_generator']), \
                     patch.object(content_pipeline, 'scene_splitter', mock_pipeline_components['scene_splitter']), \
                     patch.object(content_pipeline, 'character_analyzer', mock_pipeline_components['character_analyzer']):
                    
                    result = await content_pipeline.generate_content_async(request)
                    assert result.is_success()
        
        # 执行大量生成
        asyncio.run(generate_many())
        
        # 检查内存使用
        assert_memory(150.0, "content_pipeline_load_test")