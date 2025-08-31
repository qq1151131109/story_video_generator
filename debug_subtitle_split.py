#!/usr/bin/env python3
"""
调试字幕分割问题 - 重现"惨n白"bug
"""
import re

def debug_split_chinese_text(text: str, max_length: int = 25) -> list:
    """调试版本的中文文本分割函数"""
    print(f"原始文本: {repr(text)}")
    print(f"原始文本长度: {len(text)}")
    print(f"最大长度限制: {max_length}")
    print("=" * 50)
    
    # 优先按标点符号分割
    sentences = re.split(r'[。！？；]', text)
    print(f"按句号分割结果: {sentences}")
    
    lines = []
    
    for i, sentence in enumerate(sentences):
        print(f"\n处理句子 {i+1}: {repr(sentence)}")
        sentence = sentence.strip()
        print(f"去空格后: {repr(sentence)}")
        
        if not sentence:
            print("空句子，跳过")
            continue
            
        # 如果句子长度在限制内，直接添加
        if len(sentence) <= max_length:
            print(f"句子长度{len(sentence)}<=限制{max_length}，直接添加")
            lines.append(sentence)
        else:
            print(f"句子长度{len(sentence)}>{max_length}，需要进一步分割")
            # 按逗号分割
            parts = re.split(r'[，、]', sentence)
            print(f"按逗号分割结果: {parts}")
            
            current_line = ""
            
            for j, part in enumerate(parts):
                print(f"  处理部分 {j+1}: {repr(part)}")
                part = part.strip()
                print(f"  去空格后: {repr(part)}")
                
                if not part:
                    print("  空部分，跳过")
                    continue
                    
                test_line = current_line + part
                print(f"  测试合并: {repr(test_line)} (长度{len(test_line)})")
                
                if len(test_line) <= max_length:
                    current_line = test_line
                    print(f"  合并成功: {repr(current_line)}")
                else:
                    if current_line:
                        print(f"  当前行满了，添加: {repr(current_line)}")
                        lines.append(current_line)
                    current_line = part
                    print(f"  开始新行: {repr(current_line)}")
            
            if current_line:
                print(f"  最终添加: {repr(current_line)}")
                lines.append(current_line)
    
    print("\n" + "=" * 50)
    print("最终分割结果:")
    for i, line in enumerate(lines):
        print(f"{i+1}: {repr(line)} (长度: {len(line)})")
    
    return [line for line in lines if line.strip()]

# 测试用例
if __name__ == "__main__":
    # 测试问题字符串
    test_texts = [
        "火焰腾起时你看见韩国间谍惨白的脸色",
        "汉朝边陲一封密函竟能颠覆帝国你是大汉西域都护府的译官",
        "都护将军冷汗浸透犀甲他瞥向你"
    ]
    
    for text in test_texts:
        print(f"\n{'='*60}")
        print(f"测试文本: {text}")
        print('='*60)
        result = debug_split_chinese_text(text)
        print(f"\n输出: {result}")
        print("\n")