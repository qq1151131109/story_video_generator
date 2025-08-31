#!/usr/bin/env python3
"""
测试字幕优化系统
"""
import sys
sys.path.append('/home/shenglin/Desktop/story_video_generator')

from utils.subtitle_utils import SubtitleUtils

def test_subtitle_split():
    """测试新的字幕分割算法"""
    print("🧪 测试新字幕分割算法")
    print("=" * 60)
    
    # 测试文本（之前超长的字幕段落）
    test_texts = [
        "初授浙江钱塘县令辖区豪绅垄断漕运",  # 16字符
        "鼠尸堆中飘出恶臭衙役集体称病告假",  # 16字符
        "跪在公堂哭喊青天大老爷逼民女诬陷良商",  # 20字符
        "狱卒低声叹郭尚书捐了三万两犒边",  # 17字符
        "断头台上，你看见百姓沿街焚香泣拜"   # 16字符
    ]
    
    # 新配置参数
    max_chars = 10
    max_pixel_width = 580
    font_size = 48
    enable_pixel_validation = True
    
    for i, text in enumerate(test_texts, 1):
        print(f"测试{i}: {text} ({len(text)}字符)")
        
        # 旧算法
        old_result = SubtitleUtils._split_chinese_text(text, 12)
        print(f"  旧算法: {old_result}")
        
        # 新算法
        new_result = SubtitleUtils._split_chinese_text_advanced(
            text, max_chars, max_pixel_width, font_size, enable_pixel_validation
        )
        print(f"  新算法: {new_result}")
        
        # 验证像素宽度
        for j, line in enumerate(new_result):
            pixel_width = SubtitleUtils.calculate_pixel_width(line, font_size)
            status = "✅" if pixel_width <= max_pixel_width else "❌"
            print(f"    {j+1}: {line} | {len(line)}字符 | {pixel_width}px {status}")
        
        print()

if __name__ == "__main__":
    test_subtitle_split()