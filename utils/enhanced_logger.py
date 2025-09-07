"""
增强型日志管理器 - 优化版本
专为故事视频生成器设计的高效日志系统，支持快速问题定位和排查
"""
import logging
import logging.handlers
import sys
import json
import time
import traceback
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from threading import Lock
import asyncio

@dataclass
class LogContext:
    """日志上下文信息"""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

@dataclass 
class PerformanceMetrics:
    """性能指标"""
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    memory_usage: Optional[int] = None
    api_calls: int = 0
    success: bool = True

class StructuredFormatter(logging.Formatter):
    """结构化日志格式器"""
    
    def __init__(self, fields: List[str], sensitive_patterns: List[str] = None):
        super().__init__()
        self.fields = fields or ["timestamp", "level", "component", "message"]
        self.sensitive_patterns = [re.compile(pattern, re.IGNORECASE) 
                                 for pattern in (sensitive_patterns or [])]
    
    def format(self, record) -> str:
        """格式化日志记录"""
        log_data = {}
        
        # 基础字段
        if "timestamp" in self.fields:
            log_data["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
        if "level" in self.fields:
            log_data["level"] = record.levelname
        if "component" in self.fields:
            log_data["component"] = record.name.split('.')[-1] if '.' in record.name else record.name
        if "function" in self.fields:
            log_data["function"] = record.funcName
        if "message" in self.fields:
            log_data["message"] = self._mask_sensitive_info(record.getMessage())
        
        # 上下文信息
        if "context" in self.fields and hasattr(record, 'context'):
            log_data["context"] = record.context
        
        # 性能信息
        if "performance" in self.fields and hasattr(record, 'performance'):
            log_data["performance"] = record.performance
        
        # 错误追踪
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self._format_exception(record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
    
    def _mask_sensitive_info(self, message: str) -> str:
        """掩码敏感信息"""
        for pattern in self.sensitive_patterns:
            message = pattern.sub('***MASKED***', message)
        return message
    
    def _format_exception(self, exc_info) -> List[str]:
        """格式化异常信息"""
        return traceback.format_exception(*exc_info)

class EnhancedLoggerManager:
    """
    增强型日志管理器
    
    特性：
    1. 结构化日志输出 - JSON格式，便于分析
    2. 智能错误聚合 - 错误自动汇总到errors.log
    3. 性能追踪 - API调用时间、处理耗时统计
    4. 敏感信息掩码 - 自动屏蔽API密钥等信息
    5. 快速问题定位 - 通过上下文快速定位问题
    6. 分级日志管理 - 不同级别的日志分别处理
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('logging', {})
        self.log_dir = Path(config.get('general', {}).get('output_dir', 'output')) / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._locks = {}  # 线程锁
        self._error_counts = {}  # 错误统计
        self._performance_data = {}  # 性能数据
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志系统"""
        # 清理现有处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 设置根日志器
        root_logger.setLevel(logging.DEBUG)
        
        # 设置控制台日志
        self._setup_console_logging()
        
        # 设置文件日志
        self._setup_file_logging()
        
        # 设置第三方库日志级别
        self._configure_third_party_loggers()
    
    def _setup_console_logging(self):
        """设置控制台日志"""
        console_level = self.config.get('console_level', 'INFO')
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, console_level))
        
        # 控制台使用简洁格式
        console_formatter = self._get_console_formatter()
        console_handler.setFormatter(console_formatter)
        
        # 添加过滤器
        console_handler.addFilter(self._create_exclude_filter())
        
        logging.getLogger().addHandler(console_handler)
    
    def _setup_file_logging(self):
        """设置文件日志"""
        files_config = self.config.get('files', {})
        
        for log_type, file_config in files_config.items():
            if not file_config.get('enabled', True):
                continue
                
            self._setup_file_handler(log_type, file_config)
    
    def _setup_file_handler(self, log_type: str, file_config: Dict[str, Any]):
        """设置单个文件处理器"""
        filename = file_config['filename']
        level = file_config.get('level', 'INFO')
        max_size = file_config.get('max_size_mb', self.config.get('max_file_size_mb', 5))
        
        log_file = self.log_dir / filename
        
        # 创建轮转文件处理器
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_size * 1024 * 1024,
            backupCount=self.config.get('backup_count', 3),
            encoding='utf-8'
        )
        handler.setLevel(getattr(logging, level))
        
        # 选择格式器
        if self.config.get('log_format') == 'structured':
            formatter = StructuredFormatter(
                fields=self.config.get('structured_fields', []),
                sensitive_patterns=self.config.get('filters', {}).get('sensitive_patterns', [])
            )
        else:
            formatter = self._get_file_formatter(log_type)
        
        handler.setFormatter(formatter)
        
        # 错误日志只记录ERROR及以上级别
        if log_type == 'errors':
            handler.addFilter(lambda record: record.levelno >= logging.ERROR)
        # 性能日志只记录包含性能信息的记录
        elif log_type == 'performance':
            handler.addFilter(lambda record: hasattr(record, 'performance'))
        
        # 添加排除过滤器
        handler.addFilter(self._create_exclude_filter())
        
        logging.getLogger().addHandler(handler)
    
    def _get_console_formatter(self) -> logging.Formatter:
        """获取控制台格式器（彩色 + 简洁）"""
        class ColoredFormatter(logging.Formatter):
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
    
    def _get_file_formatter(self, log_type: str) -> logging.Formatter:
        """获取文件格式器"""
        if log_type == 'errors':
            return logging.Formatter(
                '%(asctime)s | ERROR | %(name)s | %(funcName)s:%(lineno)d | %(message)s\n'
                '%(pathname)s\n'
                '--- TRACEBACK ---\n%(exc_text)s\n--- END ---\n',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        elif log_type == 'performance':
            return logging.Formatter(
                '%(asctime)s | PERF | %(name)s | %(funcName)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            return logging.Formatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(funcName)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def _create_exclude_filter(self):
        """创建排除过滤器"""
        exclude_patterns = self.config.get('filters', {}).get('exclude_patterns', [])
        compiled_patterns = [re.compile(pattern) for pattern in exclude_patterns]
        
        def filter_func(record):
            message = record.getMessage()
            return not any(pattern.search(message) for pattern in compiled_patterns)
        
        return filter_func
    
    def _configure_third_party_loggers(self):
        """配置第三方库日志级别"""
        # 减少第三方库的日志输出
        third_party_loggers = [
            'httpx', 'urllib3', 'requests', 'aiohttp',
            'openai', 'anthropic', 'langchain',
            'PIL', 'matplotlib', 'numpy'
        ]
        
        for logger_name in third_party_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        logger = logging.getLogger(name)
        # 确保错误传播到根logger（关键修复）
        logger.propagate = True
        return logger
    
    @contextmanager
    def log_context(self, **context_data):
        """日志上下文管理器"""
        context = LogContext(**context_data)
        # 这里可以实现上下文存储逻辑
        try:
            yield context
        finally:
            pass
    
    @contextmanager 
    def performance_tracker(self, logger: logging.Logger, operation: str):
        """性能追踪上下文管理器"""
        start_time = time.time()
        metrics = PerformanceMetrics(start_time=start_time)
        
        try:
            yield metrics
            metrics.success = True
        except Exception as e:
            metrics.success = False
            raise
        finally:
            metrics.end_time = time.time()
            metrics.duration = metrics.end_time - metrics.start_time
            
            # 记录性能日志
            perf_record = logger.makeRecord(
                logger.name, logging.INFO, __file__, 0,
                f"Operation '{operation}' completed in {metrics.duration:.3f}s",
                (), None
            )
            perf_record.performance = asdict(metrics)
            logger.handle(perf_record)
    
    def log_error_with_context(self, logger: logging.Logger, error: Exception, 
                              context: Optional[Dict[str, Any]] = None):
        """记录带上下文的错误"""
        error_key = f"{type(error).__name__}:{str(error)}"
        
        # 错误统计
        if error_key not in self._error_counts:
            self._error_counts[error_key] = 0
        self._error_counts[error_key] += 1
        
        # 构建错误信息
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'occurrence_count': self._error_counts[error_key],
            'context': context or {}
        }
        
        # 记录到错误日志
        error_record = logger.makeRecord(
            logger.name, logging.ERROR, __file__, 0,
            f"Error occurred: {error_info}",
            (), (type(error), error, error.__traceback__)
        )
        error_record.context = error_info
        logger.handle(error_record)
    
    def log_api_call(self, logger: logging.Logger, method: str, url: str, 
                     status_code: Optional[int] = None,
                     response_time: Optional[float] = None, 
                     error: Optional[str] = None):
        """记录API调用（性能追踪）"""
        metrics = {
            'method': method,
            'url': self._mask_url_sensitive_info(url),
            'status_code': status_code,
            'response_time': response_time,
            'success': error is None
        }
        
        level = logging.ERROR if error else logging.INFO
        message = f"API {method} {url}"
        if status_code:
            message += f" [{status_code}]"
        if response_time:
            message += f" ({response_time:.3f}s)"
        if error:
            message += f" ERROR: {error}"
        
        # 创建性能记录
        perf_record = logger.makeRecord(
            logger.name, level, __file__, 0, message, (), None
        )
        perf_record.performance = metrics
        logger.handle(perf_record)
    
    def _mask_url_sensitive_info(self, url: str) -> str:
        """掩码URL中的敏感信息"""
        # 掩码API密钥参数
        url = re.sub(r'([?&]api_key=)[^&]*', r'\1***MASKED***', url)
        url = re.sub(r'([?&]key=)[^&]*', r'\1***MASKED***', url)
        url = re.sub(r'([?&]token=)[^&]*', r'\1***MASKED***', url)
        return url
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        return {
            'total_errors': sum(self._error_counts.values()),
            'unique_errors': len(self._error_counts),
            'top_errors': sorted(
                self._error_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
        }
    
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
        except Exception as e:
            logger = self.get_logger('logger_manager')
            logger.error(f"Failed to cleanup old logs: {e}")
        
        return cleaned_count

def setup_enhanced_logging(config: Dict[str, Any]) -> EnhancedLoggerManager:
    """
    快速设置增强型日志系统
    
    Args:
        config: 完整的配置字典
    
    Returns:
        EnhancedLoggerManager实例
    
    Usage:
        # 基础用法
        config = {...}  # 从settings.json加载
        log_manager = setup_enhanced_logging(config)
        logger = log_manager.get_logger('my_component')
        
        # 性能追踪
        with log_manager.performance_tracker(logger, 'api_call'):
            # 执行API调用
            pass
        
        # 错误记录
        try:
            risky_operation()
        except Exception as e:
            log_manager.log_error_with_context(logger, e, {'user_id': '123'})
    """
    return EnhancedLoggerManager(config)

# 向后兼容的别名
def setup_logging(log_dir: str = "output/logs", log_level: str = "INFO") -> EnhancedLoggerManager:
    """向后兼容的设置函数"""
    # 构建基础配置
    config = {
        'general': {
            'output_dir': log_dir.replace('/logs', ''),
            'log_level': log_level
        },
        'logging': {
            'level': log_level,
            'console_level': log_level,
            'file_level': 'DEBUG',
            'max_file_size_mb': 5,
            'backup_count': 3,
            'log_format': 'structured',
            'enable_error_aggregation': True,
            'enable_performance_tracking': True,
            'files': {
                'main': {
                    'filename': 'story_generator.log',
                    'level': 'INFO',
                    'enabled': True
                },
                'errors': {
                    'filename': 'errors.log',
                    'level': 'ERROR', 
                    'enabled': True
                },
                'performance': {
                    'filename': 'performance.log',
                    'level': 'INFO',
                    'enabled': True
                }
            }
        }
    }
    return setup_enhanced_logging(config)