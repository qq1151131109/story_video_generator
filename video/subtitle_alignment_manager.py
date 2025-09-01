"""
统一字幕对齐管理器
集成多种时间戳对齐方案，提供统一接口
"""
import os
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from video.subtitle_processor import SubtitleProcessor, SubtitleSegment

# 条件导入WhisperX
try:
    from media.whisper_alignment import WhisperXAligner
    WHISPERX_AVAILABLE = True
except ImportError:
    WHISPERX_AVAILABLE = False
    WhisperXAligner = None

@dataclass
class AlignmentRequest:
    """字幕对齐请求"""
    audio_file: str              # 音频文件路径
    script_text: str             # 脚本文本
    tts_subtitles: Optional[List] = None  # TTS返回的时间戳（fallback用）
    language: str = 'zh'         # 语言代码
    max_chars_per_line: int = 12 # 每行最大字符数
    max_duration_per_subtitle: float = 3.0  # 每条字幕最大时长

@dataclass 
class AlignmentResult:
    """字幕对齐结果"""
    subtitles: List[SubtitleSegment]  # 对齐后的字幕段
    method: str                       # 使用的对齐方法
    total_segments: int              # 总段数
    total_duration: float            # 总时长
    confidence_score: float          # 平均置信度(WhisperX)
    debug_info: Optional[Dict] = None # 调试信息

