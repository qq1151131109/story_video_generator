"""
日志配置工具 - 统一的日志管理
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json

class LoggerManager:
    """
    日志管理器 - 配置项目统一的日志系统
    
    功能：
    - 多级别日志输出
    - 文件轮转
    - 彩色控制台输出
    - 结构化日志
    """
    
    def __init__(self, log_dir: str = "output/logs", 
                 log_level: str = "INFO", max_bytes: int = 10485760, backup_count: int = 5):
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper())
        self.max_bytes = max_bytes  # 10MB
        self.backup_count = backup_count
        
        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置根logger
        self._setup_root_logger()
        
        # 创建专用loggers
        self._setup_specialized_loggers()
    
    def _setup_root_logger(self):
        """配置根logger"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除已有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_formatter = self._get_console_formatter()
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器（主日志）
        main_log_file = self.log_dir / "story_generator.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file, 
            maxBytes=self.max_bytes, 
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # 文件中记录所有级别
        file_formatter = self._get_file_formatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    def _setup_specialized_loggers(self):
        """设置专用loggers"""
        specialized_configs = {
            'story_generator.api': {
                'file': 'api_calls.log',
                'level': logging.INFO,
                'format_type': 'api'
            },
            'story_generator.content': {
                'file': 'content_generation.log', 
                'level': logging.INFO,
                'format_type': 'content'
            },
            'story_generator.media': {
                'file': 'media_generation.log',
                'level': logging.INFO,
                'format_type': 'media'
            },
            'story_generator.video': {
                'file': 'video_composition.log',
                'level': logging.INFO,
                'format_type': 'video'
            },
            'story_generator.cache': {
                'file': 'cache_operations.log',
                'level': logging.DEBUG,
                'format_type': 'cache'
            },
            'story_generator.batch': {
                'file': 'batch_processing.log',
                'level': logging.INFO,
                'format_type': 'batch'
            },
            'story_generator.error': {
                'file': 'errors.log',
                'level': logging.ERROR,
                'format_type': 'error'
            }
        }
        
        for logger_name, config in specialized_configs.items():
            self._create_specialized_logger(logger_name, config)
    
    def _create_specialized_logger(self, logger_name: str, config: Dict[str, Any]):
        """创建专用logger"""
        logger = logging.getLogger(logger_name)
        logger.setLevel(config['level'])
        
        # 防止重复添加处理器
        if logger.handlers:
            return logger
        
        # 文件处理器
        log_file = self.log_dir / config['file']
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(config['level'])
        
        # 根据类型选择格式器
        if config['format_type'] == 'api':
            formatter = self._get_api_formatter()
        elif config['format_type'] == 'content':
            formatter = self._get_content_formatter()
        elif config['format_type'] == 'media':
            formatter = self._get_media_formatter()
        elif config['format_type'] == 'video':
            formatter = self._get_video_formatter()
        elif config['format_type'] == 'cache':
            formatter = self._get_cache_formatter()
        elif config['format_type'] == 'batch':
            formatter = self._get_batch_formatter()
        elif config['format_type'] == 'error':
            formatter = self._get_error_formatter()
        else:
            formatter = self._get_file_formatter()
        
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 不传播到根logger（避免重复记录）
        logger.propagate = False
        
        return logger
    
    def _get_console_formatter(self) -> logging.Formatter:
        """获取控制台格式器（带颜色）"""
        class ColoredFormatter(logging.Formatter):
            """彩色格式器"""
            
            COLORS = {
                'DEBUG': '\033[36m',     # 青色
                'INFO': '\033[32m',      # 绿色  
                'WARNING': '\033[33m',   # 黄色
                'ERROR': '\033[31m',     # 红色
                'CRITICAL': '\033[35m'   # 紫色
            }
            RESET = '\033[0m'
            
            def format(self, record):
                if record.levelname in self.COLORS:
                    record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
                return super().format(record)
        
        return ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def _get_file_formatter(self) -> logging.Formatter:
        """获取文件格式器"""
        return logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _get_api_formatter(self) -> logging.Formatter:
        """API调用格式器"""
        return logging.Formatter(
            '%(asctime)s | API | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _get_content_formatter(self) -> logging.Formatter:
        """内容生成格式器"""
        return logging.Formatter(
            '%(asctime)s | CONTENT | %(levelname)-8s | %(funcName)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _get_media_formatter(self) -> logging.Formatter:
        """媒体生成格式器"""
        return logging.Formatter(
            '%(asctime)s | MEDIA | %(levelname)-8s | %(funcName)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _get_video_formatter(self) -> logging.Formatter:
        """视频合成格式器"""
        return logging.Formatter(
            '%(asctime)s | VIDEO | %(levelname)-8s | %(funcName)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _get_cache_formatter(self) -> logging.Formatter:
        """缓存操作格式器"""
        return logging.Formatter(
            '%(asctime)s | CACHE | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _get_batch_formatter(self) -> logging.Formatter:
        """批处理格式器"""
        return logging.Formatter(
            '%(asctime)s | BATCH | %(levelname)-8s | %(funcName)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _get_error_formatter(self) -> logging.Formatter:
        """错误格式器"""
        return logging.Formatter(
            '%(asctime)s | ERROR | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(lineno)-4d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的logger"""
        return logging.getLogger(name)
    
    def log_api_call(self, method: str, url: str, status_code: Optional[int] = None, 
                     response_time: Optional[float] = None, error: Optional[str] = None):
        """记录API调用"""
        api_logger = logging.getLogger('story_generator.api')
        
        message_parts = [f"Method: {method}", f"URL: {url}"]
        
        if status_code is not None:
            message_parts.append(f"Status: {status_code}")
        
        if response_time is not None:
            message_parts.append(f"Time: {response_time:.3f}s")
        
        message = " | ".join(message_parts)
        
        if error:
            api_logger.error(f"{message} | Error: {error}")
        elif status_code and status_code >= 400:
            api_logger.warning(message)
        else:
            api_logger.info(message)
    
    def log_content_generation(self, task_type: str, language: str, 
                              input_size: int, output_size: int, 
                              processing_time: float, success: bool = True):
        """记录内容生成"""
        content_logger = logging.getLogger('story_generator.content')
        
        message = (f"Task: {task_type} | Lang: {language} | "
                  f"Input: {input_size}chars | Output: {output_size}chars | "
                  f"Time: {processing_time:.3f}s")
        
        if success:
            content_logger.info(message)
        else:
            content_logger.error(f"{message} | FAILED")
    
    def log_media_generation(self, media_type: str, provider: str, 
                            processing_time: float, file_size: Optional[int] = None,
                            success: bool = True):
        """记录媒体生成"""
        media_logger = logging.getLogger('story_generator.media')
        
        message_parts = [
            f"Type: {media_type}",
            f"Provider: {provider}",
            f"Time: {processing_time:.3f}s"
        ]
        
        if file_size is not None:
            message_parts.append(f"Size: {file_size / 1024 / 1024:.2f}MB")
        
        message = " | ".join(message_parts)
        
        if success:
            media_logger.info(message)
        else:
            media_logger.error(f"{message} | FAILED")
    
    def log_video_composition(self, scenes_count: int, total_duration: float,
                             output_size: int, processing_time: float, success: bool = True):
        """记录视频合成"""
        video_logger = logging.getLogger('story_generator.video')
        
        message = (f"Scenes: {scenes_count} | Duration: {total_duration:.1f}s | "
                  f"Size: {output_size / 1024 / 1024:.1f}MB | Time: {processing_time:.1f}s")
        
        if success:
            video_logger.info(message)
        else:
            video_logger.error(f"{message} | FAILED")
    
    def log_batch_progress(self, current: int, total: int, completed: int, 
                          failed: int, eta_seconds: Optional[float] = None):
        """记录批处理进度"""
        batch_logger = logging.getLogger('story_generator.batch')
        
        message = f"Progress: {current}/{total} | Completed: {completed} | Failed: {failed}"
        
        if eta_seconds is not None:
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
            message += f" | ETA: {eta_str}"
        
        batch_logger.info(message)
    
    def log_error(self, component: str, error: Exception, context: Optional[Dict[str, Any]] = None):
        """记录错误信息"""
        error_logger = logging.getLogger('story_generator.error')
        
        message = f"Component: {component} | Error: {str(error)} | Type: {type(error).__name__}"
        
        if context:
            context_str = json.dumps(context, ensure_ascii=False, default=str)
            message += f" | Context: {context_str}"
        
        error_logger.error(message, exc_info=True)
    
    def get_log_stats(self) -> Dict[str, Any]:
        """获取日志统计信息"""
        stats = {}
        
        for log_file in self.log_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                stats[log_file.name] = {
                    'size_mb': stat.st_size / 1024 / 1024,
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                }
            except Exception:
                pass
        
        return stats
    
    def cleanup_old_logs(self, max_age_days: int = 7) -> int:
        """清理旧日志文件"""
        cleaned_count = 0
        current_time = datetime.now().timestamp()
        max_age_seconds = max_age_days * 24 * 3600
        
        try:
            for log_file in self.log_dir.rglob("*.log*"):
                if log_file.is_file():
                    file_age = current_time - log_file.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        try:
                            log_file.unlink()
                            cleaned_count += 1
                        except Exception:
                            pass
            
            if cleaned_count > 0:
                main_logger = logging.getLogger('story_generator')
                main_logger.info(f"Cleaned {cleaned_count} old log files")
        
        except Exception as e:
            main_logger = logging.getLogger('story_generator')
            main_logger.error(f"Failed to cleanup old logs: {e}")
        
        return cleaned_count
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"LoggerManager(log_dir={self.log_dir}, level={logging.getLevelName(self.log_level)})"


def setup_logging(log_dir: str = "output/logs", log_level: str = "INFO") -> LoggerManager:
    """
    快速设置日志系统
    
    Args:
        log_dir: 日志目录
        log_level: 日志级别
    
    Returns:
        LoggerManager实例
    """
    return LoggerManager(log_dir=log_dir, log_level=log_level)