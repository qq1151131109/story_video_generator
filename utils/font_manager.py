"""
字体管理器 - 支持Google Fonts开源字体自动下载和管理
"""
import os
import asyncio
import logging
from typing import Dict, List, Optional
from pathlib import Path
import aiohttp
from core.config_manager import ConfigManager
from utils.file_manager import FileManager

class FontManager:
    """
    开源字体管理器
    
    支持功能：
    1. 自动下载Google Fonts开源字体
    2. 本地字体缓存管理
    3. 字体fallback机制
    4. FFmpeg字幕渲染字体配置
    """
    
    def __init__(self, config_manager: ConfigManager, file_manager: FileManager):
        self.config = config_manager
        self.files = file_manager
        self.logger = logging.getLogger('story_generator.font_manager')
        
        # 字体存储目录
        self.fonts_dir = Path("fonts")
        self.fonts_dir.mkdir(exist_ok=True)
        
        # Google Fonts开源字体配置 - 使用备用可靠源
        self.google_fonts = {
            "noto_sans_sc": {
                "name": "Noto Sans SC",
                "display_name": "思源黑体",
                "weights": ["Regular"],
                "urls": {
                    "Regular": "https://fonts.google.com/download?family=Noto%20Sans%20SC"
                },
                "fallback_urls": {
                    "Regular": "https://github.com/notofonts/noto-cjk/releases/download/Sans2.003/04_NotoSansCJKsc.zip"
                },
                "description": "Google与Adobe联合开发的免费商用中文字体"
            },
            "source_han_sans": {
                "name": "Source Han Sans",
                "display_name": "思源黑体(备用)",
                "weights": ["Regular"],
                "urls": {
                    # 使用可靠的CDN链接
                    "Regular": "https://cdn.jsdelivr.net/gh/adobe-fonts/source-han-sans@release/SubsetOTF/CN/SourceHanSansCN-Regular.otf"
                },
                "description": "Adobe版本的思源黑体，与Noto Sans CJK相同"
            },
            "noto_serif_sc": {
                "name": "Noto Serif SC",
                "display_name": "思源宋体", 
                "weights": ["Regular"],
                "urls": {
                    "Regular": "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf"
                },
                "description": "免费商用中文宋体"
            },
            "source_han_serif": {
                "name": "Source Han Serif",
                "display_name": "思源宋体(备用)",
                "weights": ["Regular"],  
                "urls": {
                    "Regular": "https://cdn.jsdelivr.net/gh/adobe-fonts/source-han-serif@release/SubsetOTF/CN/SourceHanSerifCN-Regular.otf"
                },
                "description": "Adobe版本的思源宋体"
            }
        }
        
        # 字体优先级配置
        self.font_priority = {
            "zh": ["source_han_sans", "noto_sans_sc", "source_han_serif", "noto_serif_sc"],
            "en": ["source_han_sans"],  # 思源黑体也支持英文
            "es": ["source_han_sans"]   # 同样支持西班牙文
        }
    
    async def ensure_font_available(self, language: str = "zh", style: str = "sans") -> str:
        """
        确保指定语言和风格的字体可用
        
        Args:
            language: 语言代码 (zh/en/es)
            style: 字体风格 (sans/serif/handwriting)
            
        Returns:
            字体文件路径
        """
        font_key = self._select_font_key(language, style)
        font_info = self.google_fonts[font_key]
        
        # 检查本地是否已有字体文件
        font_path = self._get_font_path(font_key, "Regular")
        if font_path.exists():
            self.logger.debug(f"使用缓存字体: {font_path}")
            return str(font_path)
        
        # 下载字体
        await self._download_font(font_key, "Regular")
        
        if font_path.exists():
            self.logger.info(f"✅ 字体准备就绪: {font_info['display_name']}")
            return str(font_path)
        else:
            # Fallback到系统字体
            return self._get_system_fallback_font(language)
    
    def _select_font_key(self, language: str, style: str) -> str:
        """选择最适合的字体"""
        priority_list = self.font_priority.get(language, self.font_priority["zh"])
        
        if style == "serif":
            # 优先选择宋体
            if "noto_serif_sc" in priority_list:
                return "noto_serif_sc"
        elif style == "handwriting":
            # 优先选择手写体
            if "long_cang" in priority_list:
                return "long_cang"
        
        # 默认使用黑体
        return priority_list[0]
    
    def _get_font_path(self, font_key: str, weight: str = "Regular") -> Path:
        """获取字体文件路径"""
        font_info = self.google_fonts[font_key]
        # 检查URL以确定文件扩展名
        url = font_info["urls"][weight]
        extension = ".otf" if url.endswith(".otf") else ".ttf"
        filename = f"{font_info['name'].replace(' ', '')}-{weight}{extension}"
        return self.fonts_dir / font_key / filename
    
    async def _download_font(self, font_key: str, weight: str = "Regular"):
        """下载指定字体"""
        font_info = self.google_fonts[font_key]
        url = font_info["urls"][weight]
        
        font_path = self._get_font_path(font_key, weight)
        font_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.logger.info(f"📥 正在下载字体: {font_info['display_name']} ({weight})")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(font_path, 'wb') as f:
                            f.write(await response.read())
                        
                        self.logger.info(f"✅ 字体下载完成: {font_path}")
                    else:
                        self.logger.error(f"字体下载失败: {url} (状态码: {response.status})")
                        
        except Exception as e:
            self.logger.error(f"字体下载异常: {e}")
    
    def _get_system_fallback_font(self, language: str) -> str:
        """获取系统fallback字体"""
        if language == "zh":
            # 中文系统常见字体
            candidates = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 
                "/System/Library/Fonts/PingFang.ttc",  # macOS
                "SimHei",  # Windows
                "WenQuanYi Micro Hei"  # Linux
            ]
        else:
            # 英文字体
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "Arial",
                "Helvetica"
            ]
        
        for font in candidates:
            if os.path.exists(font):
                return font
        
        return "sans-serif"  # 最终fallback
    
    def get_ffmpeg_font_config(self, language: str = "zh", style: str = "sans") -> Dict[str, str]:
        """
        获取FFmpeg字幕渲染的字体配置
        
        Returns:
            字体配置字典，包含fontfile、fontsize、fontcolor等
        """
        # 获取字体文件路径
        try:
            # 这里需要在异步环境中调用
            import asyncio
            if asyncio.get_event_loop().is_running():
                # 如果已在异步环境中，使用缓存的字体路径
                font_path = str(self._get_font_path(
                    self._select_font_key(language, style), "Regular"
                ))
                if not os.path.exists(font_path):
                    font_path = self._get_system_fallback_font(language)
            else:
                # 同步环境中创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                font_path = loop.run_until_complete(
                    self.ensure_font_available(language, style)
                )
                loop.close()
        except:
            font_path = self._get_system_fallback_font(language)
        
        # 从配置文件获取字体设置
        font_size = self.config.get('subtitle.main_font_size', 48)
        font_color = self.config.get('subtitle.main_color', '#FFFFFF')
        border_color = self.config.get('subtitle.main_border_color', '#000000')
        outline = self.config.get('subtitle.outline', 3)
        
        return {
            'fontfile': font_path,
            'fontsize': font_size,
            'fontcolor': font_color,
            'bordercolor': border_color,
            'borderw': outline
        }
    
    async def download_all_fonts(self):
        """预下载所有推荐字体"""
        self.logger.info("🔄 开始预下载开源字体库...")
        
        tasks = []
        for font_key, font_info in self.google_fonts.items():
            for weight in font_info["weights"]:
                tasks.append(self._download_font(font_key, weight))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.info("✅ 字体库准备完成")
    
    def list_available_fonts(self) -> List[Dict]:
        """列出所有可用字体"""
        fonts = []
        for font_key, font_info in self.google_fonts.items():
            font_path = self._get_font_path(font_key, "Regular")
            fonts.append({
                'key': font_key,
                'name': font_info['name'],
                'display_name': font_info['display_name'],
                'description': font_info['description'],
                'available': font_path.exists(),
                'path': str(font_path) if font_path.exists() else None
            })
        return fonts
    
    def get_font_info(self) -> str:
        """获取字体状态信息"""
        fonts = self.list_available_fonts()
        available_count = sum(1 for f in fonts if f['available'])
        
        info = f"📚 字体库状态: {available_count}/{len(fonts)} 可用\n\n"
        
        for font in fonts:
            status = "✅" if font['available'] else "📥"
            info += f"{status} {font['display_name']} ({font['name']})\n"
            info += f"   {font['description']}\n"
            if font['available']:
                info += f"   路径: {font['path']}\n"
            info += "\n"
        
        return info