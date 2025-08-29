#!/usr/bin/env python3
"""
历史故事生成器 - 快速启动脚本
提供简化的用户界面和常用功能快捷入口
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def print_banner():
    """显示项目横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    历史故事生成器 v1.0.0                      ║
║                Historical Story Generator                    ║
║                                                            ║
║  🌍 多语言支持 (中文/English/Español)                        ║
║  🤖 AI智能生成 (文案/图像/音频)                              ║
║  🎬 视频处理 (字幕/动画/合成)                                ║
║  🚀 批量处理 (高效并发)                                      ║
║                                                            ║
║  基于原Coze工作流的完整Python实现                            ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_environment():
    """快速环境检查"""
    print("🔍 快速环境检查...")
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ Python版本过低，需要3.8+")
        return False
    
    # 检查基本文件
    required_files = ['main.py', 'config/settings.json', 'requirements.txt']
    missing_files = []
    
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ 缺少文件: {', '.join(missing_files)}")
        return False
    
    # 检查API密钥
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("⚠️  未检测到OPENROUTER_API_KEY，某些功能可能无法使用")
        return True  # 允许继续，但给出警告
    
    print("✅ 环境检查通过")
    return True

def show_menu():
    """显示主菜单"""
    print("\n📋 请选择操作：")
    print("=" * 50)
    print("1. 🚀 快速生成单个故事")
    print("2. 📦 批量生成多个故事") 
    print("3. 🧪 运行测试模式")
    print("4. 🌍 多语言功能测试")
    print("5. ⚙️  系统配置验证")
    print("6. 📊 性能分析和优化")
    print("7. 📚 查看帮助文档")
    print("8. 🔧 高级选项")
    print("0. 👋 退出程序")
    print("=" * 50)

def show_language_menu():
    """显示语言选择菜单"""
    print("\n🌍 选择语言 / Choose Language / Elegir Idioma:")
    print("1. 中文 (Chinese)")
    print("2. English") 
    print("3. Español (Spanish)")
    
    while True:
        choice = input("请选择 (1-3): ").strip()
        if choice == '1':
            return 'zh'
        elif choice == '2':
            return 'en'
        elif choice == '3':
            return 'es'
        else:
            print("无效选择，请重新输入")

def get_theme_examples(language):
    """获取主题示例"""
    examples = {
        'zh': [
            "秦始皇统一六国的传奇故事",
            "汉武帝开疆拓土的辉煌历史",
            "唐太宗贞观之治的盛世传奇",
            "宋太祖杯酒释兵权的智慧",
            "明成祖迁都北京的历史决策"
        ],
        'en': [
            "The legendary story of Emperor Qin Shi Huang unifying the six kingdoms",
            "The glorious history of Emperor Wu of Han expanding territory", 
            "The prosperous era of Emperor Taizong of Tang's Zhenguan reign",
            "The wisdom of Song Taizu in releasing military power with wine",
            "The historical decision of Emperor Yongle moving the capital to Beijing"
        ],
        'es': [
            "La historia legendaria del Emperador Qin Shi Huang unificando los seis reinos",
            "La historia gloriosa del Emperador Wu de Han expandiendo el territorio",
            "La era próspera del reinado Zhenguan del Emperador Taizong de Tang", 
            "La sabiduría del Emperador Taizu de Song liberando el poder militar con vino",
            "La decisión histórica del Emperador Yongle trasladando la capital a Beijing"
        ]
    }
    return examples.get(language, examples['zh'])

async def quick_generate_story():
    """快速生成单个故事"""
    print("\n🚀 快速生成单个故事")
    print("-" * 30)
    
    # 选择语言
    language = show_language_menu()
    
    # 显示主题示例
    examples = get_theme_examples(language)
    print(f"\n💡 主题示例 ({language}):")
    for i, example in enumerate(examples[:3], 1):
        print(f"   {i}. {example}")
    
    # 输入主题
    print("\n请输入故事主题:")
    theme = input("主题: ").strip()
    
    if not theme:
        print("❌ 主题不能为空")
        return
    
    print(f"\n正在生成故事: {theme}")
    print("语言:", language)
    print("请稍候...")
    
    # 调用main.py生成故事
    import subprocess
    cmd = [sys.executable, 'main.py', '--theme', theme, '--language', language]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✅ 故事生成成功！")
            print("输出信息:")
            print(result.stdout)
        else:
            print("❌ 故事生成失败")
            print("错误信息:")
            print(result.stderr)
    
    except Exception as e:
        print(f"❌ 运行出错: {e}")

