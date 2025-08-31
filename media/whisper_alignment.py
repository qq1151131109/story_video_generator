"""
WhisperX精确时间戳对齐器
用于TTS音频的词级别时间戳标注
"""
import os
import gc
import logging
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import torch
import torchaudio

from core.config_manager import ConfigManager
from utils.file_manager import FileManager

@dataclass
class WhisperAlignment:
    """WhisperX对齐结果"""
    word: str
    start: float
    end: float
    score: float

@dataclass
class WhisperSegment:
    """WhisperX片段"""
    text: str
    start: float
    end: float
    words: List[WhisperAlignment]

class WhisperXAligner:
    """
    WhisperX精确时间戳对齐器
    
    功能：
    1. 对TTS生成的音频进行精确转录
    2. 提供词级别时间戳
    3. 支持中文等多语言
    4. 基于强制对齐技术
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.whisperx')
        
        # WhisperX配置
        self.whisper_config = self._load_whisperx_config()
        
        # 模型缓存
        self._whisper_model = None
        self._align_model = None
        self._metadata = None
        
        self.logger.info("WhisperX aligner initialized")
    
    def _load_whisperx_config(self) -> Dict[str, Any]:
        """加载WhisperX配置"""
        whisper_config = self.config.get('whisperx', {})
        
        return {
            # 模型配置
            'model_size': whisper_config.get('model_size', 'large-v3'),
            'batch_size': whisper_config.get('batch_size', 16),
            'compute_type': whisper_config.get('compute_type', 'float16'),
            'device': whisper_config.get('device', 'auto'),
            
            # 对齐配置
            'return_char_alignments': whisper_config.get('return_char_alignments', False),
            'print_progress': whisper_config.get('print_progress', True),
            
            # 语言配置
            'language': whisper_config.get('language', 'zh'),  # 中文
            'condition_on_previous_text': False,
            
            # 内存优化
            'enable_vad_filter': whisper_config.get('enable_vad_filter', True),
            'vad_threshold': whisper_config.get('vad_threshold', 0.35),
            'max_new_tokens': whisper_config.get('max_new_tokens', 128),
        }
    
    def _ensure_whisperx_installed(self):
        """确保WhisperX已安装"""
        try:
            import whisperx
            return True
        except ImportError:
            self.logger.error("WhisperX not installed. Please install with: pip install whisperx")
            return False
    
    def _get_device(self) -> str:
        """自动检测最佳设备"""
        if self.whisper_config['device'] == 'auto':
            if torch.cuda.is_available():
                device = "cuda"
                self.logger.info(f"Using CUDA device: {torch.cuda.get_device_name()}")
            else:
                device = "cpu"
                self.logger.info("Using CPU device")
        else:
            device = self.whisper_config['device']
        
        return device
    
    def _load_models(self, device: str, language: str = 'zh'):
        """加载WhisperX模型"""
        if not self._ensure_whisperx_installed():
            return False
        
        try:
            import whisperx
            
            # 加载Whisper转录模型
            if self._whisper_model is None:
                self.logger.info(f"Loading WhisperX model: {self.whisper_config['model_size']}")
                self._whisper_model = whisperx.load_model(
                    self.whisper_config['model_size'], 
                    device, 
                    compute_type=self.whisper_config['compute_type'],
                    language=language
                )
                
            # 加载对齐模型
            if self._align_model is None and self._metadata is None:
                self.logger.info(f"Loading alignment model for language: {language}")
                self._align_model, self._metadata = whisperx.load_align_model(
                    language_code=language, 
                    device=device
                )
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load WhisperX models: {e}")
            return False
    
    def align_audio_text(self, audio_file: str, expected_text: str, 
                        language: str = 'zh') -> Optional[List[WhisperSegment]]:
        """
        对音频文件进行精确时间戳对齐
        
        Args:
            audio_file: 音频文件路径
            expected_text: 预期文本内容
            language: 语言代码
        
        Returns:
            List[WhisperSegment]: 对齐结果，包含词级别时间戳
        """
        if not os.path.exists(audio_file):
            self.logger.error(f"Audio file not found: {audio_file}")
            return None
            
        device = self._get_device()
        
        # 加载模型
        if not self._load_models(device, language):
            return None
        
        try:
            import whisperx
            
            # Step 1: 转录音频
            self.logger.info(f"Transcribing audio: {audio_file}")
            audio = whisperx.load_audio(audio_file)
            
            result = self._whisper_model.transcribe(
                audio, 
                batch_size=self.whisper_config['batch_size'],
                language=language,
                condition_on_previous_text=self.whisper_config['condition_on_previous_text']
            )
            
            if not result.get("segments"):
                self.logger.warning("No transcription segments found")
                return None
            
            self.logger.info(f"Transcribed {len(result['segments'])} segments")
            
            # Step 2: 对齐到预期文本
            self.logger.info("Performing forced alignment...")
            result = whisperx.align(
                result["segments"], 
                self._align_model, 
                self._metadata, 
                audio, 
                device, 
                return_char_alignments=self.whisper_config['return_char_alignments']
            )
            
            # Step 3: 转换为我们的数据结构
            segments = []
            for segment in result["segments"]:
                words = []
                if "words" in segment:
                    for word_info in segment["words"]:
                        if all(key in word_info for key in ['word', 'start', 'end', 'score']):
                            alignment = WhisperAlignment(
                                word=word_info['word'],
                                start=float(word_info['start']),
                                end=float(word_info['end']),
                                score=float(word_info['score'])
                            )
                            words.append(alignment)
                
                whisper_segment = WhisperSegment(
                    text=segment.get('text', '').strip(),
                    start=float(segment.get('start', 0)),
                    end=float(segment.get('end', 0)),
                    words=words
                )
                segments.append(whisper_segment)
            
            self.logger.info(f"Successfully aligned {len(segments)} segments with word-level timestamps")
            
            # 清理GPU内存
            if device == "cuda":
                torch.cuda.empty_cache()
                gc.collect()
            
            return segments
            
        except Exception as e:
            self.logger.error(f"WhisperX alignment failed: {e}")
            return None
    
    def create_precise_subtitles(self, segments: List[WhisperSegment], 
                               max_chars_per_subtitle: int = 12,
                               max_duration_per_subtitle: float = 3.0) -> List[Dict[str, Any]]:
        """
        基于WhisperX对齐结果创建精确字幕
        
        Args:
            segments: WhisperX对齐结果
            max_chars_per_subtitle: 每条字幕最大字符数
            max_duration_per_subtitle: 每条字幕最大持续时间
        
        Returns:
            List[Dict]: 字幕列表，包含text, start, end, duration
        """
        if not segments:
            return []
        
        subtitles = []
        current_subtitle_words = []
        current_char_count = 0
        
        for segment in segments:
            for word in segment.words:
                word_text = word.word.strip()
                if not word_text:
                    continue
                
                # 检查是否需要开始新字幕
                if (current_char_count + len(word_text) > max_chars_per_subtitle or
                    (current_subtitle_words and 
                     word.end - current_subtitle_words[0].start > max_duration_per_subtitle)):
                    
                    # 完成当前字幕
                    if current_subtitle_words:
                        subtitle = self._create_subtitle_from_words(current_subtitle_words)
                        if subtitle:
                            subtitles.append(subtitle)
                    
                    # 开始新字幕
                    current_subtitle_words = [word]
                    current_char_count = len(word_text)
                else:
                    # 添加到当前字幕
                    current_subtitle_words.append(word)
                    current_char_count += len(word_text)
        
        # 处理最后一组词
        if current_subtitle_words:
            subtitle = self._create_subtitle_from_words(current_subtitle_words)
            if subtitle:
                subtitles.append(subtitle)
        
        self.logger.info(f"Created {len(subtitles)} precise subtitles from WhisperX alignment")
        return subtitles
    
    def _create_subtitle_from_words(self, words: List[WhisperAlignment]) -> Optional[Dict[str, Any]]:
        """从词列表创建单个字幕"""
        if not words:
            return None
        
        text = ''.join(word.word for word in words).strip()
        if not text:
            return None
        
        start_time = words[0].start
        end_time = words[-1].end
        duration = end_time - start_time
        
        # 计算平均置信度
        avg_score = sum(word.score for word in words) / len(words)
        
        return {
            'text': text,
            'start': start_time,
            'end': end_time,
            'duration': duration,
            'confidence': avg_score,
            'word_count': len(words)
        }
    
    def save_alignment_debug_info(self, segments: List[WhisperSegment], 
                                 output_path: str) -> bool:
        """保存对齐调试信息"""
        try:
            debug_info = {
                'segments': [],
                'total_segments': len(segments),
                'total_duration': segments[-1].end if segments else 0
            }
            
            for i, segment in enumerate(segments):
                segment_info = {
                    'index': i,
                    'text': segment.text,
                    'start': segment.start,
                    'end': segment.end,
                    'duration': segment.end - segment.start,
                    'words': []
                }
                
                for word in segment.words:
                    word_info = {
                        'word': word.word,
                        'start': word.start,
                        'end': word.end,
                        'duration': word.end - word.start,
                        'score': word.score
                    }
                    segment_info['words'].append(word_info)
                
                debug_info['segments'].append(segment_info)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(debug_info, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Saved WhisperX alignment debug info: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save alignment debug info: {e}")
            return False
    
    def cleanup_models(self):
        """清理模型缓存"""
        self._whisper_model = None
        self._align_model = None
        self._metadata = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        
        self.logger.info("WhisperX models cleaned up")
    
    def __str__(self) -> str:
        return f"WhisperXAligner(model={self.whisper_config['model_size']}, device={self._get_device()})"