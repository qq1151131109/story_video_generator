"""
字幕工具类 - 统一的字幕处理工具
解决多个字幕处理器中的重复代码问题
"""
import re
import os
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont


class SubtitleUtils:
    """统一的字幕处理工具类"""
    
    # 字体缓存
    _font_cache = {}
    _default_font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/mnt/c/Windows/Fonts/msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc"
    ]
    
    @staticmethod
    def calculate_pixel_width(text: str, font_size: int = 48, border_width: int = 3) -> int:
        """
        计算文本的真实像素宽度
        
        Args:
            text: 要测量的文本
            font_size: 字体大小
            border_width: 边框宽度
            
        Returns:
            int: 文本的像素宽度
        """
        try:
            # 获取字体
            font = SubtitleUtils._get_font(font_size)
            if not font:
                # fallback: 中文字符按字体大小估算
                return len(text) * font_size + border_width * 2
            
            # 创建临时图像测量文本
            dummy_img = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(dummy_img)
            
            # 获取文本边界框
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            
            # 加上边框宽度
            total_width = text_width + border_width * 2
            
            return total_width
            
        except Exception as e:
            # fallback到简单估算
            return len(text) * int(font_size * 0.8) + border_width * 2
    
    @staticmethod
    def _get_font(font_size: int) -> Optional[ImageFont.FreeTypeFont]:
        """
        获取字体对象，带缓存
        
        Args:
            font_size: 字体大小
            
        Returns:
            ImageFont.FreeTypeFont: 字体对象或None
        """
        cache_key = font_size
        if cache_key in SubtitleUtils._font_cache:
            return SubtitleUtils._font_cache[cache_key]
        
        # 查找可用字体
        for font_path in SubtitleUtils._default_font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    SubtitleUtils._font_cache[cache_key] = font
                    return font
                except Exception:
                    continue
        
        # 如果没有找到字体，缓存None
        SubtitleUtils._font_cache[cache_key] = None
        return None
    
    @staticmethod
    def format_srt_time(seconds: float) -> str:
        """
        将秒数格式化为SRT时间格式
        
        Args:
            seconds: 时间秒数
            
        Returns:
            str: SRT格式时间字符串 (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    @staticmethod
    def format_ass_time(seconds: float) -> str:
        """
        将秒数格式化为ASS时间格式
        
        Args:
            seconds: 时间秒数
            
        Returns:
            str: ASS格式时间字符串 (H:MM:SS.cc)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    @staticmethod
    def format_vtt_time(seconds: float) -> str:
        """
        将秒数格式化为VTT时间格式
        
        Args:
            seconds: 时间秒数
            
        Returns:
            str: VTT格式时间字符串 (MM:SS.mmm)
        """
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:06.3f}"
    
    @staticmethod
    def split_text_by_rules(text: str, max_length: int, language: str, 
                           max_pixel_width: int = 640, font_size: int = 48, 
                           enable_pixel_validation: bool = True) -> List[str]:
        """
        统一的智能文本分割逻辑 - 升级版(像素级验证)
        
        Args:
            text: 要分割的文本
            max_length: 每行最大字符数(备用限制)
            language: 语言代码 (zh, en, es)
            max_pixel_width: 最大像素宽度
            font_size: 字体大小
            enable_pixel_validation: 是否启用像素级验证
            
        Returns:
            List[str]: 分割后的文本行列表
        """
        if not text.strip():
            return []
        
        # 语言特定的分割规则
        if language == "zh":
            return SubtitleUtils._split_chinese_text_advanced(
                text, max_length, max_pixel_width, font_size, enable_pixel_validation
            )
        elif language == "en":
            return SubtitleUtils._split_english_text(text, max_length)
        elif language == "es":
            return SubtitleUtils._split_spanish_text(text, max_length)
        else:
            # 默认使用中文规则
            return SubtitleUtils._split_chinese_text_advanced(
                text, max_length, max_pixel_width, font_size, enable_pixel_validation
            )
    
    @staticmethod 
    def _split_chinese_text_advanced(text: str, max_length: int, max_pixel_width: int, 
                                   font_size: int, enable_pixel_validation: bool) -> List[str]:
        """
        中文文本三层智能分割 - 升级版
        
        第一层: 按句号分割完整句子
        第二层: 按逗号分割长句
        第三层: 强制按像素宽度分割
        """
        if not text.strip():
            return []
        
        lines = []
        
        # 第一层: 按句号、逗号等标点分割 (短视频需要更短的字幕)
        sentences = re.split(r'[。！？；，、]', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 检查句子是否需要进一步分割
            if SubtitleUtils._text_fits_limits(sentence, max_length, max_pixel_width, 
                                             font_size, enable_pixel_validation):
                lines.append(sentence)
            else:
                # 第二层: 按逗号等弱标点分割
                comma_parts = re.split(r'[，、：:]', sentence)
                current_line = ""
                
                for part in comma_parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    # 尝试合并到当前行
                    test_line = current_line + part if not current_line else current_line + part
                    
                    if SubtitleUtils._text_fits_limits(test_line, max_length, max_pixel_width,
                                                     font_size, enable_pixel_validation):
                        current_line = test_line
                    else:
                        # 当前行已满，保存并开始新行
                        if current_line:
                            lines.append(current_line)
                        
                        # 检查单独的part是否还是太长
                        if not SubtitleUtils._text_fits_limits(part, max_length, max_pixel_width,
                                                             font_size, enable_pixel_validation):
                            # 第三层: 强制分割
                            forced_parts = SubtitleUtils._force_split_by_width(
                                part, max_length, max_pixel_width, font_size, enable_pixel_validation
                            )
                            lines.extend(forced_parts)
                            current_line = ""
                        else:
                            current_line = part
                
                if current_line:
                    lines.append(current_line)
        
        return [line for line in lines if line.strip()]
    
    @staticmethod
    def _text_fits_limits(text: str, max_length: int, max_pixel_width: int,
                         font_size: int, enable_pixel_validation: bool) -> bool:
        """检查文本是否符合长度和像素宽度限制"""
        # 字符数限制
        if len(text) > max_length:
            return False
        
        # 像素宽度限制
        if enable_pixel_validation:
            pixel_width = SubtitleUtils.calculate_pixel_width(text, font_size)
            if pixel_width > max_pixel_width:
                return False
        
        return True
    
    @staticmethod
    def _force_split_by_width(text: str, max_length: int, max_pixel_width: int,
                            font_size: int, enable_pixel_validation: bool) -> List[str]:
        """强制按宽度分割超长文本"""
        if not text:
            return []
        
        lines = []
        current_line = ""
        
        for char in text:
            test_line = current_line + char
            
            if SubtitleUtils._text_fits_limits(test_line, max_length, max_pixel_width,
                                             font_size, enable_pixel_validation):
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    @staticmethod
    def _split_chinese_text(text: str, max_length: int) -> List[str]:
        """中文文本智能分割 - 兼容版本"""
        # 优先按标点符号分割
        sentences = re.split(r'[。！？；]', text)
        lines = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 如果句子长度在限制内，直接添加
            if len(sentence) <= max_length:
                lines.append(sentence)
            else:
                # 按逗号分割
                parts = re.split(r'[，、]', sentence)
                current_line = ""
                
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                        
                    if len(current_line + part) <= max_length:
                        current_line += part
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = part
                
                if current_line:
                    lines.append(current_line)
        
        return [line for line in lines if line.strip()]
    
    @staticmethod
    def _split_english_text(text: str, max_length: int) -> List[str]:
        """英文文本智能分割"""
        # 按句子分割
        sentences = re.split(r'[.!?]', text)
        lines = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            words = sentence.split()
            current_line = ""
            
            for word in words:
                if len(current_line + " " + word) <= max_length:
                    current_line += (" " + word) if current_line else word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
        
        return [line for line in lines if line.strip()]
    
    @staticmethod
    def _split_spanish_text(text: str, max_length: int) -> List[str]:
        """西班牙文文本智能分割"""
        # 使用英文分割规则，但考虑西班牙语特殊标点
        sentences = re.split(r'[.!?¡¿]', text)
        lines = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            words = sentence.split()
            current_line = ""
            
            for word in words:
                if len(current_line + " " + word) <= max_length:
                    current_line += (" " + word) if current_line else word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
        
        return [line for line in lines if line.strip()]
    
    @staticmethod
    def calculate_text_timing(text_segments: List[str], total_duration: float) -> List[Tuple[str, float, float]]:
        """
        基于文本长度智能分配时间
        
        Args:
            text_segments: 文本段落列表
            total_duration: 总时长
            
        Returns:
            List[Tuple[str, float, float]]: (文本, 开始时间, 结束时间) 列表
        """
        if not text_segments:
            return []
        
        # 计算每段文本的相对权重（基于字符长度）
        total_chars = sum(len(segment) for segment in text_segments)
        if total_chars == 0:
            # 平均分配时间
            segment_duration = total_duration / len(text_segments)
            return [(segment, i * segment_duration, (i + 1) * segment_duration) 
                   for i, segment in enumerate(text_segments)]
        
        # 基于文本长度按比例分配时间
        timed_segments = []
        current_time = 0.0
        
        for segment in text_segments:
            char_weight = len(segment) / total_chars
            segment_duration = total_duration * char_weight
            
            # 确保最小时长（避免过短的字幕）
            segment_duration = max(segment_duration, 0.5)
            
            start_time = current_time
            end_time = current_time + segment_duration
            
            timed_segments.append((segment, start_time, end_time))
            current_time = end_time
        
        return timed_segments
    
    @staticmethod
    def validate_subtitle_timing(segments: List[Tuple[str, float, float]]) -> bool:
        """
        验证字幕时间序列的合法性
        
        Args:
            segments: (文本, 开始时间, 结束时间) 列表
            
        Returns:
            bool: 是否合法
        """
        if not segments:
            return True
        
        for i, (text, start, end) in enumerate(segments):
            # 检查单个段落时间合法性
            if start < 0 or end <= start:
                return False
            
            # 检查与前一个段落的时间关系
            if i > 0:
                prev_end = segments[i-1][2]
                if start < prev_end:
                    return False
        
        return True
    
    @staticmethod
    def optimize_subtitle_gaps(segments: List[Tuple[str, float, float]], 
                              min_gap: float = 0.1) -> List[Tuple[str, float, float]]:
        """
        优化字幕间隔，确保有足够的间隔时间
        
        Args:
            segments: 原始字幕段落
            min_gap: 最小间隔时间（秒）
            
        Returns:
            List[Tuple[str, float, float]]: 优化后的字幕段落
        """
        if not segments:
            return []
        
        optimized = []
        
        for i, (text, start, end) in enumerate(segments):
            # 第一个段落直接添加
            if i == 0:
                optimized.append((text, start, end))
                continue
            
            # 检查与前一个段落的间隔
            prev_end = optimized[i-1][2]
            if start - prev_end < min_gap:
                # 调整开始时间
                new_start = prev_end + min_gap
                new_end = max(new_start + (end - start), new_start + 0.5)
                optimized.append((text, new_start, new_end))
            else:
                optimized.append((text, start, end))
        
        return optimized