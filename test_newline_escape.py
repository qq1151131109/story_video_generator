#!/usr/bin/env python3
"""
测试换行符转义问题
"""

def test_newline_escape():
    """测试换行符转义"""
    
    # 模拟剪映渲染器的处理过程
    lines = ["火焰腾起时你瞥见", "韩国间谍惨白的脸"]
    
    print("原始分行结果:")
    for i, line in enumerate(lines):
        print(f"  {i+1}: {repr(line)}")
    
    print("\n测试不同的连接方式:")
    
    # 方式1: 使用\\n（双反斜杠）
    display_text1 = '\\n'.join(lines)
    print(f"1. '\\\\n'.join(): {repr(display_text1)}")
    
    # 方式2: 使用\n（单反斜杠）  
    display_text2 = '\n'.join(lines)
    print(f"2. '\\n'.join(): {repr(display_text2)}")
    
    # 方式3: 直接字符串拼接
    display_text3 = lines[0] + "\\n" + lines[1]
    print(f"3. 直接拼接\\\\n: {repr(display_text3)}")
    
    print("\nFFmpeg中转义处理:")
    
    # 模拟FFmpeg转义处理
    for i, text in enumerate([display_text1, display_text2, display_text3], 1):
        print(f"\n方式{i}的转义处理:")
        print(f"  原始: {repr(text)}")
        
        # FFmpeg特殊字符转义
        escaped = text.replace("'", "\\'").replace(":", "\\:")
        print(f"  转义': {repr(escaped)}")
        
        # 在FFmpeg中实际显示的内容分析
        if '\\n' in escaped:
            print(f"  ⚠️  包含字面量\\\\n，可能显示为文字'n'")
        if '\n' in escaped:
            print(f"  ✅ 包含真实换行符，正常换行")

test_newline_escape()

print("\n" + "="*60)
print("问题分析:")
print("如果剪映渲染器使用 '\\\\n'.join(lines)，")
print("那么 ['惨', '白'] 会变成 '惨\\\\n白'")  
print("在FFmpeg中可能被渲染为 '惨n白'（显示为字面量n）")