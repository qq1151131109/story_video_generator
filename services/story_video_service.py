"""
故事视频生成服务 - 将main.py的核心逻辑抽象为服务类
提供清晰的服务化架构，便于维护和测试
"""
import asyncio
import logging
import time as time_module
from pathlib import Path
from typing import Optional, Dict, Any, List

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from utils.i18n import get_i18n_manager, set_global_language, t
from utils.result_types import Result, AudioResult, VideoResult
from content.content_pipeline import ContentPipeline, ContentGenerationRequest
from media.media_pipeline import MediaPipeline, MediaGenerationRequest
from media.audio_generator import AudioGenerator, AudioGenerationRequest
from video.video_composer import VideoComposer
from video.subtitle_processor import SubtitleProcessor
from video.subtitle_alignment_manager import SubtitleAlignmentManager, AlignmentRequest


class StoryVideoService:
    """故事视频生成服务"""
    
    def __init__(self):
        """初始化服务组件"""
        self.logger = setup_logging().get_logger('story_generator')
        self.config = ConfigManager()
        # 缓存已删除
        self.files = FileManager()
        
        # 验证配置
        config_errors = self.config.validate_config()
        if config_errors:
            self.logger.error(f"Configuration errors: {config_errors}")
            raise RuntimeError(f"Invalid configuration: {config_errors}")
        
        # 初始化流水线
        self.content_pipeline = ContentPipeline(self.config, self.files)
        self.media_pipeline = MediaPipeline(self.config, self.files)
        self.video_composer = VideoComposer(self.config, self.files)
        
        self.logger.info("StoryVideoService initialized successfully")
    
    async def generate_scene_audio_segments(self, scenes, language: str) -> Result[Dict[str, Any]]:
        """
        按原始Coze工作流逻辑：为每个场景分别生成音频片段
        
        Args:
            scenes: 场景列表
            language: 语言代码
            
        Returns:
            Result[Dict]: 包含audio_segments和total_duration的结果
        """
        self.logger.info("🎵 按Coze工作流逻辑生成分场景音频片段...")
        
        audio_generator = AudioGenerator(self.config, self.files)
        
        # 从配置中获取音频设置
        audio_config = self.config.get('media.audio', {})
        primary_provider = audio_config.get('primary_provider', 'minimax')
        
        # 根据provider选择合适的voice_id
        if primary_provider == 'minimax':
            voice_id = audio_config.get('minimax_voice', 'male-qn-qingse')
        else:
            voice_id = audio_config.get('voice_id', 'pNInz6obpgDQGcFmaJgB')
        
        audio_segments = []
        total_duration = 0
        
        try:
            for i, scene in enumerate(scenes):
                self.logger.info(f"生成场景{i+1}音频: {scene.content[:30]}...")
                
                scene_audio_request = AudioGenerationRequest(
                    text=scene.content,
                    language=language,
                    voice_id=voice_id,
                    speed=audio_config.get('voice_speed', 1.2)
                )
                
                # 为每个场景生成独立的音频片段
                scene_audio_result = await audio_generator.generate_audio_async(
                    scene_audio_request, 
                    provider=primary_provider
                )
                
                if scene_audio_result and scene_audio_result.file_path:
                    audio_segments.append({
                        'file': scene_audio_result.file_path,
                        'duration': scene_audio_result.duration_seconds,
                        'scene_id': i,
                        'scene_sequence': scene.sequence,
                        'content': scene.content
                    })
                    total_duration += scene_audio_result.duration_seconds
                    self.logger.info(f"✅ 场景{i+1}音频: {scene_audio_result.duration_seconds:.1f}s")
                else:
                    self.logger.error(f"❌ 场景{i+1}音频生成失败")
                    return Result.error(f'场景{i+1}音频生成失败')
            
            self.logger.info(f"🎉 所有音频片段生成完成，总时长: {total_duration:.1f}s")
            return Result.success({
                'audio_segments': audio_segments,
                'total_duration': total_duration
            })
            
        except Exception as e:
            self.logger.error(f"分场景音频生成失败: {e}")
            return Result.error(str(e))
    
    async def generate_complete_audio(self, script_content: str, language: str) -> Result[Dict[str, Any]]:
        """
        生成完整脚本的音频文件
        
        Args:
            script_content: 完整脚本内容
            language: 语言代码
            
        Returns:
            Result[Dict]: 音频生成结果
        """
        self.logger.info("Generating complete script audio...")
        
        audio_generator = AudioGenerator(self.config, self.files)
        
        # 从配置中获取音频设置
        audio_config = self.config.get('media.audio', {})
        primary_provider = audio_config.get('primary_provider', 'minimax')
        
        # 根据provider选择合适的voice_id
        if primary_provider == 'minimax':
            voice_id = audio_config.get('minimax_voice', 'male-qn-qingse')
        else:
            voice_id = audio_config.get('voice_id', 'pNInz6obpgDQGcFmaJgB')
        
        full_audio_request = AudioGenerationRequest(
            text=script_content,
            language=language,
            voice_id=voice_id,
            speed=audio_config.get('voice_speed', 1.2)
        )
        
        try:
            # 明确指定使用主要提供商
            full_audio_result = await audio_generator.generate_audio_async(
                full_audio_request, 
                provider=primary_provider
            )
            if full_audio_result and full_audio_result.file_path:
                main_audio_file = full_audio_result.file_path
                self.logger.info(f"Complete audio generated: {full_audio_result.duration_seconds:.1f}s")
                return Result.success({
                    'audio_file': main_audio_file,
                    'audio_result': full_audio_result
                })
            else:
                self.logger.error("Complete audio generation failed")
                return Result.error("Complete audio generation failed")
        except Exception as e:
            self.logger.error(f"Complete audio generation error: {e}")
            return Result.error(str(e))
    
    async def process_subtitle_alignment(self, 
                                       audio_file: str,
                                       script_content: str,
                                       tts_subtitles,
                                       language: str) -> Result[Dict[str, Any]]:
        """
        处理字幕对齐
        
        Args:
            audio_file: 音频文件路径
            script_content: 脚本内容
            tts_subtitles: TTS返回的字幕
            language: 语言代码
            
        Returns:
            Result[Dict]: 对齐结果
        """
        self.logger.info("Performing subtitle alignment...")
        
        alignment_manager = SubtitleAlignmentManager(self.config, self.files)
        
        try:
            # 创建对齐请求 - 从配置读取参数
            subtitle_config = self.config.get('subtitle', {})
            alignment_request = AlignmentRequest(
                audio_file=audio_file,
                script_text=script_content,
                tts_subtitles=tts_subtitles,
                language=language,
                max_chars_per_line=subtitle_config.get('max_chars_per_line', 10),
                max_duration_per_subtitle=subtitle_config.get('force_split_threshold', 3.0)
            )
            
            # 执行对齐
            alignment_result = alignment_manager.align_subtitles(alignment_request)
            all_subtitle_segments = alignment_result.subtitles
            
            # 记录对齐统计信息
            stats = alignment_manager.get_alignment_stats(alignment_result)
            self.logger.info(f"Subtitle alignment completed: {alignment_result.method}")
            self.logger.info(f"Segments: {stats['total_segments']}, Duration: {stats['total_duration']:.1f}s, Confidence: {stats['confidence_score']:.3f}")
            
            # 清理资源
            alignment_manager.cleanup()
            
            return Result.success({
                'segments': all_subtitle_segments,
                'method': alignment_result.method,
                'stats': stats
            })
            
        except Exception as e:
            self.logger.error(f"Subtitle alignment failed: {e}")
            return Result.error(str(e))
    
    def save_subtitle_file(self, subtitle_segments: list, theme: str) -> Optional[str]:
        """
        保存字幕文件
        
        Args:
            subtitle_segments: 字幕段落列表
            theme: 主题（用于生成文件名）
            
        Returns:
            Optional[str]: 保存的字幕文件路径
        """
        if not subtitle_segments:
            self.logger.warning("No subtitle segments to save")
            return None
        
        self.logger.info("Saving synchronized subtitles...")
        subtitle_processor = SubtitleProcessor(self.config, self.files)
        
        timestamp = time_module.strftime("%Y%m%d_%H%M%S")
        subtitle_filename = f"subtitle_{timestamp}.srt"
        subtitle_path = self.files.get_output_path('subtitles', subtitle_filename)
        
        try:
            saved_subtitle_path = subtitle_processor.save_subtitle_file(subtitle_segments, subtitle_path)
            self.logger.info(f"Synchronized subtitles saved: {len(subtitle_segments)} segments")
            return saved_subtitle_path
        except Exception as e:
            self.logger.error(f"Failed to save subtitle file: {e}")
            return None
    
    def generate_output_paths(self, theme: str) -> Dict[str, str]:
        """
        生成输出文件路径
        
        Args:
            theme: 故事主题
            
        Returns:
            Dict: 包含各种输出路径的字典
        """
        timestamp = time_module.strftime("%Y%m%d_%H%M%S")
        safe_theme = theme.replace(' ', '_').replace('/', '_')[:30]
        
        return {
            'video_filename': f"story_video_{safe_theme}_{timestamp}.mp4",
            'video_path': self.files.get_output_path('videos', f"story_video_{safe_theme}_{timestamp}.mp4"),
            'timestamp': timestamp
        }
    
    async def compose_final_video(self,
                                scenes,
                                scene_videos=None,
                                character_images=None,
                                images=None,  # 保持向后兼容
                                audio_file: Optional[str] = None,
                                subtitle_file: Optional[str] = None,
                                output_path: str = None,
                                audio_duration: Optional[float] = None) -> Optional[str]:
        """
        合成最终视频 - 支持一体化模式（角色图像+场景视频）
        
        Args:
            scenes: 场景列表
            scene_videos: 预生成的场景视频列表（一体化模式）
            character_images: 角色图像列表（用于首帧）
            images: 图像列表（传统模式，保持向后兼容）
            audio_file: 音频文件路径
            subtitle_file: 字幕文件路径
            output_path: 输出视频路径
            audio_duration: 音频时长
            
        Returns:
            Optional[str]: 成功时返回视频文件路径，失败时返回None
        """
        self.logger.info("Composing final video...")
        
        try:
            # 一体化模式：优先使用预生成的场景视频
            video_media = scene_videos if scene_videos else images
            
            video_path = await self.video_composer.create_video(
                scenes=scenes,
                images=video_media,  # 在一体化模式下，这里传递的是视频文件
                character_images=character_images,  # 角色图像用于首帧
                audio_file=audio_file,
                subtitle_file=str(subtitle_file) if subtitle_file else None,
                output_path=str(output_path),
                audio_duration=audio_duration,
                use_jianying_style=True,  # 🎬 启用剪映风格字幕
                integrated_mode=bool(scene_videos)  # 标识是否为一体化模式
            )
            
            if video_path:
                self.logger.info(f"Video composition completed: {video_path}")
                return video_path
            else:
                self.logger.error("Video composition failed")
                return None
                
        except Exception as e:
            self.logger.error(f"Video composition failed: {e}")
            return None
    
    def log_completion_summary(self,
                             content_result,
                             media_result,
                             video_path: Optional[str],
                             content_files: Dict,
                             media_files: Dict):
        """
        记录完成总结信息
        
        Args:
            content_result: 内容生成结果
            media_result: 媒体生成结果  
            video_path: 视频文件路径
            content_files: 内容文件路径
            media_files: 媒体文件路径
        """
        from pathlib import Path
        import os
        
        total_time = content_result.total_processing_time + media_result.total_processing_time
        self.logger.info(f"Story generation completed in {total_time:.2f}s")
        self.logger.info(f"Output files:")
        self.logger.info(f"  - Content: {content_files.get('summary', 'N/A')}")
        self.logger.info(f"  - Media: {media_files.get('manifest', 'N/A')}")
        if video_path:
            self.logger.info(f"  - Video: {video_path}")
        
        # 显示详细的日志文件位置
        print("\n" + "="*80)
        print("🎯 故事视频生成完成！")
        print("="*80)
        
        # 显示输出文件
        if video_path and Path(video_path).exists():
            file_size = os.path.getsize(video_path) / (1024*1024)  # MB
            print(f"📹 最终视频: {video_path} ({file_size:.1f}MB)")
        
        # 显示日志文件位置
        log_dir = Path("output/logs")
        print(f"\n📋 详细日志文件位置:")
        
        if log_dir.exists():
            log_files = [
                ("story_generator.log", "主要生成日志 (包含所有详细步骤)"),
                ("detailed.log", "超详细日志 (DEBUG级别)"),
                ("errors.log", "错误日志 (仅错误信息)"),
                ("performance.log", "性能监控日志")
            ]
            
            for log_file, description in log_files:
                log_path = log_dir / log_file
                if log_path.exists():
                    file_size = os.path.getsize(log_path) / 1024  # KB
                    print(f"  📄 {log_path} ({file_size:.1f}KB) - {description}")
        
        print(f"\n🔍 查看完整生成过程:")
        print(f"  cat {log_dir}/story_generator.log")
        print(f"  tail -f {log_dir}/story_generator.log  # 实时查看")
        print(f"  tail -50 {log_dir}/detailed.log      # 查看最近50行详细日志")
        
        print("\n" + "="*80)
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        获取服务统计信息
        
        Returns:
            Dict: 服务统计信息
        """
        return {
            # 缓存已删除
            'config_status': 'valid',
            'supported_languages': self.config.get_supported_languages(),
            'output_dir': self.config.get('general.output_dir')
        }