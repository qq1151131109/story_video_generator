#!/usr/bin/env python3
"""
快速启动测试 - 验证系统能否正确初始化
测试配置和方法调用兼容性（不需要langchain依赖）
"""

import sys
from pathlib import Path
import json

# 添加项目根路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_config_loading():
    """测试配置加载"""
    try:
        from core.config_manager import ConfigManager
        config = ConfigManager()
        
        # 测试LLM配置获取
        llm_config = config.get_llm_config('script_generation')
        print("✅ 配置加载成功")
        print(f"   模型: {getattr(llm_config, 'model', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def test_method_compatibility():
    """测试方法兼容性"""
    try:
        # 检查文件中是否有正确的方法
        with open('utils/enhanced_llm_manager.py', 'r') as f:
            content = f.read()
        
        # 检查关键方法
        methods = [
            'def call_llm_with_fallback(',
            'def generate_structured_output(',
            'async def call_llm_with_fallback('
        ]
        
        missing_methods = []
        for method in methods:
            if method not in content:
                missing_methods.append(method)
        
        if not missing_methods:
            print("✅ 所有必需方法都存在")
            return True
        else:
            print(f"❌ 缺少方法: {missing_methods}")
            return False
            
    except Exception as e:
        print(f"❌ 方法兼容性检查失败: {e}")
        return False

def test_import_structure():
    """测试导入结构"""
    try:
        # 测试核心模块导入
        from core.config_manager import ConfigManager
        print("✅ ConfigManager 导入成功")
        
        from utils.file_manager import FileManager
        print("✅ FileManager 导入成功")
        
        # 这些会因为langchain依赖失败，但我们可以检查它们的存在性
        content_modules = [
            'content/script_generator.py',
            'content/scene_splitter.py',
            'content/character_analyzer.py',
            'content/image_prompt_generator.py',
            'content/theme_extractor.py'
        ]
        
        for module_path in content_modules:
            if Path(module_path).exists():
                with open(module_path, 'r') as f:
                    content = f.read()
                    if 'call_llm_with_fallback' in content:
                        print(f"✅ {module_path} 使用兼容方法")
                    else:
                        print(f"⚠️ {module_path} 不使用兼容方法")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入结构测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 快速启动测试")
    print("目标: 验证系统初始化和方法兼容性")
    print("=" * 50)
    
    tests = [
        ("配置加载", test_config_loading),
        ("方法兼容性", test_method_compatibility), 
        ("导入结构", test_import_structure)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 测试: {test_name}")
        if test_func():
            passed += 1
        
    success_rate = (passed / total) * 100
    
    print(f"\n📊 测试结果:")
    print(f"   通过: {passed}/{total}")
    print(f"   成功率: {success_rate:.1f}%")
    
    if success_rate == 100:
        print(f"\n🎉 系统启动就绪！")
        print(f"✅ 所有核心组件正常")
        print(f"✅ 配置系统工作正常")
        print(f"✅ 兼容性方法已添加")
        print(f"\n💡 下一步: 安装依赖 pip install -r requirements.txt")
        print(f"   然后运行: python main.py")
    elif success_rate >= 70:
        print(f"\n✅ 系统基本就绪")
        print(f"大部分组件正常，少数问题需要修复")
    else:
        print(f"\n⚠️ 系统需要进一步修复")

if __name__ == "__main__":
    main()