#!/usr/bin/env python3
"""
测试数据模型修复
验证结构化输出模型的验证规则是否正确
"""

import sys
from pathlib import Path
import json

# 添加项目根路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_script_generation_model():
    """测试ScriptGenerationOutput模型"""
    try:
        from utils.structured_output_models import ScriptGenerationOutput
        
        # 测试正常长度内容
        normal_content = "This is a test story content. " * 100  # ~3000字符
        
        try:
            model = ScriptGenerationOutput(
                title="Test Story",
                content=normal_content,
                theme="Test Theme"
            )
            print(f"✅ 正常长度内容通过 ({len(normal_content)} 字符)")
        except Exception as e:
            print(f"❌ 正常长度内容失败: {e}")
            return False
        
        # 测试更长的内容（现在应该支持10000字符）
        long_content = "This is a longer test story content. " * 200  # ~7400字符
        
        try:
            model = ScriptGenerationOutput(
                title="Long Test Story",
                content=long_content,
                theme="Test Theme"
            )
            print(f"✅ 长内容通过 ({len(long_content)} 字符)")
        except Exception as e:
            print(f"❌ 长内容失败: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ ScriptGenerationOutput 测试失败: {e}")
        return False

def test_character_analysis_model():
    """测试CharacterAnalysisOutput模型"""
    try:
        from utils.structured_output_models import CharacterAnalysisOutput, CharacterModel
        
        # 创建测试角色（符合最小长度要求）
        character = CharacterModel(
            name="Test Character",
            description="A test character with detailed description for testing purposes",
            image_prompt="A detailed test prompt for image generation that meets the minimum length requirement of 20 characters"
        )
        
        # 测试字符串格式的main_character
        try:
            model = CharacterAnalysisOutput(
                characters=[character],
                main_character="Test Character"
            )
            print("✅ 字符串格式main_character通过")
        except Exception as e:
            print(f"❌ 字符串格式main_character失败: {e}")
            return False
        
        # 测试字典格式的main_character（应该被转换）
        try:
            model = CharacterAnalysisOutput(
                characters=[character],
                main_character={"name": "Test Character", "description": "Main character"}
            )
            print("✅ 字典格式main_character通过转换")
            print(f"   转换后: {model.main_character}")
        except Exception as e:
            print(f"❌ 字典格式main_character失败: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ CharacterAnalysisOutput 测试失败: {e}")
        return False

def test_compatibility_adapter():
    """测试兼容性适配器的JSON转换"""
    try:
        from utils.structured_output_models import ScriptGenerationOutput
        
        # 创建模型实例（符合最小长度要求）
        model = ScriptGenerationOutput(
            title="Test Story",
            content="Test content for JSON conversion that meets the minimum length requirement of 100 characters for proper testing and validation of the model functionality and JSON serialization capabilities.",
            theme="Test Theme"
        )
        
        # 测试model_dump方法
        if hasattr(model, 'model_dump'):
            print("✅ 模型有 model_dump 方法")
            
            # 测试JSON转换
            import json
            json_str = json.dumps(model.model_dump(), ensure_ascii=False, indent=2)
            print(f"✅ JSON转换成功 ({len(json_str)} 字符)")
            
            # 验证JSON可以被解析回来
            parsed_data = json.loads(json_str)
            if 'title' in parsed_data and 'content' in parsed_data:
                print("✅ JSON结构正确")
            else:
                print("❌ JSON结构不正确")
                return False
        else:
            print("❌ 模型没有 model_dump 方法")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 兼容性适配器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🔧 数据模型修复验证")
    print("目标: 验证结构化输出模型能正确处理LLM返回数据")
    print("=" * 60)
    
    tests = [
        ("脚本生成模型", test_script_generation_model),
        ("角色分析模型", test_character_analysis_model),
        ("兼容性适配器", test_compatibility_adapter)
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
        print(f"\n🎉 数据模型修复成功！")
        print(f"✅ ScriptGenerationOutput 支持更长内容")
        print(f"✅ CharacterAnalysisOutput 支持字典格式main_character")
        print(f"✅ 兼容性适配器能正确转换JSON")
        print(f"\n💡 现在再次运行 python main.py 应该能解决数据格式问题")
    elif success_rate >= 70:
        print(f"\n✅ 数据模型基本修复")
        print(f"大部分问题已解决，少数需要进一步调试")
    else:
        print(f"\n⚠️ 数据模型需要进一步修复")

if __name__ == "__main__":
    main()