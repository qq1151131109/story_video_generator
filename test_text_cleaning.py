#!/usr/bin/env python3
"""
测试文本清理函数
"""
import re

def test_clean_text_for_ffmpeg(text: str) -> str:
    """测试版本的文本清理函数"""
    print(f"原始文本: {repr(text)}")
    
    # 先统一换行符格式，处理字面量\n符号
    text = text.replace('\\n', '\n')     # 将字面量\n转换为实际换行符
    print(f"处理\\n后: {repr(text)}")
    
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    print(f"统一换行符后: {repr(text)}")
    
    # 清理特殊符号但保留基本中文标点和换行符
    cleaned = re.sub(r'[^\w\s\u4e00-\u9fff，。！？、；：""''（）\n]', '', text)
    print(f"正则清理后: {repr(cleaned)}")
    
    result = cleaned.strip()
    print(f"去空格后: {repr(result)}")
    
    return result

# 测试用例
test_cases = [
    "火焰腾起时你瞥见韩国间谍惨白的脸",
    "汉朝边陲，一封密函竟能颠覆帝国，你，是大汉西域都护府的译官",
    "粮草营莫名起火，焦臭弥漫",
    "守粮校尉横死帐中，胸口插着匈奴短刀",
    "这里有一个\\n换行符",
    "特殊符号测试: <>[]{}|\\@#$%^&*"
]

for i, test_text in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"测试 {i}: {test_text}")
    print('='*60)
    result = test_clean_text_for_ffmpeg(test_text)
    print(f"最终结果: {repr(result)}")
    
    # 检查是否有字符丢失
    original_chars = set(test_text)
    result_chars = set(result)
    lost_chars = original_chars - result_chars
    if lost_chars:
        print(f"丢失的字符: {lost_chars}")