def batch_generate_stories():
    """批量生成故事"""
    print("\n📦 批量生成多个故事")
    print("-" * 30)
    
    # 选择语言
    language = show_language_menu()
    
    # 显示可用主题文件
    theme_files = {
        'zh': 'example_themes.txt',
        'en': 'themes_en.txt',
        'es': 'themes_es.txt'
    }
    
    default_file = theme_files.get(language, 'example_themes.txt')
    
    print(f"\n📄 默认主题文件: {default_file}")
    file_path = input(f"主题文件路径 (回车使用默认): ").strip() or default_file
    
    if not Path(file_path).exists():
        print(f"❌ 文件不存在: {file_path}")
        return
    
    # 并发数设置
    concurrent = input("最大并发数 (默认2): ").strip() or "2"
    
    try:
        concurrent = int(concurrent)
        if concurrent < 1 or concurrent > 10:
            raise ValueError("并发数应该在1-10之间")
    except ValueError as e:
        print(f"❌ 无效的并发数: {e}")
        return
    
    print(f"\n开始批量生成...")
    print(f"主题文件: {file_path}")
    print(f"语言: {language}")
    print(f"并发数: {concurrent}")
    print("请稍候...")
    
    # 调用main.py批量生成
    import subprocess
    cmd = [sys.executable, 'main.py', '--batch', file_path, '--language', language, '--concurrent', str(concurrent)]
    
    try:
        result = subprocess.run(cmd, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✅ 批量生成完成！")
        else:
            print("❌ 批量生成出现问题")
    
    except Exception as e:
        print(f"❌ 运行出错: {e}")

def run_test_mode():
    """运行测试模式"""
    print("\n🧪 运行测试模式")
    print("-" * 20)
    
    import subprocess
    cmd = [sys.executable, 'main.py', '--test']
    
    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"❌ 测试运行出错: {e}")

def run_multilang_test():
    """运行多语言测试"""
    print("\n🌍 多语言功能测试")
    print("-" * 25)
    
    import subprocess
    cmd = [sys.executable, 'test_multilang.py']
    
    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"❌ 多语言测试出错: {e}")

def run_system_validation():
    """运行系统验证"""
    print("\n⚙️ 系统配置验证")
    print("-" * 22)
    
    import subprocess
    cmd = [sys.executable, 'validate_setup.py']
    
    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"❌ 系统验证出错: {e}")

def run_performance_analysis():
    """运行性能分析"""
    print("\n📊 性能分析和优化")
    print("-" * 25)
    
    import subprocess
    cmd = [sys.executable, 'optimize.py']
    
    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"❌ 性能分析出错: {e}")

def show_help():
    """显示帮助文档"""
    print("\n📚 帮助文档")
    print("-" * 15)
    print("""
📖 主要文档:
  - README.md          : 项目说明和快速开始
  - DEPLOYMENT.md      : 完整部署指南  
  - PROJECT_SUMMARY.md : 项目技术总结

🔧 配置文件:
  - config/settings.json    : 主配置文件
  - config/themes/         : 多语言主题库
  - config/prompts/        : 多语言提示词模板

🧪 测试工具:
  - test_suite.py          : 综合测试套件
  - test_multilang.py      : 多语言功能测试
  - validate_setup.py      : 系统配置验证
  - optimize.py            : 性能分析工具

🚀 快速命令:
  python main.py --test                    # 运行测试模式
  python main.py --theme "主题" --language zh  # 生成单个故事
  python main.py --batch themes.txt        # 批量生成
  
📧 获取支持:
  - 查看GitHub Issues
  - 阅读详细文档
  - 运行系统验证工具
    """)
    
    input("\n按回车继续...")

def show_advanced_options():
    """显示高级选项"""
    print("\n🔧 高级选项")
    print("-" * 15)
    
    while True:
        print("\n请选择高级功能:")
        print("1. 🧪 运行完整测试套件")
        print("2. 🗑️  清理缓存和临时文件")
        print("3. 📋 查看系统状态")
        print("4. ⚙️  编辑配置文件")
        print("5. 📦 导出项目配置")
        print("0. 🔙 返回主菜单")
        
        choice = input("\n请选择 (0-5): ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            run_full_test_suite()
        elif choice == '2':
            cleanup_files()
        elif choice == '3':
            show_system_status()
        elif choice == '4':
            edit_config()
        elif choice == '5':
            export_config()
        else:
            print("无效选择，请重新输入")

def run_full_test_suite():
    """运行完整测试套件"""
    print("\n🧪 运行完整测试套件")
    print("-" * 25)
    
    import subprocess
    cmd = [sys.executable, 'test_suite.py']
    
    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"❌ 测试套件运行出错: {e}")

