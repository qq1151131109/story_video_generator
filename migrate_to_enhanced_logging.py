#!/usr/bin/env python3
"""
日志系统迁移脚本
将现有项目迁移到增强型日志系统
"""
import sys
from pathlib import Path
import re
import shutil
from typing import List, Dict, Any

def backup_current_logger():
    """备份当前的logger.py"""
    original = Path("utils/logger.py")
    backup = Path("utils/logger.py.backup")
    
    if original.exists() and not backup.exists():
        shutil.copy2(original, backup)
        print(f"✅ 已备份原日志文件到: {backup}")
    elif backup.exists():
        print(f"ℹ️  备份文件已存在: {backup}")

def update_logger_imports():
    """更新项目中的日志导入"""
    print("\n🔄 更新日志导入语句...")
    
    # 查找所有Python文件
    python_files = []
    for pattern in ["*.py", "**/*.py"]:
        python_files.extend(Path(".").glob(pattern))
    
    # 排除不需要修改的文件
    exclude_patterns = [
        "**/test_*.py",
        "**/__pycache__/**",
        "**/.*/**",
        "migrate_to_enhanced_logging.py",
        "test_enhanced_logging.py",
        "utils/enhanced_logger.py"
    ]
    
    filtered_files = []
    for file_path in python_files:
        if not any(file_path.match(pattern) for pattern in exclude_patterns):
            filtered_files.append(file_path)
    
    updated_count = 0
    
    for file_path in filtered_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # 更新导入语句
            replacements = [
                # 基础导入
                (r'from utils\.logger import setup_logging', 
                 'from utils.enhanced_logger import setup_enhanced_logging'),
                (r'from utils\.logger import LoggerManager',
                 'from utils.enhanced_logger import EnhancedLoggerManager'),
                
                # 初始化调用  
                (r'setup_logging\(\)',
                 'setup_enhanced_logging(self.config.config if hasattr(self, "config") else {})'),
                (r'setup_logging\(([^)]*)\)',
                 r'setup_enhanced_logging(self.config.config if hasattr(self, "config") else {})'),
                
                # Logger获取
                (r'\.get_logger\(([^)]+)\)',
                 r'.get_logger(\1)'),  # 保持不变，新系统兼容
            ]
            
            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content)
            
            # 如果内容有变化，写入文件
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                updated_count += 1
                print(f"  ✅ 更新: {file_path}")
        
        except Exception as e:
            print(f"  ❌ 无法更新 {file_path}: {e}")
    
    print(f"✅ 共更新了 {updated_count} 个文件")

def create_compatibility_layer():
    """创建兼容性层"""
    print("\n🔗 创建兼容性层...")
    
    compatibility_code = '''"""
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
'''
    
    # 更新现有的logger.py
    logger_file = Path("utils/logger.py")
    with open(logger_file, 'w', encoding='utf-8') as f:
        f.write(compatibility_code)
    
    print("✅ 兼容性层创建完成")

