#!/usr/bin/env python3
"""
字体配置管理器 - 管理Google Fonts开源字体
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.font_manager import FontManager

class FontSetupTool:
    """字体配置管理工具"""
    
    def __init__(self):
        self.config = ConfigManager()
        self.files = FileManager()
        self.font_manager = FontManager(self.config, self.files)
    
    def show_status(self):
        """显示字体状态"""
        print("📚 Google Fonts开源字体库状态:")
        print("=" * 50)
        print(self.font_manager.get_font_info())
        print("=" * 50)
    
    async def download_fonts(self):
        """下载所有推荐字体"""
        print("🔄 开始下载Google Fonts开源字体库...")
        try:
            await self.font_manager.download_all_fonts()
            print("✅ 字体下载完成!")
        except Exception as e:
            print(f"❌ 字体下载失败: {e}")
    
    async def test_font_config(self, language="zh"):
        """测试字体配置"""
        print(f"🧪 测试字体配置 (语言: {language})...")
        
        try:
            # 测试不同风格的字体
            styles = ["sans", "serif", "handwriting"]
            
            for style in styles:
                print(f"\n测试风格: {style}")
                font_path = await self.font_manager.ensure_font_available(language, style)
                print(f"  字体路径: {font_path}")
                
                font_config = self.font_manager.get_ffmpeg_font_config(language, style)
                print(f"  FFmpeg配置: {font_config}")
                
                if os.path.exists(font_config['fontfile']):
                    print("  ✅ 字体文件存在")
                else:
                    print("  ⚠️  字体文件不存在，将使用系统fallback")
                    
        except Exception as e:
            print(f"❌ 字体配置测试失败: {e}")
    
    def clean_fonts(self):
        """清理字体缓存"""
        fonts_dir = self.font_manager.fonts_dir
        if fonts_dir.exists():
            import shutil
            shutil.rmtree(fonts_dir)
            print(f"🧹 已清理字体缓存目录: {fonts_dir}")
        else:
            print("📂 字体缓存目录不存在")
    
    def show_recommendations(self):
        """显示字体推荐配置"""
        print("""
🎨 Google Fonts开源字体推荐配置:

1. 思源黑体 (Noto Sans SC) - 推荐 ⭐⭐⭐⭐⭐
   • 用途: 中文无衬线字体，适合现代视频字幕
   • 特点: 清晰易读，支持简体中文、英文、数字
   • 授权: Google开源，完全免费商用
   • 替代: 微软雅黑（需商业授权）

2. 思源宋体 (Noto Serif SC) - 推荐 ⭐⭐⭐⭐
   • 用途: 中文衬线字体，适合正式、传统内容
   • 特点: 传统韵味，适合历史文化类视频
   • 授权: Google开源，完全免费商用

3. 龙藏体 (Long Cang) - 推荐 ⭐⭐⭐
   • 用途: 中文毛笔字体，适合艺术创意内容
   • 特点: 手写风格，独特视觉效果
   • 授权: Google开源，完全免费商用

💡 使用建议:
- 一般视频使用思源黑体
- 历史文化内容使用思源宋体
- 艺术创意内容使用龙藏体
- 所有字体都支持中英文混合显示
        """)

async def main():
    """主函数"""
    tool = FontSetupTool()
    
    if len(sys.argv) < 2:
        print("""
🔧 字体配置管理器 - Google Fonts开源字体

用法:
    python tools/font_setup.py <命令> [选项]

命令:
    status              - 显示字体状态
    download            - 下载所有字体
    test [language]     - 测试字体配置 (默认中文)
    clean               - 清理字体缓存
    recommend          - 显示字体推荐

示例:
    python tools/font_setup.py status
    python tools/font_setup.py download
    python tools/font_setup.py test zh
    python tools/font_setup.py test en
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        tool.show_status()
    
    elif command == "download":
        await tool.download_fonts()
        tool.show_status()
    
    elif command == "test":
        language = sys.argv[2] if len(sys.argv) > 2 else "zh"
        await tool.test_font_config(language)
    
    elif command == "clean":
        tool.clean_fonts()
        print("✅ 字体缓存已清理")
    
    elif command == "recommend":
        tool.show_recommendations()
    
    else:
        print(f"❌ 未知命令: {command}")
        print("使用 'python tools/font_setup.py' 查看帮助")

if __name__ == "__main__":
    asyncio.run(main())