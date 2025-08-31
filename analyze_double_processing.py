#!/usr/bin/env python3
"""
分析双重文本处理问题
"""

# 第一层: SceneSplitter输出的场景content
scene_contents = [
    "你是万历年的新科进士，初授浙江钱塘县令，辖区豪绅垄断漕运，上级知府暗中索贿。",  # 场景1: 32字符
    "才到任三天，师爷就递来账本，低声说"郭尚书家三公子强占民田，苦主悬梁自尽"。你拍案要查，当夜书房窗棂突然射进一支毒箭，钉着血书"多管闲事者曝尸运河"。",  # 场景2: 73字符 💥
    "次日清早，县仓储粮莫名发霉，鼠尸堆中飘出恶臭，衙役集体称病告假。更致命的是，苦主女儿突然翻供，跪在公堂哭喊"青天大老爷逼民女诬陷良商"。",  # 场景3: 69字符 💥
    "你当街焚烧假账本，火光照亮百姓惊惶的脸。暗中将尚书公子的密信抄送其政敌，借浙党清流之势施压。",  # 场景4: 49字符 💥
    "最后亮出御赐密折权，直奏天子"漕运贪腐链涉皇商"。三日后缇骑破门而入，你以"欺君罪"被锁入诏狱。",  # 场景5: 46字符 💥
    "墙角血污沾湿囚衣，狱卒低声叹"郭尚书捐了三万两犒边"。断头台上，你看见百姓沿街焚香泣拜。",  # 场景6: 43字符 💥
    "这一刻你终于明白，\n皇权之下从无清官，\n只有棋子与弃子的残酷博弈。"  # 场景7: 27字符
]

print("🎬 第一层处理: SceneSplitter的场景分割")
print("=" * 60)
for i, content in enumerate(scene_contents, 1):
    length = len(content.replace('\n', ''))
    status = "🔴 超长" if length > 30 else "🟡 偏长" if length > 20 else "🟢 正常"
    print(f"场景{i}: {length}字符 {status}")
    print(f"  内容: {content[:40]}{'...' if len(content) > 40 else ''}")
    
    # 分析句子结构
    sentences = content.split('。')
    if len(sentences) > 2:
        print(f"  💥 包含{len(sentences)-1}个完整句子")
    print()

print("\n🔄 第二层处理: SubtitleAlignmentManager的智能分割")
print("=" * 60)

# 模拟SubtitleUtils.split_text_by_rules(text, 12, "zh")的处理
def simulate_subtitle_split(text, max_length=12):
    """模拟字幕分割"""
    import re
    
    # 优先按标点符号分割
    sentences = re.split(r'[。！？；]', text)
    lines = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
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

print("场景内容 → 字幕分割结果:")
total_subtitle_segments = 0

for i, content in enumerate(scene_contents, 1):
    print(f"\n场景{i} ({len(content)}字符):")
    print(f"原始: {content}")
    
    # 模拟字幕分割 (max_length=12对应当前配置)
    subtitle_lines = simulate_subtitle_split(content, 12)
    total_subtitle_segments += len(subtitle_lines)
    
    print(f"分割为{len(subtitle_lines)}个字幕段落:")
    for j, line in enumerate(subtitle_lines, 1):
        length = len(line)
        status = "🔴 超长" if length > 15 else "🟡 偏长" if length > 12 else "🟢 合适"
        print(f"  {i}-{j}: {length}字符 {status} | {line}")

print(f"\n📊 分割结果统计:")
print(f"原始场景数: {len(scene_contents)}")
print(f"最终字幕段数: {total_subtitle_segments}")
print(f"分割比例: {total_subtitle_segments/len(scene_contents):.1f}倍")

print("\n🔍 双重处理问题:")
print("1. SceneSplitter已经将长文案分为多个场景")
print("2. SubtitleAlignmentManager再次分割每个场景的内容")
print("3. 但场景分割还是太粗（平均49字符/场景）")
print("4. 导致字幕分割承担了过重的分割任务")

print("\n💡 优化思路:")
print("1. 改进SceneSplitter，让场景分割更细粒度")
print("2. 或者改进字幕分割算法，加强像素级控制")
print("3. 两者结合，形成层级化的文本分割体系")