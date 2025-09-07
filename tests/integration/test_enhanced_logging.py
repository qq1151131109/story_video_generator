#!/usr/bin/env python3
"""
增强型日志系统测试脚本
验证新日志系统的各项功能
"""
import asyncio
import time
import json
import sys
from pathlib import Path

# 添加项目根路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 导入增强日志系统
from utils.enhanced_logger import setup_enhanced_logging
from core.config_manager import ConfigManager

def test_basic_logging():
    """测试基础日志功能"""
    print("🧪 测试1: 基础日志功能")
    
    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.config
    
    # 初始化日志系统
    log_manager = setup_enhanced_logging(config)
    logger = log_manager.get_logger('test_component')
    
    # 测试各级别日志
    logger.debug("这是DEBUG日志 - 应该只在文件中看到")
    logger.info("这是INFO日志 - 控制台和文件都有")
    logger.warning("这是WARNING日志 - 应该高亮显示")
    logger.error("这是ERROR日志 - 应该记录到errors.log")
    
    print("✅ 基础日志测试完成")

def test_structured_logging():
    """测试结构化日志"""
    print("\n🧪 测试2: 结构化日志")
    
    config_manager = ConfigManager()
    log_manager = setup_enhanced_logging(config_manager.config)
    logger = log_manager.get_logger('structured_test')
    
    # 测试结构化日志
    logger.info("测试结构化日志输出")
    
    # 检查日志文件内容
    log_file = Path("output/logs/story_generator.log")
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            last_line = f.readlines()[-1]
            try:
                log_data = json.loads(last_line)
                print(f"✅ 结构化日志格式正确: {list(log_data.keys())}")
            except json.JSONDecodeError:
                print("❌ 日志格式不是有效的JSON")
    
    print("✅ 结构化日志测试完成")

def test_performance_tracking():
    """测试性能追踪"""
    print("\n🧪 测试3: 性能追踪")
    
    config_manager = ConfigManager()
    log_manager = setup_enhanced_logging(config_manager.config)
    logger = log_manager.get_logger('performance_test')
    
    # 测试性能追踪
    with log_manager.performance_tracker(logger, 'test_operation'):
        time.sleep(0.1)  # 模拟耗时操作
        print("  执行了一个耗时操作")
    
    # 检查性能日志
    perf_log = Path("output/logs/performance.log")
    if perf_log.exists():
        print("✅ 性能日志文件已创建")
    
    print("✅ 性能追踪测试完成")

def test_error_handling():
    """测试错误处理"""
    print("\n🧪 测试4: 错误处理和聚合")
    
    config_manager = ConfigManager()
    log_manager = setup_enhanced_logging(config_manager.config)
    logger = log_manager.get_logger('error_test')
    
    # 测试错误记录
    try:
        raise ValueError("这是一个测试错误")
    except Exception as e:
        log_manager.log_error_with_context(
            logger, e, 
            context={'test_id': '12345', 'operation': 'test_error_handling'}
        )
    
    # 生成多个相同错误来测试聚合
    for i in range(3):
        try:
            raise ConnectionError("API连接失败")
        except Exception as e:
            log_manager.log_error_with_context(logger, e)
    
    # 获取错误摘要
    error_summary = log_manager.get_error_summary()
    print(f"✅ 错误统计: {error_summary}")
    
    # 检查错误日志文件
    error_log = Path("output/logs/errors.log")
    if error_log.exists() and error_log.stat().st_size > 0:
        print("✅ 错误日志文件已创建并有内容")
    else:
        print("❌ 错误日志文件为空或不存在")
    
    print("✅ 错误处理测试完成")

def test_api_logging():
    """测试API调用日志"""
    print("\n🧪 测试5: API调用日志")
    
    config_manager = ConfigManager()
    log_manager = setup_enhanced_logging(config_manager.config)
    logger = log_manager.get_logger('api_test')
    
    # 测试成功的API调用
    log_manager.log_api_call(
        logger, 
        'POST', 
        'https://api.openai.com/v1/chat/completions?api_key=sk-xxx', 
        status_code=200,
        response_time=1.23
    )
    
    # 测试失败的API调用
    log_manager.log_api_call(
        logger,
        'POST',
        'https://api.runninghub.cn/workflow',
        status_code=401,
        response_time=0.56,
        error='Unauthorized: Invalid API key'
    )
    
    print("✅ API调用日志测试完成")

def test_sensitive_masking():
    """测试敏感信息掩码"""
    print("\n🧪 测试6: 敏感信息掩码")
    
    config_manager = ConfigManager()
    log_manager = setup_enhanced_logging(config_manager.config)
    logger = log_manager.get_logger('mask_test')
    
    # 记录包含敏感信息的日志
    logger.info("使用API密钥: sk-proj-abcdefg123456789")
    logger.info("密码: password123")
    logger.info("认证令牌: token_xyz789")
    
    print("✅ 敏感信息掩码测试完成（检查日志文件确认掩码效果）")

def check_log_files():
    """检查生成的日志文件"""
    print("\n📁 检查生成的日志文件:")
    
    log_dir = Path("output/logs")
    expected_files = [
        'story_generator.log',
        'errors.log', 
        'performance.log'
    ]
    
    for filename in expected_files:
        log_file = log_dir / filename
        if log_file.exists():
            size = log_file.stat().st_size
            print(f"  ✅ {filename}: {size} bytes")
        else:
            print(f"  ❌ {filename}: 不存在")

def cleanup_test_logs():
    """清理测试日志"""
    print("\n🧹 是否清理测试日志? (y/n): ", end="")
    response = input().lower().strip()
    
    if response in ['y', 'yes']:
        log_dir = Path("output/logs")
        cleaned = 0
        for log_file in log_dir.glob("*.log*"):
            try:
                log_file.unlink()
                cleaned += 1
            except Exception:
                pass
        print(f"✅ 已清理 {cleaned} 个日志文件")

def main():
    """主测试函数"""
    print("🚀 开始测试增强型日志系统")
    print("=" * 50)
    
    try:
        test_basic_logging()
        test_structured_logging() 
        test_performance_tracking()
        test_error_handling()
        test_api_logging()
        test_sensitive_masking()
        
        print("\n" + "=" * 50)
        print("📊 测试总结:")
        check_log_files()
        
        print("\n✅ 所有测试完成!")
        
        cleanup_test_logs()
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()