class SubtitleAlignmentManager:
    """
    统一字幕对齐管理器
    
    支持多种对齐方案：
    1. WhisperX精确词级别对齐（优先）
    2. TTS时间戳 + 智能分割（fallback）
    3. 基于文本长度的估计对齐（最后备选）
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.subtitle_alignment')
        
        # 初始化子组件
        self.subtitle_processor = SubtitleProcessor(config_manager, file_manager)
        
        # WhisperX对齐器（按需初始化）
        self._whisper_aligner = None
        
        # 配置参数
        self.alignment_config = self._load_alignment_config()
        
        self.logger.info("Subtitle alignment manager initialized")
    
    def _load_alignment_config(self) -> Dict[str, Any]:
        """加载对齐配置"""
        whisperx_config = self.config.get('whisperx', {})
        subtitle_config = self.config.get('subtitle', {})
        
        return {
            # 对齐方法优先级
            'prefer_whisperx': whisperx_config.get('enabled', False) and WHISPERX_AVAILABLE,
            
            # 字幕分割参数
            'max_chars_per_line': subtitle_config.get('max_line_length', 12),
            'max_duration_per_subtitle': subtitle_config.get('max_duration_per_subtitle', 3.0),
            
            # WhisperX参数
            'whisperx_model': whisperx_config.get('model_size', 'large-v3'),
            'whisperx_device': whisperx_config.get('device', 'auto'),
            
            # 质量控制
            'min_confidence_threshold': whisperx_config.get('min_confidence_threshold', 0.5),
        }
    
    def align_subtitles(self, request: AlignmentRequest) -> AlignmentResult:
        """
        执行字幕对齐
        
        Args:
            request: 对齐请求
            
        Returns:
            AlignmentResult: 对齐结果
        """
        self.logger.info(f"Starting subtitle alignment for audio: {request.audio_file}")
        
        # 只使用WhisperX精确对齐
        if self.alignment_config['prefer_whisperx']:
            result = self._try_whisperx_alignment(request)
            if result:
                return result
        
        # 如果没有WhisperX或WhisperX失败，直接抛出异常
        raise Exception("WhisperX alignment failed or not available. No fallback methods provided.")
    
    def _try_whisperx_alignment(self, request: AlignmentRequest) -> Optional[AlignmentResult]:
        """尝试WhisperX对齐"""
        if not WHISPERX_AVAILABLE:
            self.logger.warning("WhisperX not available, skipping")
            return None
        
        try:
            self.logger.info("Attempting WhisperX alignment...")
            
            # 初始化WhisperX对齐器
            if self._whisper_aligner is None:
                self._whisper_aligner = WhisperXAligner(self.config, self.file_manager)
            
            # 执行对齐
            alignment_result = self._whisper_aligner.align_audio_text(
                request.audio_file,
                request.script_text,
                request.language
            )
            
            if not alignment_result:
                self.logger.warning("WhisperX alignment returned no results")
                return None
            
            # 创建精确字幕
            precise_subtitles = self._whisper_aligner.create_precise_subtitles(
                alignment_result,
                max_chars_per_subtitle=request.max_chars_per_line,
                max_duration_per_subtitle=request.max_duration_per_subtitle
            )
            
            # 转换为SubtitleSegment格式
            subtitle_segments = []
            total_confidence = 0.0
            
            for sub in precise_subtitles:
                subtitle_segment = SubtitleSegment(
                    text=sub['text'],
                    start_time=sub['start'],
                    end_time=sub['end'],
                    duration=sub['duration']
                )
                subtitle_segments.append(subtitle_segment)
                total_confidence += sub.get('confidence', 0.8)
            
            # 计算平均置信度
            avg_confidence = total_confidence / len(precise_subtitles) if precise_subtitles else 0.0
            
            # 保存调试信息
            debug_path = self.file_manager.get_output_path('debug', 'whisperx_alignment_debug.json')
            self._whisper_aligner.save_alignment_debug_info(alignment_result, debug_path)
            
            # 清理模型缓存
            self._whisper_aligner.cleanup_models()
            
            result = AlignmentResult(
                subtitles=subtitle_segments,
                method='WhisperX',
                total_segments=len(subtitle_segments),
                total_duration=subtitle_segments[-1].end_time if subtitle_segments else 0.0,
                confidence_score=avg_confidence,
                debug_info={'debug_file': debug_path}
            )
            
            self.logger.info(f"WhisperX alignment successful: {len(subtitle_segments)} segments, confidence: {avg_confidence:.3f}")
            return result
            
        except Exception as e:
            self.logger.error(f"WhisperX alignment failed: {e}")
            return None
    

    

    
    def save_alignment_result(self, result: AlignmentResult, output_path: str) -> bool:
        """保存对齐结果为SRT文件"""
        try:
            srt_content = self.subtitle_processor.generate_srt(result.subtitles)
            success = self.file_manager.save_text(srt_content, output_path)
            
            if success:
                self.logger.info(f"Subtitle alignment saved: {output_path} ({result.method})")
                return True
            else:
                self.logger.error(f"Failed to save alignment result: {output_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error saving alignment result: {e}")
            return False
    
    def get_alignment_stats(self, result: AlignmentResult) -> Dict[str, Any]:
        """获取对齐统计信息"""
        if not result.subtitles:
            return {}
        
        total_chars = sum(len(seg.text) for seg in result.subtitles)
        
        return {
            'method': result.method,
            'total_segments': result.total_segments,
            'total_duration': result.total_duration,
            'total_characters': total_chars,
            'avg_chars_per_segment': total_chars / result.total_segments,
            'avg_duration_per_segment': result.total_duration / result.total_segments,
            'chars_per_second': total_chars / result.total_duration if result.total_duration > 0 else 0,
            'confidence_score': result.confidence_score
        }
    
    def _get_audio_duration(self, audio_file: str) -> Optional[float]:
        """获取音频文件的实际时长"""
        try:
            import subprocess
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                '-of', 'csv=p=0', audio_file
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration
        except Exception as e:
            self.logger.warning(f"Could not get audio duration for {audio_file}: {e}")
        
        return None
    
    def cleanup(self):
        """清理资源"""
        if self._whisper_aligner:
            self._whisper_aligner.cleanup_models()
            self._whisper_aligner = None
        
        self.logger.info("Subtitle alignment manager cleaned up")
    
    def __str__(self) -> str:
        methods = []
        if self.alignment_config['prefer_whisperx']:
            methods.append("WhisperX")
        if self.alignment_config.get('enable_tts_fallback', False):
            methods.append("TTS")
        if self.alignment_config.get('enable_estimate_fallback', False):
            methods.append("Estimation")
        
        return f"SubtitleAlignmentManager(methods={methods})"