"""
日志系统兼容性层
确保现有代码可以无缝使用新的增强型日志系统
"""
from utils.enhanced_logger import (
    setup_enhanced_logging,
    EnhancedLoggerManager
)
from core.config_manager import ConfigManager

# 向后兼容的别名
LoggerManager = EnhancedLoggerManager

def setup_logging(log_dir: str = "output/logs", log_level: str = "INFO"):
    """
    向后兼容的setup_logging函数
    自动使用增强型日志系统
    """
    try:
        # 尝试使用ConfigManager获取完整配置
        config_manager = ConfigManager()
        return setup_enhanced_logging(config_manager.config)
    except Exception:
        # 降级使用基础配置
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