def cleanup_files():
    """清理缓存和临时文件"""
    print("\n🗑️ 清理缓存和临时文件")
    print("-" * 30)
    
    import shutil
    
    cleanup_dirs = [
        'output/cache',
        'output/temp',
        'output/temp_cache',
        'output/temp_files'
    ]
    
    cleaned_count = 0
    
    for dir_path in cleanup_dirs:
        if Path(dir_path).exists():
            try:
                shutil.rmtree(dir_path)
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                print(f"✅ 清理完成: {dir_path}")
                cleaned_count += 1
            except Exception as e:
                print(f"❌ 清理失败 {dir_path}: {e}")
    
    print(f"\n清理完成，共处理 {cleaned_count} 个目录")

def show_system_status():
    """显示系统状态"""
    print("\n📋 系统状态")
    print("-" * 15)
    
    # 检查关键文件
    print("📁 文件检查:")
    key_files = ['main.py', 'config/settings.json', 'requirements.txt']
    for file_path in key_files:
        status = "✅" if Path(file_path).exists() else "❌"
        print(f"  {status} {file_path}")
    
    # 检查输出目录
    print("\n📂 输出目录:")
    output_dirs = ['output/scripts', 'output/images', 'output/audio', 'output/videos']
    for dir_path in output_dirs:
        if Path(dir_path).exists():
            file_count = len(list(Path(dir_path).glob('*')))
            print(f"  ✅ {dir_path} ({file_count} 文件)")
        else:
            print(f"  ❌ {dir_path} (不存在)")
    
    # 检查环境变量
    print("\n🔑 环境变量:")
    env_vars = ['OPENROUTER_API_KEY', 'RUNNINGHUB_API_KEY', 'AZURE_API_KEY']
    for var in env_vars:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        print(f"  {status} {var}")

def edit_config():
    """编辑配置文件"""
    print("\n⚙️ 配置文件编辑")
    print("-" * 20)
    
    config_file = Path('config/settings.json')
    
    if not config_file.exists():
        print("❌ 配置文件不存在")
        return
    
    print(f"配置文件路径: {config_file}")
    print("请使用文本编辑器打开并编辑配置文件")
    
    # 尝试用系统默认编辑器打开
    import subprocess
    import platform
    
    try:
        if platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', str(config_file)])
        elif platform.system() == 'Windows':
            subprocess.run(['notepad', str(config_file)])
        else:  # Linux
            subprocess.run(['xdg-open', str(config_file)])
        
        print("✅ 配置文件已在默认编辑器中打开")
    except:
        print(f"请手动编辑文件: {config_file}")

def export_config():
    """导出项目配置"""
    print("\n📦 导出项目配置")
    print("-" * 20)
    
    import json
    from datetime import datetime
    
    export_data = {
        'export_time': datetime.now().isoformat(),
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'project_files': [],
        'environment_variables': {},
        'system_info': {}
    }
    
    # 收集项目文件信息
    for file_path in Path('.').rglob('*.py'):
        if 'venv' not in str(file_path) and '__pycache__' not in str(file_path):
            export_data['project_files'].append(str(file_path))
    
    # 收集环境变量
    env_vars = ['OPENROUTER_API_KEY', 'RUNNINGHUB_API_KEY', 'AZURE_API_KEY', 'ELEVENLABS_API_KEY', 'STABILITY_API_KEY']
    for var in env_vars:
        value = os.getenv(var)
        export_data['environment_variables'][var] = "已设置" if value else "未设置"
    
    # 保存导出文件
    export_file = f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 配置导出完成: {export_file}")
    except Exception as e:
        print(f"❌ 导出失败: {e}")

def main():
    """主函数"""
    print_banner()
    
    # 快速环境检查
    if not check_environment():
        print("\n❌ 环境检查失败，请检查系统配置")
        print("💡 建议运行: python validate_setup.py")
        return
    
    while True:
        show_menu()
        choice = input("\n请选择 (0-8): ").strip()
        
        try:
            if choice == '0':
                print("\n👋 感谢使用历史故事生成器！")
                break
            elif choice == '1':
                asyncio.run(quick_generate_story())
            elif choice == '2':
                batch_generate_stories()
            elif choice == '3':
                run_test_mode()
            elif choice == '4':
                run_multilang_test()
            elif choice == '5':
                run_system_validation()
            elif choice == '6':
                run_performance_analysis()
            elif choice == '7':
                show_help()
            elif choice == '8':
                show_advanced_options()
            else:
                print("❌ 无效选择，请重新输入")
        
        except KeyboardInterrupt:
            print("\n\n⏹️ 操作已中断")
        except Exception as e:
            print(f"\n❌ 操作出错: {e}")
        
        # 暂停，等待用户确认
        if choice != '0':
            input("\n按回车继续...")

if __name__ == "__main__":
    main()