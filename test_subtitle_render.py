#!/usr/bin/env python3
"""
测试字幕渲染过程，重现"惨n白"bug
"""
import tempfile
import subprocess
import os
from pathlib import Path

# 创建测试SRT文件
test_srt_content = """1
00:00:00,000 --> 00:00:03,000
火焰腾起时你瞥见韩国间谍惨白的脸

2  
00:00:03,000 --> 00:00:06,000
你感到一阵寒意袭来心中惨淡

"""

# 创建临时文件
with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
    f.write(test_srt_content)
    srt_file = f.name

print(f"创建的SRT文件: {srt_file}")
print("文件内容:")
with open(srt_file, 'r', encoding='utf-8') as f:
    content = f.read()
    print(content)
    print("字符详情:")
    for i, char in enumerate(content):
        if char in '惨白淡':
            print(f"位置 {i}: {repr(char)} ({ord(char)})")

# 创建一个简单的黑色视频用于测试
black_video = "/tmp/test_black.mp4"
cmd_black = [
    'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=720x1280:d=10',
    '-pix_fmt', 'yuv420p', black_video
]

print("\n创建测试视频...")
result = subprocess.run(cmd_black, capture_output=True, text=True)
if result.returncode != 0:
    print(f"创建测试视频失败: {result.stderr}")
    exit(1)

# 测试FFmpeg字幕渲染
output_video = "/tmp/test_with_subtitles.mp4"
font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

cmd_subtitle = [
    'ffmpeg', '-y',
    '-i', black_video,
    '-vf', f"subtitles='{srt_file}':force_style='FontName=NotoSansCJK,FontSize=48,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'",
    '-c:a', 'copy',
    '-t', '10',
    output_video
]

print(f"\n测试FFmpeg字幕渲染...")
print(f"命令: {' '.join(cmd_subtitle)}")
result = subprocess.run(cmd_subtitle, capture_output=True, text=True)

if result.returncode == 0:
    print(f"成功创建带字幕的视频: {output_video}")
    
    # 检查输出文件大小
    size = Path(output_video).stat().st_size
    print(f"视频大小: {size/1024/1024:.1f} MB")
    
    # 使用ffprobe分析字幕信息
    cmd_probe = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', output_video]
    probe_result = subprocess.run(cmd_probe, capture_output=True, text=True)
    if probe_result.returncode == 0:
        print("视频流信息获取成功")
        
else:
    print(f"FFmpeg渲染失败: {result.stderr}")

# 清理临时文件
os.unlink(srt_file)
if os.path.exists(black_video):
    os.unlink(black_video)

print(f"\n测试完成。如果问题存在，请检查视频: {output_video}")
print("可以使用视频播放器打开查看字幕是否正确显示")