"""
多语言功能测试脚本
"""
import asyncio
import sys
from pathlib import Path
import time

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.i18n import get_i18n_manager, set_global_language, t
from utils.logger import setup_logging
from content.content_pipeline import ContentPipeline, ContentGenerationRequest


async def test_single_language(language: str):
    """测试单一语言的内容生成"""
    print(f"\n{'='*60}")
    print(f"测试语言: {language}")
    print(f"{'='*60}")
    
    # 设置全局语言
    set_global_language(language)
    i18n = get_i18n_manager()
    
    # 显示语言信息
    lang_info = i18n.get_language_info(language)
    print(f"语言名称: {lang_info['name']} ({lang_info['english_name']})")
    
    # 测试本地化消息
    print(f"成功消息: {t('common', 'success')}")
    print(f"处理中消息: {t('common', 'processing')}")
    print(f"生成文案消息: {t('content', 'generating_script')}")
    
    # 初始化组件
    logger = setup_logging()
    config = ConfigManager()
    cache = CacheManager()
    files = FileManager()
    
    # 选择测试主题
    test_themes = {
        'zh': "秦始皇统一六国的传奇故事",
        'en': "The legendary story of Emperor Qin Shi Huang unifying the six kingdoms", 
        'es': "La historia legendaria del Emperador Qin Shi Huang unificando los seis reinos"
    }
    
    theme = test_themes.get(language, test_themes['zh'])
    print(f"测试主题: {theme}")
    
    try:
        # 创建内容生成流水线
        content_pipeline = ContentPipeline(config, cache, files)
        
        print(f"\n{t('content', 'generating_script')}...")
        start_time = time.time()
        
        # 生成内容请求
        request = ContentGenerationRequest(
            theme=theme,
            language=language,
            style="horror",
            target_length=500,  # 减少长度以加快测试
            target_scene_count=5,  # 减少场景数量
            scene_duration=3.0,
            max_characters=2  # 减少角色数量
        )
        
        # 生成内容
        result = await content_pipeline.generate_content_async(request)
        
        generation_time = time.time() - start_time
        
        # 显示结果
        print(f"\n{t('content', 'script_generated')}!")
        print(f"标题: {result.script.title}")
        print(f"字数: {result.script.word_count}")
        print(f"场景数: {len(result.scenes.scenes)}")
        print(f"角色数: {len(result.characters.characters)}")
        print(f"生成时间: {i18n.format_time_duration(generation_time)}")
        
        # 显示生成的内容摘要
        print(f"\n内容预览:")
        print(f"文案: {result.script.content[:100]}...")
        
        print(f"\n场景列表:")
        for i, scene in enumerate(result.scenes.scenes[:3], 1):
            print(f"  {i}. {scene.content[:50]}...")
        
        if result.characters.characters:
            print(f"\n角色列表:")
            for char in result.characters.characters:
                print(f"  - {char.name}: {char.role}")
        
        return True
        
    except Exception as e:
        print(f"\n{t('errors', 'config_error', error=str(e))}")
        return False


async def test_multilanguage_batch():
    """测试多语言批量处理"""
    print(f"\n{'='*60}")
    print(f"多语言批量测试")
    print(f"{'='*60}")
    
    languages = ['zh', 'en', 'es']
    results = {}
    
    for language in languages:
        print(f"\n正在测试 {language}...")
        success = await test_single_language(language)
        results[language] = success
        
        # 添加延迟避免API限制
        if language != languages[-1]:
            print(f"等待 2 秒...")
            await asyncio.sleep(2)
    
    # 总结结果
    print(f"\n{'='*60}")
    print(f"批量测试结果")
    print(f"{'='*60}")
    
    for language, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        i18n = get_i18n_manager()
        lang_info = i18n.get_language_info(language)
        print(f"{lang_info['name']:>8}: {status}")
    
    success_count = sum(results.values())
    print(f"\n总计: {success_count}/{len(languages)} 成功")


def test_i18n_features():
    """测试国际化功能"""
    print(f"\n{'='*60}")
    print(f"国际化功能测试")
    print(f"{'='*60}")
    
    i18n = get_i18n_manager()
    
    # 测试语言切换
    for language in ['zh', 'en', 'es']:
        print(f"\n语言: {language}")
        i18n.set_language(language)
        
        # 测试各种消息类型
        print(f"  通用消息: {t('common', 'success')}")
        print(f"  内容消息: {t('content', 'generating_script')}")
        print(f"  媒体消息: {t('media', 'generating_image')}")
        print(f"  错误消息: {t('errors', 'api_key_missing', service='TestAPI')}")
    
    # 测试格式化功能
    print(f"\n格式化功能测试:")
    print(f"时间格式化 (65秒): {i18n.format_time_duration(65)}")
    print(f"时间格式化 (3665秒): {i18n.format_time_duration(3665)}")
    print(f"文件大小 (1536字节): {i18n.format_file_size(1536)}")
    print(f"文件大小 (2097152字节): {i18n.format_file_size(2097152)}")
    
    # 测试语言检测
    test_texts = [
        "这是一个中文测试文本",
        "This is an English test text",
        "Este es un texto de prueba en español"
    ]
    
    print(f"\n语言检测测试:")
    for text in test_texts:
        detected = i18n.detect_language_from_text(text)
        print(f"  '{text}' -> {detected}")


def test_theme_files():
    """测试主题文件"""
    print(f"\n{'='*60}")
    print(f"主题文件测试")
    print(f"{'='*60}")
    
    theme_files = {
        'zh': 'example_themes.txt',
        'en': 'themes_en.txt', 
        'es': 'themes_es.txt'
    }
    
    for language, filename in theme_files.items():
        print(f"\n语言: {language} - 文件: {filename}")
        
        file_path = Path(__file__).parent / filename
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                themes = [line.strip() for line in f if line.strip()]
            
            print(f"  主题数量: {len(themes)}")
            print(f"  示例主题:")
            for i, theme in enumerate(themes[:3], 1):
                print(f"    {i}. {theme}")
            
            # 验证主题语言匹配
            i18n = get_i18n_manager()
            matching_themes = [theme for theme in themes 
                             if i18n.validate_theme_translation(theme, language)]
            print(f"  语言匹配率: {len(matching_themes)}/{len(themes)} ({len(matching_themes)/len(themes)*100:.1f}%)")
        else:
            print(f"  文件不存在: {filename}")


async def main():
    """主测试函数"""
    print("历史故事生成器 - 多语言功能测试")
    print("=" * 60)
    
    # 1. 测试国际化基础功能
    test_i18n_features()
    
    # 2. 测试主题文件
    test_theme_files()
    
    # 3. 询问是否进行实际内容生成测试
    print(f"\n是否进行实际内容生成测试？(需要API密钥)")
    choice = input("输入 'y' 继续，其他任意键跳过: ").strip().lower()
    
    if choice == 'y':
        # 4. 测试单语言内容生成
        test_language = input("选择测试语言 (zh/en/es，默认zh): ").strip() or 'zh'
        await test_single_language(test_language)
        
        # 5. 询问是否进行批量测试
        batch_choice = input("\n是否进行多语言批量测试？(y/N): ").strip().lower()
        if batch_choice == 'y':
            await test_multilanguage_batch()
    
    print(f"\n测试完成！")


if __name__ == "__main__":
    asyncio.run(main())