def update_service_classes():
    """更新服务类使用增强型日志功能"""
    print("\n🎯 更新服务类以使用增强功能...")
    
    service_file = Path("services/story_video_service.py")
    if not service_file.exists():
        print("❌ 服务文件不存在")
        return
    
    try:
        with open(service_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 在初始化方法中添加日志管理器引用
        init_pattern = r'(def __init__\(self\):.*?\n)(        self\.logger = .*?\n)'
        init_replacement = r'\1        # 初始化增强型日志系统\n        from core.config_manager import ConfigManager\n        from utils.enhanced_logger import setup_enhanced_logging\n        config = ConfigManager()\n        self._log_manager = setup_enhanced_logging(config.config)\n\2'
        
        content = re.sub(init_pattern, init_replacement, content, flags=re.DOTALL)
        
        # 添加增强型日志方法的使用示例
        enhancement_methods = '''
    
    def log_performance_metrics(self, operation: str, duration: float, success: bool = True):
        """记录性能指标"""
        if hasattr(self, '_log_manager'):
            with self._log_manager.performance_tracker(self.logger, operation):
                pass  # 性能已被追踪
    
    def log_error_with_context(self, error: Exception, context: dict = None):
        """记录带上下文的错误"""
        if hasattr(self, '_log_manager'):
            self._log_manager.log_error_with_context(self.logger, error, context)
        else:
            self.logger.error(f"Error: {error}")
    
    def log_api_call_performance(self, method: str, url: str, status_code: int = None, 
                                response_time: float = None, error: str = None):
        """记录API调用性能"""
        if hasattr(self, '_log_manager'):
            self._log_manager.log_api_call(self.logger, method, url, status_code, response_time, error)
'''
        
        # 在类的末尾添加增强方法
        class_end_pattern = r'(\n    def get_service_stats.*?return.*?\n        }.*?\n)'
        if re.search(class_end_pattern, content, re.DOTALL):
            content = re.sub(class_end_pattern, r'\1' + enhancement_methods, content, flags=re.DOTALL)
        
        with open(service_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ 服务类已更新")
    
    except Exception as e:
        print(f"❌ 更新服务类失败: {e}")

def validate_migration():
    """验证迁移结果"""
    print("\n✅ 验证迁移结果...")
    
    # 检查关键文件
    critical_files = [
        "utils/enhanced_logger.py",
        "utils/logger.py",
        "config/settings.json"
    ]
    
    all_good = True
    for file_path in critical_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} 缺失")
            all_good = False
    
    # 检查配置
    try:
        with open("config/settings.json", 'r', encoding='utf-8') as f:
            import json
            config = json.load(f)
            
        if 'logging' in config:
            print("  ✅ 日志配置已添加到settings.json")
        else:
            print("  ❌ 日志配置未找到")
            all_good = False
    
    except Exception as e:
        print(f"  ❌ 配置验证失败: {e}")
        all_good = False
    
    if all_good:
        print("🎉 迁移验证通过！")
    else:
        print("⚠️  迁移可能存在问题，请手动检查")

def show_usage_examples():
    """显示新日志系统的使用示例"""
    print("\n📚 新日志系统使用示例:")
    print("=" * 50)
    
    examples = '''
# 1. 基础使用（与原系统相同）
from utils.logger import setup_logging
log_manager = setup_logging()
logger = log_manager.get_logger('my_component')
logger.info("这是一条日志")

# 2. 性能追踪
with log_manager.performance_tracker(logger, 'api_call'):
    # 执行耗时操作
    result = api_call()

# 3. 错误记录（带上下文）
try:
    risky_operation()
except Exception as e:
    log_manager.log_error_with_context(
        logger, e, 
        context={'user_id': '123', 'operation': 'test'}
    )

# 4. API调用记录
log_manager.log_api_call(
    logger, 'POST', 'https://api.example.com',
    status_code=200, response_time=1.23
)

# 5. 错误统计
error_summary = log_manager.get_error_summary()
print(f"总错误数: {error_summary['total_errors']}")
'''
    
    print(examples)

def main():
    """主迁移函数"""
    print("🚀 开始迁移到增强型日志系统")
    print("=" * 60)
    
    try:
        # 步骤1: 备份原文件
        backup_current_logger()
        
        # 步骤2: 创建兼容性层
        create_compatibility_layer()
        
        # 步骤3: 更新导入语句（可选，兼容性层会处理）
        print("\n❓ 是否要更新代码中的导入语句? (y/n，建议选n，使用兼容性层): ", end="")
        update_imports = input().lower().strip() in ['y', 'yes']
        
        if update_imports:
            update_logger_imports()
        
        # 步骤4: 更新服务类
        update_service_classes()
        
        # 步骤5: 验证迁移
        validate_migration()
        
        # 步骤6: 显示使用示例
        show_usage_examples()
        
        print("\n" + "=" * 60)
        print("✅ 迁移完成！")
        print("\n📋 下一步操作:")
        print("1. 运行 'python test_enhanced_logging.py' 测试新日志系统")
        print("2. 重启应用程序以使用新日志系统")
        print("3. 检查 output/logs/ 目录中的新日志文件")
        print("4. 如果出现问题，可以恢复 utils/logger.py.backup")
        
    except Exception as e:
        print(f"\n❌ 迁移过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()