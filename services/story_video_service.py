"""
故事视频生成服务 - 将main.py的核心逻辑抽象为服务类
提供清晰的服务化架构，便于维护和测试
"""
import asyncio
import logging
import time as time_module
from pathlib import Path
from typing import Optional, Dict, Any

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from utils.i18n import get_i18n_manager, set_global_language, t
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
        self.content_pipeline = ContentPipeline(self.config, None, self.files)
        self.media_pipeline = MediaPipeline(self.config, None, self.files)
        self.video_composer = VideoComposer(self.config, self.files)
        
        self.logger.info("StoryVideoService initialized successfully")
    
    async def generate_complete_audio(self, script_content: str, language: str) -> Dict[str, Any]:
        """
        生成完整脚本的音频文件
        
        Args:
            script_content: 完整脚本内容
            language: 语言代码
            
        Returns:
            Dict: 音频生成结果 {audio_file: str, audio_result: GeneratedAudio}
        """
        self.logger.info("Generating complete script audio...")
        
        audio_generator = AudioGenerator(self.config, None, self.files)
        
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
                return {
                    'audio_file': main_audio_file,
                    'audio_result': full_audio_result,
                    'success': True
                }
            else:
                self.logger.error("Complete audio generation failed")
                return {
                    'audio_file': None,
                    'audio_result': None,
                    'success': False
                }
        except Exception as e:
            self.logger.error(f"Complete audio generation error: {e}")
            return {
                'audio_file': None,
                'audio_result': None,
                'success': False,
                'error': str(e)
            }
    
    async def process_subtitle_alignment(self, 
                                       audio_file: str,
                                       script_content: str,
                                       tts_subtitles,
                                       language: str) -> Dict[str, Any]:
        """
        处理字幕对齐
        
        Args:
            audio_file: 音频文件路径
            script_content: 脚本内容
            tts_subtitles: TTS返回的字幕
            language: 语言代码
            
        Returns:
            Dict: 对齐结果
        """
        self.logger.info("Performing subtitle alignment...")
        
        alignment_manager = SubtitleAlignmentManager(self.config, self.files)
        
        try:
            # 创建对齐请求
            alignment_request = AlignmentRequest(
                audio_file=audio_file,
                script_text=script_content,
                tts_subtitles=tts_subtitles,
                language=language,
                max_chars_per_line=12,  # 移动端优化
                max_duration_per_subtitle=3.0
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
            
            return {
                'segments': all_subtitle_segments,
                'method': alignment_result.method,
                'stats': stats,
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Subtitle alignment failed: {e}")
            return {
                'segments': [],
                'success': False,
                'error': str(e)
            }
    
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
                                images,
                                audio_file: Optional[str],
                                subtitle_file: Optional[str],
                                output_path: str,
                                audio_duration: Optional[float] = None) -> Optional[str]:
        """
        合成最终视频
        
        Args:
            scenes: 场景列表
            images: 图像列表
            audio_file: 音频文件路径
            subtitle_file: 字幕文件路径
            output_path: 输出视频路径
            audio_duration: 音频时长
            
        Returns:
            Optional[str]: 成功时返回视频文件路径，失败时返回None
        """
        self.logger.info("Composing final video...")
        
        try:
            video_path = await self.video_composer.create_video(
                scenes=scenes,
                images=images,
                audio_file=audio_file,
                subtitle_file=str(subtitle_file) if subtitle_file else None,
                output_path=str(output_path),
                audio_duration=audio_duration,
                use_jianying_style=True  # 🎬 启用剪映风格字幕
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
        total_time = content_result.total_processing_time + media_result.total_processing_time
        self.logger.info(f"Story generation completed in {total_time:.2f}s")
        self.logger.info(f"Output files:")
        self.logger.info(f"  - Content: {content_files.get('summary', 'N/A')}")
        self.logger.info(f"  - Media: {media_files.get('manifest', 'N/A')}")
        if video_path:
            self.logger.info(f"  - Video: {video_path}")
    
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