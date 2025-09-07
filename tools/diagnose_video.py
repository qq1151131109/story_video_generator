#!/usr/bin/env python3
"""
视频诊断工具 - 诊断黑屏问题和视频质量问题
"""
import sys
import json
from pathlib import Path
import subprocess

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def analyze_video(video_path):
    """分析视频文件"""
    if not Path(video_path).exists():
        return {"error": f"视频文件不存在: {video_path}"}
    
    try:
        # 使用ffprobe获取视频信息
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-show_format', str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"error": f"FFprobe failed: {result.stderr}"}
        
        data = json.loads(result.stdout)
        
        video_stream = None
        audio_stream = None
        
        for stream in data['streams']:
            if stream['codec_type'] == 'video':
                video_stream = stream
            elif stream['codec_type'] == 'audio':
                audio_stream = stream
        
        analysis = {
            "file_path": video_path,
            "file_size_mb": round(int(data['format']['size']) / 1024 / 1024, 2),
            "duration": float(data['format']['duration']),
            "format": data['format']['format_name'],
            "has_video": video_stream is not None,
            "has_audio": audio_stream is not None
        }
        
        if video_stream:
            analysis.update({
                "video_codec": video_stream['codec_name'],
                "resolution": f"{video_stream['width']}x{video_stream['height']}",
                "fps": eval(video_stream['r_frame_rate']),
                "bitrate": int(video_stream.get('bit_rate', 0)),
                "frame_count": int(video_stream.get('nb_frames', 0))
            })
        
        if audio_stream:
            analysis.update({
                "audio_codec": audio_stream['codec_name'],
                "sample_rate": int(audio_stream['sample_rate']),
                "audio_bitrate": int(audio_stream.get('bit_rate', 0))
            })
        
        return analysis
        
    except Exception as e:
        return {"error": f"分析失败: {str(e)}"}

def detect_black_frames(video_path, threshold=0.98, min_duration=1.0):
    """检测黑屏帧"""
    try:
        cmd = [
            'ffmpeg', '-i', str(video_path), 
            '-vf', f'blackdetect=d={min_duration}:pic_th={threshold}',
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        black_periods = []
        for line in result.stderr.split('\n'):
            if 'blackdetect' in line and 'black_start' in line:
                parts = line.split()
                start = None
                end = None
                duration = None
                
                for part in parts:
                    if part.startswith('black_start:'):
                        start = float(part.split(':')[1])
                    elif part.startswith('black_end:'):
                        end = float(part.split(':')[1])
                    elif part.startswith('black_duration:'):
                        duration = float(part.split(':')[1])
                
                if start is not None and duration is not None:
                    black_periods.append({
                        "start": start,
                        "end": end or (start + duration),
                        "duration": duration
                    })
        
        return black_periods
        
    except Exception as e:
        return {"error": f"黑屏检测失败: {str(e)}"}

def diagnose_video_issues(video_path):
    """综合诊断视频问题"""
    print(f"🔍 分析视频文件: {video_path}")
    print("=" * 60)
    
    # 基础分析
    analysis = analyze_video(video_path)
    if "error" in analysis:
        print(f"❌ 分析失败: {analysis['error']}")
        return
    
    # 显示基础信息
    print(f"📁 文件大小: {analysis['file_size_mb']} MB")
    print(f"⏱️  总时长: {analysis['duration']:.1f} 秒")
    print(f"🎬 分辨率: {analysis.get('resolution', 'N/A')}")
    print(f"🎞️  帧率: {analysis.get('fps', 'N/A')} fps")
    print(f"🎥 视频编码: {analysis.get('video_codec', 'N/A')}")
    print(f"🎵 音频编码: {analysis.get('audio_codec', 'N/A')}")
    print(f"📊 视频比特率: {analysis.get('bitrate', 0)} bps")
    
    # 质量判断
    issues = []
    recommendations = []
    
    # 检查文件大小异常
    expected_size = analysis['duration'] * 0.5  # 预期每秒0.5MB
    if analysis['file_size_mb'] < expected_size * 0.3:
        issues.append("文件太小，可能是低质量或黑屏视频")
        
    if analysis['file_size_mb'] > expected_size * 3:
        issues.append("文件过大，可能编码效率低")
    
    # 检查比特率
    if analysis.get('bitrate', 0) < 1000:
        issues.append("视频比特率过低，可能影响画质")
    
    # 黑屏检测
    print("\n🖤 黑屏检测中...")
    black_periods = detect_black_frames(video_path)
    
    if isinstance(black_periods, dict) and "error" in black_periods:
        print(f"⚠️  黑屏检测失败: {black_periods['error']}")
    elif black_periods:
        print(f"❌ 发现 {len(black_periods)} 个黑屏片段:")
        total_black_duration = 0
        for i, period in enumerate(black_periods):
            print(f"   片段{i+1}: {period['start']:.1f}s - {period['end']:.1f}s (时长: {period['duration']:.1f}s)")
            total_black_duration += period['duration']
        
        black_percentage = (total_black_duration / analysis['duration']) * 100
        print(f"📊 黑屏占比: {black_percentage:.1f}%")
        
        if black_percentage > 50:
            issues.append("视频主要为黑屏内容")
        elif black_percentage > 20:
            issues.append("视频包含较多黑屏片段")
    else:
        print("✅ 未发现明显黑屏问题")
    
    # 总结诊断结果
    print("\n" + "=" * 60)
    if issues:
        print("⚠️  发现的问题:")
        for issue in issues:
            print(f"   • {issue}")
    else:
        print("✅ 视频质量正常")
    
    if recommendations:
        print("\n💡 建议:")
        for rec in recommendations:
            print(f"   • {rec}")
    
    return analysis, black_periods, issues

def main():
    if len(sys.argv) < 2:
        print("""
🔍 视频诊断工具

用法:
    python tools/diagnose_video.py <视频文件路径>
    python tools/diagnose_video.py latest  # 分析最新生成的视频

示例:
    python tools/diagnose_video.py output/videos/story_video_xxx.mp4
    python tools/diagnose_video.py latest
        """)
        return
    
    video_path = sys.argv[1]
    
    if video_path == "latest":
        # 找到最新的视频文件
        video_dir = Path("output/videos")
        if not video_dir.exists():
            print("❌ 输出目录不存在")
            return
        
        video_files = list(video_dir.glob("story_video_*.mp4"))
        if not video_files:
            print("❌ 未找到生成的视频文件")
            return
        
        # 按修改时间排序，取最新的
        video_path = max(video_files, key=lambda p: p.stat().st_mtime)
        print(f"🎯 分析最新视频: {video_path.name}")
    
    diagnose_video_issues(video_path)

if __name__ == "__main__":
    main()