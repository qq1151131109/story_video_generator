"""
系统配置验证脚本 - 检查多语言支持和API配置
"""
import sys
from pathlib import Path
import os
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.i18n import get_i18n_manager
from utils.logger import setup_logging


def check_python_environment():
    """检查Python环境"""
    print("🐍 Python环境检查")
    print("-" * 40)
    
    # Python版本检查
    version = sys.version_info
    print(f"Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version < (3, 8):
        print("❌ Python版本过低，需要3.8+")
        return False
    else:
        print("✅ Python版本符合要求")
    
    # 必需模块检查
    required_modules = [
        'asyncio', 'aiohttp', 'openai', 'pathlib', 'json', 
        'logging', 'dataclasses', 'typing', 'time', 'hashlib'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ 缺少模块: {', '.join(missing_modules)}")
        return False
    else:
        print("✅ 所有必需模块已安装")
    
    return True


def check_project_structure():
    """检查项目结构"""
    print("\n📁 项目结构检查")
    print("-" * 40)
    
    base_dir = Path(__file__).parent
    
    required_dirs = [
        'core', 'content', 'media', 'video', 'utils', 'config'
    ]
    
    required_files = [
        '__init__.py', 'main.py', 'requirements.txt',
        'core/__init__.py', 'core/config_manager.py', 'core/cache_manager.py',
        'utils/__init__.py', 'utils/file_manager.py', 'utils/logger.py', 'utils/i18n.py',
        'content/__init__.py', 'content/content_pipeline.py',
        'config/settings.json'
    ]
    
    # 检查目录
    missing_dirs = []
    for dir_name in required_dirs:
        if not (base_dir / dir_name).is_dir():
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print(f"❌ 缺少目录: {', '.join(missing_dirs)}")
        return False
    else:
        print("✅ 所有必需目录存在")
    
    # 检查文件
    missing_files = []
    for file_name in required_files:
        if not (base_dir / file_name).is_file():
            missing_files.append(file_name)
    
    if missing_files:
        print(f"❌ 缺少文件: {', '.join(missing_files)}")
        return False
    else:
        print("✅ 所有必需文件存在")
    
    return True


def check_configuration():
    """检查配置文件"""
    print("\n⚙️ 配置文件检查")
    print("-" * 40)
    
    try:
        config = ConfigManager()
        
        # 检查基本配置
        supported_languages = config.get_supported_languages()
        print(f"支持的语言: {supported_languages}")
        
        if len(supported_languages) < 3:
            print("⚠️  警告: 支持的语言少于3种")
        else:
            print("✅ 多语言配置正常")
        
        # 检查输出目录
        output_dir = config.get('general.output_dir', 'output')
        output_path = Path(output_dir)
        
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ 输出目录可用: {output_path}")
        except Exception as e:
            print(f"❌ 输出目录创建失败: {e}")
            return False
        
        # 验证配置完整性
        config_errors = config.validate_config()
        if config_errors:
            print("❌ 配置错误:")
            for error in config_errors:
                print(f"  - {error}")
            return False
        else:
            print("✅ 配置验证通过")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        return False


def check_api_keys():
    """检查API密钥配置"""
    print("\n🔑 API密钥检查")
    print("-" * 40)
    
    api_keys = {
        'OPENROUTER_API_KEY': '必需 - LLM文案生成',
        'RUNNINGHUB_API_KEY': '可选 - 图像生成(主要)',
        'AZURE_API_KEY': '可选 - 音频合成(主要)', 
        'ELEVENLABS_API_KEY': '可选 - 音频合成(备用)',
        'STABILITY_API_KEY': '可选 - 图像生成(备用)'
    }
    
    available_keys = []
    missing_required = []
    
    for key, description in api_keys.items():
        value = os.getenv(key)
        if value:
            # 隐藏API密钥内容，只显示前后几位
            if len(value) > 10:
                masked_value = f"{value[:4]}...{value[-4:]}"
            else:
                masked_value = "***"
            print(f"✅ {key}: {masked_value} - {description}")
            available_keys.append(key)
        else:
            print(f"❌ {key}: 未设置 - {description}")
            if '必需' in description:
                missing_required.append(key)
    
    print(f"\n可用API密钥: {len(available_keys)}/{len(api_keys)}")
    
    if missing_required:
        print(f"❌ 缺少必需的API密钥: {', '.join(missing_required)}")
        return False
    else:
        print("✅ 至少有必需的API密钥")
        return True


def check_multilanguage_support():
    """检查多语言支持"""
    print("\n🌍 多语言支持检查")
    print("-" * 40)
    
    try:
        i18n = get_i18n_manager()
        
        # 检查支持的语言
        languages = i18n.get_supported_languages()
        print(f"支持的语言数量: {len(languages)}")
        
        for lang_code, lang_info in languages.items():
            print(f"  - {lang_code}: {lang_info['name']} ({lang_info['english_name']})")
        
        # 检查消息本地化
        test_passed = True
        for lang_code in languages.keys():
            i18n.set_language(lang_code)
            
            # 测试基本消息
            success_msg = i18n.get_message('common', 'success')
            if not success_msg or '[' in success_msg:
                print(f"❌ {lang_code}: 基本消息缺失")
                test_passed = False
            
            # 测试内容生成消息
            content_msg = i18n.get_message('content', 'generating_script')
            if not content_msg or '[' in content_msg:
                print(f"❌ {lang_code}: 内容生成消息缺失")
                test_passed = False
        
        if test_passed:
            print("✅ 所有语言的本地化消息完整")
        
        # 检查主题文件
        theme_files = {
            'zh': 'example_themes.txt',
            'en': 'themes_en.txt',
            'es': 'themes_es.txt'
        }
        
        theme_files_ok = True
        for lang_code, filename in theme_files.items():
            file_path = Path(__file__).parent / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    themes = [line.strip() for line in f if line.strip()]
                print(f"✅ {lang_code}: {len(themes)} 个主题 ({filename})")
            else:
                print(f"❌ {lang_code}: 主题文件缺失 ({filename})")
                theme_files_ok = False
        
        return test_passed and theme_files_ok
        
    except Exception as e:
        print(f"❌ 多语言支持检查失败: {e}")
        return False


def check_cache_system():
    """检查缓存系统（已禁用，缓存功能已移除）"""
    print("\n💾 缓存系统检查")
    print("-" * 40)
    print("⚠️  缓存功能已移除，跳过缓存系统检查")
    return True


def check_logging_system():
    """检查日志系统"""
    print("\n📝 日志系统检查")
    print("-" * 40)
    
    try:
        logger_manager = setup_logging()
        
        # 测试日志记录
        test_logger = logger_manager.get_logger('story_generator.test')
        test_logger.info("测试日志消息")
        
        # 检查日志统计
        log_stats = logger_manager.get_log_stats()
        if log_stats:
            print(f"✅ 日志系统正常，共 {len(log_stats)} 个日志文件")
        else:
            print("⚠️  日志统计为空，但功能可能正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 日志系统检查失败: {e}")
        return False


def generate_setup_report():
    """生成配置报告"""
    print("\n📊 生成配置报告")
    print("-" * 40)
    
    checks = [
        ("Python环境", check_python_environment),
        ("项目结构", check_project_structure), 
        ("配置文件", check_configuration),
        ("API密钥", check_api_keys),
        ("多语言支持", check_multilanguage_support),
        ("缓存系统", check_cache_system),
        ("日志系统", check_logging_system)
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"❌ {check_name}检查出错: {e}")
            results[check_name] = False
    
    # 生成总结报告
    print("\n" + "="*60)
    print("配置验证总结")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for check_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{check_name:>12}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n🎉 所有检查通过！系统已准备好运行。")
        print("\n建议运行:")
        print("  python main.py --test  # 运行测试模式")
        print("  python test_multilang.py  # 测试多语言功能")
    else:
        print(f"\n⚠️  发现 {failed} 个问题，请修复后再运行系统。")
        
        if not results.get("API密钥", False):
            print("\n💡 API密钥配置提示:")
            print("  创建 .env 文件并添加:")
            print("  OPENROUTER_API_KEY=your_key_here")
    
    return failed == 0


def main():
    """主函数"""
    print("历史故事生成器 - 系统配置验证")
    print("="*60)
    
    success = generate_setup_report()
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()