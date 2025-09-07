#!/usr/bin/env python3
"""
快速测试 - 使用现有的API密钥测试系统
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from tools.load_env import load_env_file
load_env_file(verbose=True)  # 启用详细输出用于调试

from content.scene_splitter import SceneSplitter, SceneSplitRequest
from core.config_manager import ConfigManager
from utils.file_manager import FileManager

async def quick_test():
    """快速测试系统是否正常工作"""
    print("🧪 快速测试系统...")
    
    try:
        # 检查API密钥
        openrouter_key = os.getenv('OPENROUTER_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        
        print(f"OPENROUTER_API_KEY: {'已设置' if openrouter_key else '❌ 未设置'}")
        print(f"OPENAI_API_KEY: {'已设置' if openai_key else '❌ 未设置'}")
        
        # 初始化组件
        print("\n初始化组件...")
        config = ConfigManager()
        file_mgr = FileManager('output', 'output/temp')
        
        # 创建场景分割器
        splitter = SceneSplitter(config, file_mgr)
        
        # 简单的中文测试
        print("\n🎬 测试中文场景分割...")
        request = SceneSplitRequest(
            script_content="""
            这是一个关于古代英雄的故事。英雄从小就展现出非凡的勇气，经常帮助村民解决各种困难。
            他决心成为保卫家园的战士，开始了艰苦的训练。在山中的道场，他跟随老师学习剑法和武艺。
            经过多年的努力，他的武艺已经炉火纯青。当邪恶的敌人入侵时，他挺身而出迎接挑战。
            在激烈的战斗中，他运用所学的武艺，与敌人展开殊死搏斗。最终他战胜了邪恶的敌人，拯救了村庄。
            村民们为英雄的勇敢行为欢呼，他的名字被传颂至今。从此，村庄重新获得了和平与繁荣。
            """,
            language='zh',
            target_scene_count=8  # 增加到8个场景以满足验证要求
        )
        
        # 执行测试
        result = await splitter.split_scenes_async(request)
        
        if result and result.scenes:
            print(f"✅ 测试成功！生成了 {len(result.scenes)} 个场景")
            print(f"使用模型: {result.model_used}")
            print(f"处理时间: {result.split_time:.2f}秒")
            
            # 显示场景
            for i, scene in enumerate(result.scenes):
                print(f"  场景{i+1}: {scene.content[:50]}...")
                
            return True
        else:
            print("❌ 测试失败：没有生成场景")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_enhanced_manager():
    """测试增强LLM管理器"""
    print("\n🚀 测试增强LLM管理器...")
    
    try:
        from utils.enhanced_llm_manager import EnhancedLLMManager
        
        config = ConfigManager()
        manager = EnhancedLLMManager(config)
        
        info = manager.get_model_info()
        print("📊 管理器状态:")
        for key, value in info.items():
            print(f"   {key}: {value}")
            
        # 如果有可用的LLM，测试结构化输出
        if info['structured_output_enabled'] or info['retry_parser_enabled']:
            print("\n🎯 测试结构化输出...")
            result = await manager.generate_structured_output(
                task_type='scene_splitting',
                system_prompt='你是专业的场景分割专家',
                user_prompt='将以下故事分成3个场景：一个英雄的冒险故事'
            )
            print(f"✅ 结构化输出成功: {type(result).__name__}")
            if hasattr(result, 'scenes'):
                print(f"   生成场景数: {len(result.scenes)}")
            return True
        else:
            print("⚠️ 没有可用的LLM提供商")
            return False
            
    except Exception as e:
        print(f"❌ 增强管理器测试失败: {e}")
        return False

def print_api_setup_guide():
    """打印API设置指南"""
    print("\n" + "="*60)
    print("🔧 API密钥设置指南")
    print("="*60)
    
    print("\n方案1: 使用OpenRouter (推荐)")
    print("export OPENROUTER_API_KEY='your_openrouter_key'")
    print("export OPENROUTER_BASE_URL='https://openrouter.ai/api/v1'")
    
    print("\n方案2: 使用现有OpenAI密钥")
    print("# 您已有OPENAI_API_KEY，系统会自动使用")
    
    print("\n方案3: 测试模式")
    print("# 系统会尝试使用所有可用的API密钥")
    
    print("\n🚀 启动命令:")
    print("python quick_test.py  # 测试系统")
    print("python main.py        # 正式运行")

async def main():
    """主函数"""
    print("🧪 系统诊断和测试")
    print("="*50)
    
    # 测试增强管理器
    manager_ok = await test_enhanced_manager()
    
    # 测试场景分割
    if manager_ok:
        splitter_ok = await quick_test()
        
        if splitter_ok:
            print(f"\n🎉 系统工作正常！")
            print("您可以使用 python main.py 开始正式生成")
        else:
            print(f"\n⚠️ 场景分割器需要调试")
    else:
        print(f"\n⚠️ LLM管理器需要配置")
    
    # 显示配置指南
    print_api_setup_guide()

if __name__ == "__main__":
    asyncio.run(main())