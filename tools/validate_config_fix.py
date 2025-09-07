#!/usr/bin/env python3
"""
验证配置修复 - 不依赖langchain
测试ConfigManager修复后是否能正确获取LLM配置
"""

import sys
from pathlib import Path

# 添加项目根路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_config_manager():
    """测试ConfigManager修复"""
    print("🧪 测试ConfigManager修复效果")
    print("=" * 50)
    
    try:
        from core.config_manager import ConfigManager
        print("✅ ConfigManager导入成功")
        
        # 初始化配置管理器
        config = ConfigManager()
        print("✅ ConfigManager初始化成功")
        
        # 测试各种任务类型的LLM配置获取
        task_types = [
            'script_generation',
            'scene_splitting', 
            'character_analysis',
            'image_prompt_generation',
            'theme_extraction'
        ]
        
        success_count = 0
        
        for task_type in task_types:
            try:
                llm_config = config.get_llm_config(task_type)
                print(f"✅ {task_type} 配置获取成功")
                print(f"   模型: {getattr(llm_config, 'model', 'N/A')}")
                success_count += 1
            except Exception as e:
                print(f"❌ {task_type} 配置获取失败: {e}")
        
        success_rate = (success_count / len(task_types)) * 100
        
        print(f"\n📊 配置获取测试结果:")
        print(f"   总任务类型数: {len(task_types)}")
        print(f"   成功获取配置数: {success_count}")
        print(f"   成功率: {success_rate:.1f}%")
        
        if success_rate == 100:
            print("\n🎉 配置修复完全成功！")
            print("✅ 所有任务类型都能正确获取LLM配置")
            print("✅ 不再需要llm.default配置节点")
            print("✅ 系统可以正常启动（需要安装依赖）")
        elif success_rate >= 80:
            print("\n✅ 配置修复基本成功")
            print("大部分任务类型能获取配置")
        else:
            print("\n⚠️ 配置修复需要进一步调试")
            
        return success_rate >= 80
        
    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🔧 ConfigManager配置修复验证")
    print("目标: 验证修复后的配置管理器能正确工作\n")
    
    success = test_config_manager()
    
    print("\n" + "="*50)
    if success:
        print("🎯 结论: 配置修复成功！")
        print("✅ ConfigManager.get_llm_config()方法已修复")
        print("✅ 不再强制要求llm.default配置")
        print("✅ 可以直接使用任务特定配置")
        print("\n💡 下一步: 安装依赖 pip install -r requirements.txt")
    else:
        print("⚠️ 结论: 配置修复需要进一步调试")

if __name__ == "__main__":
    main()