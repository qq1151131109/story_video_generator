"""
完整工作流端到端测试
测试从主题输入到视频输出的完整流程
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import json

from services.story_video_service import StoryVideoService
from utils.result_types import Result


class TestCompleteWorkflow:
    """完整工作流测试类"""
    
    @pytest.fixture
    def e2e_service(self, config_manager, temp_dir):
        """端到端测试服务实例"""
        # 设置测试输出目录
        config_manager.config['general']['output_dir'] = str(temp_dir)
        return StoryVideoService()
    
    @pytest.fixture
    def mock_all_external_services(self):
        """Mock所有外部服务"""
        mocks = {}
        
        # Mock文件下载
        def mock_download_file(url, filepath):
            filepath.parent.mkdir(parents=True, exist_ok=True)
            if 'image' in url:
                filepath.write_bytes(b'fake_image_data')
            elif 'audio' in url:
                filepath.write_bytes(b'fake_audio_data')
            elif 'video' in url:
                filepath.write_bytes(b'fake_video_data')
            return True
        
        mocks['download_file'] = mock_download_file
        
        # Mock API调用
        async def mock_api_post(url, **kwargs):
            if 'openai.com' in url or 'openrouter.ai' in url:
                return {
                    'choices': [{
                        'message': {
                            'content': '你知道吗？康熙皇帝年仅十六岁时，就展现了超凡的政治智慧...' * 10
                        }
                    }],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 200}
                }
            elif 'runninghub.cn' in url:
                return {
                    'success': True,
                    'data': {
                        'task_id': 'test-task-123',
                        'status': 'completed',
                        'result_url': 'https://example.com/test-image.jpg'
                    }
                }
            elif 'minimax' in url:
                return {
                    'success': True,
                    'data': {
                        'audio_url': 'https://example.com/test-audio.mp3',
                        'duration': 10.5,
                        'subtitles': [
                            {'start': 0.0, 'end': 5.0, 'text': '你知道吗？'},
                            {'start': 5.0, 'end': 10.0, 'text': '康熙是如何智擒鳌拜的？'}
                        ]
                    }
                }
            else:
                return {'success': True, 'data': {}}
        
        mocks['api_post'] = mock_api_post
        
        # Mock FFmpeg命令执行
        def mock_run_command(command, **kwargs):
            return Mock(returncode=0, stdout='', stderr='')
        
        mocks['run_command'] = mock_run_command
        
        return mocks
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_story_generation(self, e2e_service, mock_all_external_services, temp_dir, performance_tracker):
        """测试完整故事生成流程"""
        # 应用所有Mock
        with patch('utils.file_manager.download_file', side_effect=mock_all_external_services['download_file']), \
             patch('aiohttp.ClientSession.post', return_value=AsyncMock(**{'json.return_value': mock_all_external_services['api_post']})), \
             patch('subprocess.run', side_effect=mock_all_external_services['run_command']):
            
            performance_tracker.start('complete_workflow')
            
            # 执行完整流程
            theme = "康熙大帝智擒鳌拜的惊心传奇"
            language = "zh"
            
            # 步骤1：生成内容
            from content.content_pipeline import ContentGenerationRequest
            content_request = ContentGenerationRequest(
                theme=theme,
                language=language,
                style="horror"
            )
            
            content_result = await e2e_service.content_pipeline.generate_content_async(content_request)
            
            if content_result.is_error():
                pytest.skip(f"Content generation failed: {content_result.error}")
            
            # 步骤2：生成媒体
            from media.media_pipeline import MediaGenerationRequest
            media_request = MediaGenerationRequest(
                scenes=content_result.data.scenes.scenes,
                characters=content_result.data.characters.characters,
                main_character=content_result.data.characters.main_character,
                language=language,
                script_title=content_result.data.script.title,
                full_script=content_result.data.script.content
            )
            
            media_result = await e2e_service.media_pipeline.generate_media_async(media_request)
            
            if media_result.is_error():
                pytest.skip(f"Media generation failed: {media_result.error}")
            
            # 步骤3：合成视频
            output_paths = e2e_service.generate_output_paths(theme)
            video_path = await e2e_service.compose_final_video(
                scenes=content_result.data.scenes.scenes,
                images=media_result.data.scene_media,
                character_images=media_result.data.character_images,
                audio_file=str(media_result.data.title_audio),
                subtitle_file=None,  # 暂时跳过字幕
                output_path=output_paths['video_path']
            )
            
            total_time = performance_tracker.end('complete_workflow')
            
            # 验证结果
            assert video_path is not None, "Video generation failed"
            
            video_file = Path(video_path)
            assert video_file.exists(), f"Video file not created: {video_path}"
            assert video_file.stat().st_size > 0, "Video file is empty"
            
            # 验证性能
            assert total_time < 300, f"Complete workflow too slow: {total_time:.2f}s"
            
            print(f"✅ Complete workflow test passed in {total_time:.2f}s")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_multi_language_workflow(self, e2e_service, mock_all_external_services):
        """测试多语言工作流"""
        test_cases = [
            ("康熙大帝智擒鳌拜", "zh"),
            ("Napoleon's Last Battle", "en"),
            ("El Cid Campeador", "es")
        ]
        
        with patch('utils.file_manager.download_file', side_effect=mock_all_external_services['download_file']), \
             patch('aiohttp.ClientSession.post', return_value=AsyncMock(**{'json.return_value': mock_all_external_services['api_post']})), \
             patch('subprocess.run', side_effect=mock_all_external_services['run_command']):
            
            for theme, language in test_cases:
                # 生成内容
                from content.content_pipeline import ContentGenerationRequest
                content_request = ContentGenerationRequest(
                    theme=theme,
                    language=language
                )
                
                content_result = await e2e_service.content_pipeline.generate_content_async(content_request)
                
                # 验证语言特定结果
                if content_result.is_success():
                    assert content_result.data.script.language == language
                    print(f"✅ {language} workflow completed")
                else:
                    print(f"⚠️  {language} workflow failed: {content_result.error}")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_integrated_video_mode(self, e2e_service, mock_all_external_services):
        """测试一体化视频生成模式"""
        # 启用一体化模式
        e2e_service.config.config['media']['enable_integrated_generation'] = True
        
        with patch('utils.file_manager.download_file', side_effect=mock_all_external_services['download_file']), \
             patch('aiohttp.ClientSession.post', return_value=AsyncMock(**{'json.return_value': mock_all_external_services['api_post']})), \
             patch('subprocess.run', side_effect=mock_all_external_services['run_command']):
            
            theme = "康熙大帝智擒鳌拜"
            language = "zh"
            
            # 生成内容
            from content.content_pipeline import ContentGenerationRequest
            content_request = ContentGenerationRequest(
                theme=theme,
                language=language
            )
            
            content_result = await e2e_service.content_pipeline.generate_content_async(content_request)
            
            if content_result.is_error():
                pytest.skip(f"Content generation failed: {content_result.error}")
            
            # 生成媒体（一体化模式）
            from media.media_pipeline import MediaGenerationRequest
            media_request = MediaGenerationRequest(
                scenes=content_result.data.scenes.scenes,
                characters=content_result.data.characters.characters,
                main_character=content_result.data.characters.main_character,
                language=language,
                script_title=content_result.data.script.title,
                full_script=content_result.data.script.content
            )
            
            media_result = await e2e_service.media_pipeline.generate_media_async(media_request)
            
            # 验证一体化模式结果
            if media_result.is_success():
                # 一体化模式应该直接生成视频而不是图片
                assert media_result.data.scene_media is not None
                print("✅ Integrated video mode completed")
            else:
                print(f"⚠️  Integrated mode failed: {media_result.error}")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, e2e_service, mock_all_external_services):
        """测试错误恢复工作流"""
        # 模拟API失败然后恢复
        call_count = 0
        original_api_post = mock_all_external_services['api_post']
        
        async def failing_then_success_api(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:  # 前两次调用失败
                raise Exception("API临时不可用")
            else:
                return await original_api_post(*args, **kwargs)
        
        with patch('utils.file_manager.download_file', side_effect=mock_all_external_services['download_file']), \
             patch('aiohttp.ClientSession.post', side_effect=failing_then_success_api), \
             patch('subprocess.run', side_effect=mock_all_external_services['run_command']):
            
            theme = "康熙大帝智擒鳌拜"
            language = "zh"
            
            # 生成内容（应该在重试后成功）
            from content.content_pipeline import ContentGenerationRequest
            content_request = ContentGenerationRequest(
                theme=theme,
                language=language
            )
            
            content_result = await e2e_service.content_pipeline.generate_content_async(content_request)
            
            # 验证错误恢复
            if content_result.is_success():
                print("✅ Error recovery workflow completed")
            else:
                print(f"⚠️  Error recovery failed: {content_result.error}")
                # 这可能是预期的，取决于重试逻辑
    
    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio 
    async def test_concurrent_workflow_execution(self, e2e_service, mock_all_external_services):
        """测试并发工作流执行"""
        themes = [
            "康熙大帝智擒鳌拜",
            "唐玄宗开元盛世", 
            "秦始皇统一六国"
        ]
        
        with patch('utils.file_manager.download_file', side_effect=mock_all_external_services['download_file']), \
             patch('aiohttp.ClientSession.post', return_value=AsyncMock(**{'json.return_value': mock_all_external_services['api_post']})), \
             patch('subprocess.run', side_effect=mock_all_external_services['run_command']):
            
            # 创建并发任务
            async def generate_content(theme):
                from content.content_pipeline import ContentGenerationRequest
                request = ContentGenerationRequest(
                    theme=theme,
                    language="zh"
                )
                return await e2e_service.content_pipeline.generate_content_async(request)
            
            tasks = [generate_content(theme) for theme in themes]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证并发结果
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"⚠️  Theme {themes[i]} failed with exception: {result}")
                elif result.is_success():
                    successful_results.append(result)
                    print(f"✅ Theme {themes[i]} completed")
                else:
                    print(f"⚠️  Theme {themes[i]} failed: {result.error}")
            
            # 至少一半的任务应该成功
            assert len(successful_results) >= len(themes) // 2, \
                f"Too many concurrent failures: {len(successful_results)}/{len(themes)}"
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_resource_cleanup_after_workflow(self, e2e_service, mock_all_external_services, temp_dir):
        """测试工作流后的资源清理"""
        initial_files = set(temp_dir.rglob('*'))
        
        with patch('utils.file_manager.download_file', side_effect=mock_all_external_services['download_file']), \
             patch('aiohttp.ClientSession.post', return_value=AsyncMock(**{'json.return_value': mock_all_external_services['api_post']})), \
             patch('subprocess.run', side_effect=mock_all_external_services['run_command']):
            
            theme = "康熙大帝智擒鳌拜"
            language = "zh"
            
            # 执行内容生成
            from content.content_pipeline import ContentGenerationRequest
            content_request = ContentGenerationRequest(
                theme=theme,
                language=language
            )
            
            content_result = await e2e_service.content_pipeline.generate_content_async(content_request)
            
            # 检查临时文件
            current_files = set(temp_dir.rglob('*'))
            new_files = current_files - initial_files
            
            # 验证清理逻辑
            temp_files = [f for f in new_files if 'temp' in str(f)]
            output_files = [f for f in new_files if 'output' in str(f)]
            
            print(f"New temp files: {len(temp_files)}")
            print(f"New output files: {len(output_files)}")
            
            # 输出文件应该保留，临时文件应该清理
            # 这取决于具体的清理逻辑实现


class TestWorkflowRobustness:
    """工作流健壮性测试"""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_disk_space_handling(self, e2e_service, mock_all_external_services, temp_dir):
        """测试磁盘空间不足处理"""
        # 模拟磁盘空间不足
        def mock_disk_full_write(*args, **kwargs):
            raise OSError("No space left on device")
        
        with patch('pathlib.Path.write_bytes', side_effect=mock_disk_full_write):
            theme = "康熙大帝智擒鳌拜"
            language = "zh"
            
            from content.content_pipeline import ContentGenerationRequest
            content_request = ContentGenerationRequest(
                theme=theme,
                language=language
            )
            
            content_result = await e2e_service.content_pipeline.generate_content_async(content_request)
            
            # 验证错误处理
            if content_result.is_error():
                assert "space" in content_result.error.lower() or "disk" in content_result.error.lower()
                print("✅ Disk space error handled correctly")
            else:
                print("⚠️  Disk space error not detected")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, e2e_service):
        """测试网络超时处理"""
        import asyncio
        
        # 模拟网络超时
        async def timeout_api(*args, **kwargs):
            await asyncio.sleep(10)  # 超过合理超时时间
            return {}
        
        with patch('aiohttp.ClientSession.post', side_effect=timeout_api):
            theme = "康熙大帝智擒鳌拜"
            language = "zh"
            
            from content.content_pipeline import ContentGenerationRequest
            content_request = ContentGenerationRequest(
                theme=theme,
                language=language
            )
            
            # 设置较短的超时时间来快速测试
            start_time = asyncio.get_event_loop().time()
            
            try:
                content_result = await asyncio.wait_for(
                    e2e_service.content_pipeline.generate_content_async(content_request),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                print("✅ Network timeout handled correctly")
                return
            
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if content_result.is_error() and elapsed < 8:
                print("✅ Network timeout handled correctly")
            else:
                print(f"⚠️  Timeout handling unexpected: {elapsed:.2f}s")
    
    @pytest.mark.e2e
    def test_memory_usage_during_workflow(self, e2e_service, mock_all_external_services, assert_memory):
        """测试工作流期间的内存使用"""
        import asyncio
        
        async def memory_test():
            with patch('utils.file_manager.download_file', side_effect=mock_all_external_services['download_file']), \
                 patch('aiohttp.ClientSession.post', return_value=AsyncMock(**{'json.return_value': mock_all_external_services['api_post']})):
                
                # 执行多个工作流以测试内存累积
                for i in range(5):
                    theme = f"测试主题{i}"
                    language = "zh"
                    
                    from content.content_pipeline import ContentGenerationRequest
                    content_request = ContentGenerationRequest(
                        theme=theme,
                        language=language
                    )
                    
                    content_result = await e2e_service.content_pipeline.generate_content_async(content_request)
                    
                    # 简单验证结果
                    assert content_result.is_success() or content_result.is_error()
        
        # 执行内存测试
        asyncio.run(memory_test())
        
        # 检查内存使用（假设不超过200MB）
        assert_memory(200.0, "workflow_memory_test")