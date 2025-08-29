"""
国际化支持模块 - 多语言文本和本地化处理
"""
from typing import Dict, Any, Optional
from pathlib import Path
import json
import logging
from dataclasses import dataclass

@dataclass
class LocalizedText:
    """本地化文本"""
    zh: str = ""  # 中文
    en: str = ""  # 英语
    es: str = ""  # 西班牙语

class I18nManager:
    """
    国际化管理器
    
    功能：
    - 多语言文本管理
    - 语言检测和验证
    - 本地化消息处理
    - 动态语言切换
    """
    
    def __init__(self, default_language: str = "zh"):
        self.default_language = default_language
        self.current_language = default_language
        self.logger = logging.getLogger(__name__)
        
        # 支持的语言
        self.supported_languages = {
            'zh': {
                'name': '中文',
                'english_name': 'Chinese',
                'locale': 'zh_CN',
                'rtl': False
            },
            'en': {
                'name': 'English',
                'english_name': 'English',
                'locale': 'en_US',
                'rtl': False
            },
            'es': {
                'name': 'Español',
                'english_name': 'Spanish',
                'locale': 'es_ES',
                'rtl': False
            }
        }
        
        # 加载本地化消息
        self.messages = {}
        self._load_messages()
        
        self.logger.info(f"I18n manager initialized with default language: {default_language}")
    
    def _load_messages(self):
        """加载本地化消息"""
        base_messages = {
            # 通用消息
            'common': {
                'success': LocalizedText(
                    zh="成功",
                    en="Success",
                    es="Éxito"
                ),
                'failed': LocalizedText(
                    zh="失败",
                    en="Failed",
                    es="Fallido"
                ),
                'error': LocalizedText(
                    zh="错误",
                    en="Error", 
                    es="Error"
                ),
                'warning': LocalizedText(
                    zh="警告",
                    en="Warning",
                    es="Advertencia"
                ),
                'processing': LocalizedText(
                    zh="处理中...",
                    en="Processing...",
                    es="Procesando..."
                ),
                'completed': LocalizedText(
                    zh="已完成",
                    en="Completed",
                    es="Completado"
                ),
                'cancelled': LocalizedText(
                    zh="已取消",
                    en="Cancelled",
                    es="Cancelado"
                )
            },
            
            # 内容生成相关
            'content': {
                'generating_script': LocalizedText(
                    zh="正在生成文案...",
                    en="Generating script...",
                    es="Generando guión..."
                ),
                'splitting_scenes': LocalizedText(
                    zh="正在分割场景...",
                    en="Splitting scenes...",
                    es="Dividiendo escenas..."
                ),
                'analyzing_characters': LocalizedText(
                    zh="正在分析角色...",
                    en="Analyzing characters...",
                    es="Analizando personajes..."
                ),
                'script_generated': LocalizedText(
                    zh="文案生成完成",
                    en="Script generated successfully",
                    es="Guión generado exitosamente"
                ),
                'scenes_split': LocalizedText(
                    zh="场景分割完成",
                    en="Scenes split successfully",
                    es="Escenas divididas exitosamente"
                ),
                'characters_analyzed': LocalizedText(
                    zh="角色分析完成",
                    en="Characters analyzed successfully",
                    es="Personajes analizados exitosamente"
                )
            },
            
            # 媒体生成相关
            'media': {
                'generating_image': LocalizedText(
                    zh="正在生成图像...",
                    en="Generating image...",
                    es="Generando imagen..."
                ),
                'generating_audio': LocalizedText(
                    zh="正在生成音频...",
                    en="Generating audio...",
                    es="Generando audio..."
                ),
                'image_generated': LocalizedText(
                    zh="图像生成完成",
                    en="Image generated successfully",
                    es="Imagen generada exitosamente"
                ),
                'audio_generated': LocalizedText(
                    zh="音频生成完成",
                    en="Audio generated successfully",
                    es="Audio generado exitosamente"
                ),
                'provider_failed': LocalizedText(
                    zh="提供商 {provider} 失败: {error}",
                    en="Provider {provider} failed: {error}",
                    es="Proveedor {provider} falló: {error}"
                ),
                'trying_fallback': LocalizedText(
                    zh="正在尝试备用提供商...",
                    en="Trying fallback provider...",
                    es="Probando proveedor de respaldo..."
                )
            },
            
            # 视频处理相关
            'video': {
                'processing_subtitles': LocalizedText(
                    zh="正在处理字幕...",
                    en="Processing subtitles...",
                    es="Procesando subtítulos..."
                ),
                'creating_animation': LocalizedText(
                    zh="正在创建动画...",
                    en="Creating animation...",
                    es="Creando animación..."
                ),
                'composing_video': LocalizedText(
                    zh="正在合成视频...",
                    en="Composing video...",
                    es="Componiendo video..."
                )
            },
            
            # 批处理相关
            'batch': {
                'starting_batch': LocalizedText(
                    zh="开始批量处理，共 {total} 个任务",
                    en="Starting batch processing, {total} tasks total",
                    es="Iniciando procesamiento en lote, {total} tareas en total"
                ),
                'batch_progress': LocalizedText(
                    zh="进度: {current}/{total} (成功: {success}, 失败: {failed})",
                    en="Progress: {current}/{total} (Success: {success}, Failed: {failed})",
                    es="Progreso: {current}/{total} (Éxito: {success}, Fallido: {failed})"
                ),
                'batch_completed': LocalizedText(
                    zh="批量处理完成: 成功 {success}, 失败 {failed}",
                    en="Batch processing completed: {success} successful, {failed} failed",
                    es="Procesamiento en lote completado: {success} exitoso, {failed} fallido"
                ),
                'estimated_time': LocalizedText(
                    zh="预计剩余时间: {eta}",
                    en="Estimated time remaining: {eta}",
                    es="Tiempo estimado restante: {eta}"
                )
            },
            
            # 错误消息
            'errors': {
                'api_key_missing': LocalizedText(
                    zh="缺少API密钥: {service}",
                    en="Missing API key: {service}",
                    es="Falta clave API: {service}"
                ),
                'invalid_language': LocalizedText(
                    zh="不支持的语言: {language}",
                    en="Unsupported language: {language}",
                    es="Idioma no soportado: {language}"
                ),
                'file_not_found': LocalizedText(
                    zh="文件未找到: {path}",
                    en="File not found: {path}",
                    es="Archivo no encontrado: {path}"
                ),
                'network_error': LocalizedText(
                    zh="网络错误: {error}",
                    en="Network error: {error}",
                    es="Error de red: {error}"
                ),
                'config_error': LocalizedText(
                    zh="配置错误: {error}",
                    en="Configuration error: {error}",
                    es="Error de configuración: {error}"
                )
            }
        }
        
        self.messages = base_messages
    
    def set_language(self, language: str) -> bool:
        """
        设置当前语言
        
        Args:
            language: 语言代码
        
        Returns:
            bool: 设置是否成功
        """
        if language not in self.supported_languages:
            self.logger.warning(f"Unsupported language: {language}")
            return False
        
        self.current_language = language
        self.logger.info(f"Language set to: {language}")
        return True
    
    def get_message(self, category: str, key: str, language: Optional[str] = None, **kwargs) -> str:
        """
        获取本地化消息
        
        Args:
            category: 消息分类
            key: 消息键
            language: 语言代码（可选，默认使用当前语言）
            **kwargs: 格式化参数
        
        Returns:
            str: 本地化消息
        """
        lang = language or self.current_language
        
        try:
            if category not in self.messages:
                return f"[Missing category: {category}]"
            
            if key not in self.messages[category]:
                return f"[Missing key: {category}.{key}]"
            
            localized_text = self.messages[category][key]
            
            # 获取指定语言的文本
            if hasattr(localized_text, lang):
                text = getattr(localized_text, lang)
            else:
                # 回退到默认语言
                text = getattr(localized_text, self.default_language, "")
            
            # 如果文本为空，尝试英语
            if not text and lang != 'en' and hasattr(localized_text, 'en'):
                text = localized_text.en
            
            # 格式化参数
            if kwargs and text:
                try:
                    text = text.format(**kwargs)
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Failed to format message {category}.{key}: {e}")
            
            return text or f"[Empty text: {category}.{key}]"
            
        except Exception as e:
            self.logger.error(f"Failed to get message {category}.{key}: {e}")
            return f"[Error: {category}.{key}]"
    
    def get_language_info(self, language: str) -> Optional[Dict[str, Any]]:
        """
        获取语言信息
        
        Args:
            language: 语言代码
        
        Returns:
            Dict[str, Any]: 语言信息
        """
        return self.supported_languages.get(language)
    
    def get_supported_languages(self) -> Dict[str, Dict[str, Any]]:
        """获取支持的语言列表"""
        return self.supported_languages.copy()
    
    def detect_language_from_text(self, text: str) -> str:
        """
        从文本检测语言（简单实现）
        
        Args:
            text: 输入文本
        
        Returns:
            str: 检测到的语言代码
        """
        if not text:
            return self.default_language
        
        # 简单的语言检测逻辑
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        spanish_chars = len([c for c in text.lower() if c in 'ñáéíóúü'])
        
        total_chars = len(text)
        
        if chinese_chars > total_chars * 0.3:
            return 'zh'
        elif spanish_chars > 0:
            return 'es'
        else:
            return 'en'
    
    def format_time_duration(self, seconds: float, language: Optional[str] = None) -> str:
        """
        格式化时长显示
        
        Args:
            seconds: 时长（秒）
            language: 语言代码
        
        Returns:
            str: 格式化的时长字符串
        """
        lang = language or self.current_language
        
        if seconds < 60:
            if lang == 'zh':
                return f"{seconds:.1f}秒"
            elif lang == 'es':
                return f"{seconds:.1f}s"
            else:
                return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            if lang == 'zh':
                return f"{minutes}分{secs}秒"
            elif lang == 'es':
                return f"{minutes}m {secs}s"
            else:
                return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            if lang == 'zh':
                return f"{hours}小时{minutes}分钟"
            elif lang == 'es':
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h {minutes}m"
    
    def format_file_size(self, bytes_size: int, language: Optional[str] = None) -> str:
        """
        格式化文件大小显示
        
        Args:
            bytes_size: 文件大小（字节）
            language: 语言代码
        
        Returns:
            str: 格式化的文件大小字符串
        """
        lang = language or self.current_language
        
        if bytes_size < 1024:
            return f"{bytes_size}B"
        elif bytes_size < 1024 * 1024:
            kb = bytes_size / 1024
            return f"{kb:.1f}KB"
        elif bytes_size < 1024 * 1024 * 1024:
            mb = bytes_size / (1024 * 1024)
            return f"{mb:.1f}MB"
        else:
            gb = bytes_size / (1024 * 1024 * 1024)
            return f"{gb:.2f}GB"
    
    def get_error_message(self, error_type: str, language: Optional[str] = None, **kwargs) -> str:
        """
        获取错误消息的便捷方法
        
        Args:
            error_type: 错误类型
            language: 语言代码
            **kwargs: 格式化参数
        
        Returns:
            str: 本地化错误消息
        """
        return self.get_message('errors', error_type, language, **kwargs)
    
    def get_success_message(self, message_type: str, language: Optional[str] = None, **kwargs) -> str:
        """
        获取成功消息的便捷方法
        
        Args:
            message_type: 消息类型
            language: 语言代码
            **kwargs: 格式化参数
        
        Returns:
            str: 本地化成功消息
        """
        # 先尝试在对应分类中查找
        for category in ['content', 'media', 'video', 'batch']:
            try:
                if message_type in self.messages[category]:
                    return self.get_message(category, message_type, language, **kwargs)
            except:
                continue
        
        # 回退到通用消息
        return self.get_message('common', message_type, language, **kwargs)
    
    def validate_theme_translation(self, theme: str, target_language: str) -> bool:
        """
        验证主题是否适合目标语言
        
        Args:
            theme: 主题文本
            target_language: 目标语言
        
        Returns:
            bool: 是否适合
        """
        detected_lang = self.detect_language_from_text(theme)
        
        # 如果检测到的语言与目标语言匹配，或者是通用主题，则适合
        return detected_lang == target_language or detected_lang == self.default_language
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"I18nManager(current_language={self.current_language}, supported={list(self.supported_languages.keys())})"


# 全局实例
_i18n_manager = None

def get_i18n_manager(default_language: str = "zh") -> I18nManager:
    """获取全局i18n管理器实例"""
    global _i18n_manager
    if _i18n_manager is None:
        _i18n_manager = I18nManager(default_language)
    return _i18n_manager

def set_global_language(language: str) -> bool:
    """设置全局语言"""
    i18n = get_i18n_manager()
    return i18n.set_language(language)

def t(category: str, key: str, language: Optional[str] = None, **kwargs) -> str:
    """获取本地化消息的快捷方法"""
    i18n = get_i18n_manager()
    return i18n.get_message(category, key, language, **kwargs)