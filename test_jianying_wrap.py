#!/usr/bin/env python3
"""
测试剪映风格字幕的文本换行逻辑
"""
import sys
import re
sys.path.append('.')

def test_wrap_by_width(text: str, max_width: int = 400, max_lines: int = 2) -> list:
    """测试版本的宽度换行算法"""
    print(f"原始文本: {repr(text)}")
    print(f"最大宽度: {max_width}px, 最大行数: {max_lines}")
    print("-" * 50)
    
    lines = []
    current_text = text.strip()
    
    def mock_measure_text_width(text: str) -> int:
        """模拟文本宽度测量 - 假设每个中文字符50px"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return chinese_chars * 50 + other_chars * 30
    
    line_count = 0
    while current_text and line_count < max_lines:
        line_count += 1
        print(f"\n第{line_count}行处理:")
        print(f"  剩余文本: {repr(current_text)}")
        
        # 从最长可能的文本开始检查
        best_split = len(current_text)
        print(f"  开始二分查找，文本长度: {len(current_text)}")
        
        # 二分查找最佳分割点
        left, right = 0, len(current_text)
        
        while left < right:
            mid = (left + right + 1) // 2
            test_text = current_text[:mid]
            test_width = mock_measure_text_width(test_text)
            
            print(f"    二分[{left},{right}] mid={mid}: '{test_text}' 宽度={test_width}")
            
            if test_width <= max_width:
                left = mid
            else:
                right = mid - 1
        
        split_pos = left
        print(f"  二分查找结果: split_pos={split_pos}")
        
        # 在合适的标点处断句
        if split_pos < len(current_text):
            print(f"  在split_pos={split_pos}前查找标点...")
            # 在split_pos之前查找最近的标点
            for i in range(split_pos, max(0, split_pos - 8), -1):
                if current_text[i] in '。！？，、；： ':
                    print(f"    找到标点 '{current_text[i]}' 在位置 {i}")
                    split_pos = i + 1
                    break
        
        line_text = current_text[:split_pos].strip()
        print(f"  提取的行: {repr(line_text)}")
        
        if line_text:
            lines.append(line_text)
        
        current_text = current_text[split_pos:].strip()
        print(f"  剩余文本: {repr(current_text)}")
    
    # 如果还有剩余文本且已达到最大行数，加省略号
    if current_text and lines and len(lines) == max_lines:
        last_line = lines[-1]
        print(f"\n达到最大行数，处理省略号...")
        print(f"  最后一行: {repr(last_line)}")
        print(f"  剩余文本: {repr(current_text)}")
        
        if mock_measure_text_width(last_line + "...") <= max_width:
            lines[-1] = last_line + "..."
            print(f"  添加省略号: {repr(lines[-1])}")
        else:
            # 截断最后一行并添加省略号
            while last_line and mock_measure_text_width(last_line + "...") > max_width:
                print(f"    截断字符: {repr(last_line[-1])}")
                last_line = last_line[:-1]
            lines[-1] = last_line + "..."
            print(f"  截断后加省略号: {repr(lines[-1])}")
    
    print(f"\n最终结果: {lines}")
    return lines

# 测试用例
test_cases = [
    "火焰腾起时你瞥见韩国间谍惨白的脸色变得苍白如纸",
    "粮草营莫名起火焦臭弥漫守粮校尉横死帐中胸口插着匈奴短刀",
    "汉朝边陲一封密函竟能颠覆帝国你是大汉西域都护府的译官"
]

for i, text in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"测试案例 {i}")
    print('='*60)
    result = test_wrap_by_width(text)
    print(f"\n案例{i}结果: {result}")
    
    # 检查是否有问题字符
    for line in result:
        if 'n' in line and '惨' in line:
            print(f"❌ 发现问题行: {repr(line)}")
            print(f"字符详情: {[c for c in line]}")