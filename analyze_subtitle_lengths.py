#!/usr/bin/env python3
"""
分析字幕长度分布
"""
import re

# 从SRT文件内容分析
srt_content = """1
00:00:00,000 --> 00:00:02,070
你是万历年的新科进士

2
00:00:02,070 --> 00:00:05,383
初授浙江钱塘县令辖区豪绅垄断漕运

3
00:00:05,383 --> 00:00:07,040
上级知府暗中索贿

4
00:00:07,200 --> 00:00:09,574
才到任三天师爷就递来账本

5
00:00:09,574 --> 00:00:12,541
低声说"郭尚书家三公子强占民田

6
00:00:12,541 --> 00:00:13,926
苦主悬梁自尽"

7
00:00:14,076 --> 00:00:15,017
你拍案要查

8
00:00:15,017 --> 00:00:17,653
当夜书房窗棂突然射进一支毒箭

9
00:00:17,653 --> 00:00:20,477
钉着血书"多管闲事者曝尸运河"

10
00:00:20,628 --> 00:00:23,247
次日清早县仓储粮莫名发霉

11
00:00:23,247 --> 00:00:26,739
鼠尸堆中飘出恶臭衙役集体称病告假

12
00:00:26,891 --> 00:00:29,285
更致命的是苦主女儿突然翻供

13
00:00:29,285 --> 00:00:32,968
跪在公堂哭喊"青天大老爷逼民女诬陷良商"

14
00:00:33,119 --> 00:00:34,592
你当街焚烧假账本

15
00:00:34,592 --> 00:00:36,433
火光照亮百姓惊惶的脸

16
00:00:36,576 --> 00:00:39,357
暗中将尚书公子的密信抄送其政敌

17
00:00:39,357 --> 00:00:41,027
借浙党清流之势施压

18
00:00:41,183 --> 00:00:42,853
最后亮出御赐密折权

19
00:00:42,853 --> 00:00:45,449
直奏天子"漕运贪腐链涉皇商"

20
00:00:45,612 --> 00:00:47,609
三日后缇骑破门而入

21
00:00:47,609 --> 00:00:50,272
你以"欺君罪"被锁入诏狱

22
00:00:50,435 --> 00:00:51,949
墙角血污沾湿囚衣

23
00:00:51,949 --> 00:00:55,165
狱卒低声叹"郭尚书捐了三万两犒边"

24
00:00:55,332 --> 00:00:58,784
断头台上，你看见百姓沿街焚香泣拜

25
00:00:58,932 --> 00:01:00,817
这一刻你终于明白，

26
00:01:00,984 --> 00:01:03,078
皇权之下从无清官，

27
00:01:03,216 --> 00:01:05,705
只有棋子与弃子的残酷博弈"""

# 解析字幕文本
srt_pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)\n'
matches = re.findall(srt_pattern, srt_content, re.DOTALL)

print("=== 字幕长度分析 ===")
print(f"总字幕段落数: {len(matches)}")
print("-" * 60)

lengths = []
long_subtitles = []
very_long_subtitles = []

for i, match in enumerate(matches, 1):
    sequence, start_time, end_time, text = match
    text = text.strip()
    length = len(text)
    lengths.append(length)
    
    status = ""
    if length > 15:
        very_long_subtitles.append((i, text, length))
        status = "🔴 超长"
    elif length > 12:
        long_subtitles.append((i, text, length))
        status = "🟡 偏长"
    elif length > 8:
        status = "🟢 正常"
    else:
        status = "🔵 偏短"
    
    print(f"{i:2d}: {length:2d}字符 {status} | {text}")

print("\n" + "=" * 60)
print("📊 统计分析:")
print(f"平均长度: {sum(lengths)/len(lengths):.1f} 字符")
print(f"最大长度: {max(lengths)} 字符")
print(f"最小长度: {min(lengths)} 字符")

print(f"\n🟡 偏长字幕 (>12字符): {len(long_subtitles)}条")
for seq, text, length in long_subtitles:
    print(f"  #{seq}: {length}字符 - {text}")

print(f"\n🔴 超长字幕 (>15字符): {len(very_long_subtitles)}条")
for seq, text, length in very_long_subtitles:
    print(f"  #{seq}: {length}字符 - {text}")
    
    # 分析是否包含多句话
    sentence_count = len([p for p in text if p in '。！？'])
    comma_count = len([p for p in text if p in '，、'])
    if sentence_count > 0:
        print(f"    💥 包含{sentence_count}个句子结束符")
    if comma_count > 1:
        print(f"    💥 包含{comma_count}个逗号/顿号")
    print()

print("=" * 60)
print("🔍 问题分析:")
print("1. 存在多个超过15字符的字幕段落")
print("2. 部分字幕包含多个句子或短语")
print("3. 字幕分割粒度过粗，需要进一步细分")

# 估算像素宽度
print(f"\n📏 像素宽度估算 (字体48px):")
for seq, text, length in very_long_subtitles[:3]:  # 只分析前3个最长的
    estimated_width = length * 48  # 简单估算
    print(f"  #{seq}: {text}")
    print(f"    估算宽度: {estimated_width}px (超出640px限制)")