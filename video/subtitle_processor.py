"""
字幕处理器 - 智能字幕分割和时间同步
对应原工作流的字幕配置和时间同步逻辑
"""
import re
import time
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import logging
from dataclasses import dataclass
import json

from core.config_manager import ConfigManager
from utils.file_manager import FileManager

@dataclass
class SubtitleSegment:
    """字幕片段"""
    text: str                    # 字幕文本
    start_time: float           # 开始时间（秒）
    end_time: float             # 结束时间（秒）
    duration: float             # 持续时间（秒）
    position: str = "bottom"    # 位置（bottom, top, center）
    style: str = "main"         # 样式（main, title）

@dataclass
class SubtitleRequest:
    """字幕处理请求"""
    text: str                   # 原始文本
    scene_duration: float       # 场景时长
    language: str              # 语言代码
    max_line_length: int = 25  # 最大行长度（对应原工作流）
    style: str = "main"        # 字幕样式

class SubtitleProcessor:
    """
    字幕处理器
    
    基于原工作流的字幕配置：
    - SUB_CONFIG.MAX_LINE_LENGTH: 25
    - 分割优先级：句号、感叹号、问号等
    - 支持多语言智能分割
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.video')
        
        # 获取字幕配置
        self.subtitle_config = config_manager.get('subtitle', {})
        
        # 分割优先级（对应原工作流）
        self.split_priority = self.subtitle_config.get('split_priority', [
            "。", "！", "？", "，", ",", "：", ":", "、", "；", ";", " "
        ])
        
        # 最大行长度
        self.max_line_length = self.subtitle_config.get('max_line_length', 25)
        
        # 字幕样式配置
        self._load_subtitle_styles()
        
        self.logger.info("Subtitle processor initialized")
    
    def _load_subtitle_styles(self):
        """加载字幕样式配置"""
        self.styles = {
            'main': {
                'font_size': self.subtitle_config.get('main_font_size', 7),
                'color': self.subtitle_config.get('main_color', '#FFFFFF'),
                'border_color': self.subtitle_config.get('main_border_color', '#000000'),
                'position': 'bottom',
                'font_family': 'Arial'
            },
            'title': {
                'font_size': self.subtitle_config.get('title_font_size', 40),
                'color': self.subtitle_config.get('title_color', '#000000'),
                'border_color': self.subtitle_config.get('title_border_color', '#ffffff'),
                'font_family': self.subtitle_config.get('title_font', '书南体'),
                'letter_spacing': self.subtitle_config.get('title_letter_spacing', 26),
                'position': 'center'
            }
        }
    
    def process_subtitle(self, request: SubtitleRequest) -> List[SubtitleSegment]:
        """
        处理字幕文本，生成字幕片段
        
        Args:
            request: 字幕处理请求
        
        Returns:
            List[SubtitleSegment]: 字幕片段列表
        """
        try:
            self.logger.info(f"Processing subtitle: {request.text[:50]}...")
            
            # 智能分割文本
            text_segments = self._split_text_intelligently(request.text, request.language)
            
            # 计算时间分配
            segments = self._assign_timing(text_segments, request.scene_duration)
            
            # 设置样式和位置
            for segment in segments:
                segment.style = request.style
                segment.position = self.styles[request.style]['position']
            
            self.logger.info(f"Generated {len(segments)} subtitle segments")
            
            return segments
            
        except Exception as e:
            self.logger.error(f"Subtitle processing failed: {e}")
            # 返回单个全文字幕作为备选
            return [SubtitleSegment(
                text=request.text,
                start_time=0.0,
                end_time=request.scene_duration,
                duration=request.scene_duration,
                position="bottom",
                style=request.style
            )]
    
    def _split_text_intelligently(self, text: str, language: str) -> List[str]:
        """
        智能分割文本
        
        Args:
            text: 原始文本
            language: 语言代码
        
        Returns:
            List[str]: 分割后的文本片段
        """
        if len(text) <= self.max_line_length:
            return [text]
        
        segments = []
        remaining_text = text.strip()
        
        while remaining_text:
            if len(remaining_text) <= self.max_line_length:
                segments.append(remaining_text)
                break
            
            # 尝试按优先级分割
            best_split_pos = -1
            best_split_char = ""
            
            # 在最大长度范围内寻找最佳分割点
            search_end = min(self.max_line_length, len(remaining_text))
            
            for i in range(search_end, 0, -1):
                char = remaining_text[i-1]
                if char in self.split_priority:
                    priority = self.split_priority.index(char)
                    if best_split_pos == -1 or priority < self.split_priority.index(best_split_char):
                        best_split_pos = i
                        best_split_char = char
            
            if best_split_pos > 0:
                # 找到了合适的分割点
                segment = remaining_text[:best_split_pos].strip()
                if segment:
                    segments.append(segment)
                remaining_text = remaining_text[best_split_pos:].strip()
            else:
                # 没有找到分割点，强制在最大长度处分割
                segment = remaining_text[:self.max_line_length].strip()
                segments.append(segment)
                remaining_text = remaining_text[self.max_line_length:].strip()
        
        return [seg for seg in segments if seg]
    
    def _assign_timing(self, text_segments: List[str], total_duration: float) -> List[SubtitleSegment]:
        """
        为文本片段分配时间
        
        Args:
            text_segments: 文本片段列表
            total_duration: 总时长
        
        Returns:
            List[SubtitleSegment]: 带时间信息的字幕片段
        """
        if not text_segments:
            return []
        
        segments = []
        
        # 计算每个片段的权重（基于文本长度）
        total_length = sum(len(segment) for segment in text_segments)
        
        current_time = 0.0
        
        for i, text in enumerate(text_segments):
            # 根据文本长度分配时间
            if total_length > 0:
                segment_duration = (len(text) / total_length) * total_duration
            else:
                segment_duration = total_duration / len(text_segments)
            
            # 确保最后一个片段准确结束
            if i == len(text_segments) - 1:
                end_time = total_duration
            else:
                end_time = current_time + segment_duration
            
            segment = SubtitleSegment(
                text=text,
                start_time=current_time,
                end_time=end_time,
                duration=end_time - current_time
            )
            
            segments.append(segment)
            current_time = end_time
        
        return segments
    
    def generate_srt(self, segments: List[SubtitleSegment]) -> str:
        """
        生成SRT格式字幕文件内容
        
        Args:
            segments: 字幕片段列表
        
        Returns:
            str: SRT格式内容
        """
        srt_content = []
        
        for i, segment in enumerate(segments, 1):
            # 时间格式：HH:MM:SS,mmm
            start_time = self._format_srt_time(segment.start_time)
            end_time = self._format_srt_time(segment.end_time)
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(segment.text)
            srt_content.append("")  # 空行分隔
        
        return '\n'.join(srt_content)
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化SRT时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def generate_ass(self, segments: List[SubtitleSegment]) -> str:
        """
        生成ASS格式字幕文件内容（支持样式）
        
        Args:
            segments: 字幕片段列表
        
        Returns:
            str: ASS格式内容
        """
        ass_header = """[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
Style: Title,Arial,40,&H00000000,&H000000FF,&H00FFFFFF,&H80000000,1,0,0,0,100,100,26,0,1,2,0,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        ass_content = [ass_header.strip()]
        
        for segment in segments:
            start_time = self._format_ass_time(segment.start_time)
            end_time = self._format_ass_time(segment.end_time)
            
            style_name = segment.style.capitalize()
            
            event = f"Dialogue: 0,{start_time},{end_time},{style_name},,0,0,0,,{segment.text}"
            ass_content.append(event)
        
        return '\n'.join(ass_content)
    
    def _format_ass_time(self, seconds: float) -> str:
        """格式化ASS时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        
        return f"{hours:01d}:{minutes:02d}:{secs:05.2f}"
    
    def generate_vtt(self, segments: List[SubtitleSegment]) -> str:
        """
        生成WebVTT格式字幕文件内容
        
        Args:
            segments: 字幕片段列表
        
        Returns:
            str: WebVTT格式内容
        """
        vtt_content = ["WEBVTT", ""]
        
        for i, segment in enumerate(segments, 1):
            start_time = self._format_vtt_time(segment.start_time)
            end_time = self._format_vtt_time(segment.end_time)
            
            vtt_content.append(f"{i}")
            vtt_content.append(f"{start_time} --> {end_time}")
            vtt_content.append(segment.text)
            vtt_content.append("")
        
        return '\n'.join(vtt_content)
    
    def _format_vtt_time(self, seconds: float) -> str:
        """格式化WebVTT时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
        else:
            return f"{minutes:02d}:{secs:06.3f}"
    
    def save_subtitle_file(self, segments: List[SubtitleSegment], 
                          output_path: str, format: str = "srt") -> str:
        """
        保存字幕文件
        
        Args:
            segments: 字幕片段列表
            output_path: 输出路径
            format: 字幕格式 (srt, ass, vtt)
        
        Returns:
            str: 保存的文件路径
        """
        try:
            if format.lower() == "srt":
                content = self.generate_srt(segments)
            elif format.lower() == "ass":
                content = self.generate_ass(segments)
            elif format.lower() == "vtt":
                content = self.generate_vtt(segments)
            else:
                raise ValueError(f"Unsupported subtitle format: {format}")
            
            # 确保文件扩展名正确
            output_path = Path(output_path)
            if output_path.suffix.lower() != f".{format.lower()}":
                output_path = output_path.with_suffix(f".{format.lower()}")
            
            success = self.file_manager.save_text(content, str(output_path))
            
            if success:
                self.logger.info(f"Saved {format.upper()} subtitle file: {output_path}")
                return str(output_path)
            else:
                raise Exception(f"Failed to save subtitle file: {output_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to save subtitle file: {e}")
            raise
    
    def batch_process_subtitles(self, requests: List[SubtitleRequest]) -> List[List[SubtitleSegment]]:
        """
        批量处理字幕
        
        Args:
            requests: 字幕处理请求列表
        
        Returns:
            List[List[SubtitleSegment]]: 字幕片段列表的列表
        """
        self.logger.info(f"Batch processing {len(requests)} subtitle requests")
        
        results = []
        
        for i, request in enumerate(requests):
            try:
                segments = self.process_subtitle(request)
                results.append(segments)
            except Exception as e:
                self.logger.error(f"Batch subtitle processing failed for request {i}: {e}")
                # 添加备选字幕
                results.append([SubtitleSegment(
                    text=request.text,
                    start_time=0.0,
                    end_time=request.scene_duration,
                    duration=request.scene_duration
                )])
        
        return results
    
    def get_subtitle_stats(self, segments: List[SubtitleSegment]) -> Dict[str, Any]:
        """获取字幕统计信息"""
        if not segments:
            return {}
        
        total_chars = sum(len(segment.text) for segment in segments)
        total_duration = max(segment.end_time for segment in segments)
        
        return {
            'segment_count': len(segments),
            'total_characters': total_chars,
            'total_duration': total_duration,
            'avg_chars_per_segment': total_chars / len(segments),
            'avg_duration_per_segment': total_duration / len(segments),
            'chars_per_second': total_chars / total_duration if total_duration > 0 else 0
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"SubtitleProcessor(max_line_length={self.max_line_length})"