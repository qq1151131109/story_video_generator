#!/usr/bin/env python3
"""
快速测试字幕分割优化效果
"""
import sys
sys.path.append('/home/shenglin/Desktop/story_video_generator')

from utils.subtitle_utils import SubtitleUtils

def test_quick_subtitle_split():
    """快速测试字幕分割"""
    print("⚡ 快速字幕分割测试")
    print("=" * 50)
    
    # 测试超长文本
    test_cases = [
        "你是万历年的新科进士，初授浙江钱塘县令，辖区豪绅垄断漕运，上级知府暗中索贿",
        "才到任三天，师爷就递来账本，低声说郭尚书家三公子强占民田，苦主悬梁自尽",
        "跪在公堂哭喊青天大老爷逼民女诬陷良商"
    ]
    
    # 新配置
    max_chars = 8  # 更严格的字符限制
    max_pixel_width = 580
    font_size = 48
    
    for i, text in enumerate(test_cases, 1):
        print(f"测试{i}: {text}")
        print(f"原长度: {len(text)}字符")
        
        # 使用新算法分割
        result = SubtitleUtils._split_chinese_text_advanced(
            text, max_chars, max_pixel_width, font_size, True
        )
        
        print(f"分割为{len(result)}行:")
        total_width = 0
        for j, line in enumerate(result, 1):
            pixel_width = SubtitleUtils.calculate_pixel_width(line, font_size)
            total_width += pixel_width
            status = "✅" if pixel_width <= max_pixel_width else "❌"
            print(f"  {j}: {line} | {len(line)}字 | {pixel_width}px {status}")
        
        print(f"平均宽度: {total_width/len(result) if result else 0:.0f}px")
        print()

if __name__ == "__main__":
    test_quick_subtitle_split()