"""
历史故事生成器 - 主程序入口
"""
import asyncio
import argparse
import sys
from pathlib import Path
import logging
import time

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from load_env import load_env_file
load_env_file()

from core.config_manager import ConfigManager
from core.cache_manager import CacheManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from utils.i18n import get_i18n_manager, set_global_language, t
from content.content_pipeline import ContentPipeline, ContentGenerationRequest
from media.media_pipeline import MediaPipeline, MediaGenerationRequest


async def generate_single_story(theme: str, language: str = "zh"):
    """
    生成单个历史故事
    
    Args:
        theme: 故事主题
        language: 语言代码 (zh, en, es)
    """
    try:
        # 设置语言
        set_global_language(language)
        i18n = get_i18n_manager()
        
        # 初始化组件
        logger = setup_logging()
        main_logger = logger.get_logger('story_generator')
        
        main_logger.info(f"Starting story generation: {theme} ({language})")
        
        config = ConfigManager()
        cache = CacheManager()
        files = FileManager()
        
        # 验证配置
        config_errors = config.validate_config()
        if config_errors:
            main_logger.error(f"Configuration errors: {config_errors}")
            return False
        
        # 第一步：生成内容
        main_logger.info("Phase 1: Generating content...")
        content_pipeline = ContentPipeline(config, cache, files)
        
        content_request = ContentGenerationRequest(
            theme=theme,
            language=language,
            style="horror",
            target_length=800,
            target_scene_count=8,
            scene_duration=3.0,
            max_characters=3
        )
        
        content_result = await content_pipeline.generate_content_async(content_request)
        
        main_logger.info(f"Content generated: {content_result.script.word_count} chars, "
                        f"{len(content_result.scenes.scenes)} scenes, "
                        f"{len(content_result.characters.characters)} characters")
        
        # 保存内容文件
        content_files = content_pipeline.save_complete_content(content_result)
        main_logger.info(f"Content files saved: {list(content_files.keys())}")
        
        # 第二步：生成媒体
        main_logger.info("Phase 2: Generating media...")
        media_pipeline = MediaPipeline(config, cache, files)
        
        media_request = MediaGenerationRequest(
            scenes=content_result.scenes.scenes,
            characters=content_result.characters.characters,
            main_character=content_result.characters.main_character,
            language=language,
            script_title=content_result.script.title,
            full_script=content_result.script.content
        )
        
        # 估算成本
        cost_estimate = media_pipeline.estimate_costs(media_request)
        main_logger.info(f"Estimated cost: ${cost_estimate['total']:.2f}")
        
        media_result = await media_pipeline.generate_media_async(media_request)
        
        main_logger.info(f"Media generated: {len(media_result.scene_media)} scene media, "
                        f"{len(media_result.character_images)} character images")
        
        # 保存媒体文件
        media_files = media_pipeline.save_media_files(media_result)
        main_logger.info(f"Media files saved: {media_files['manifest']}")
        
        # 输出完成信息
        total_time = content_result.total_processing_time + media_result.total_processing_time
        main_logger.info(f"Story generation completed in {total_time:.2f}s")
        main_logger.info(f"Output files:")
        main_logger.info(f"  - Content: {content_files.get('summary', 'N/A')}")
        main_logger.info(f"  - Media: {media_files.get('manifest', 'N/A')}")
        
        return True
        
    except Exception as e:
        main_logger.error(f"Story generation failed: {e}")
        return False


async def batch_generate_stories(themes_file: str, language: str = "zh", max_concurrent: int = 2):
    """
    批量生成历史故事
    
    Args:
        themes_file: 主题列表文件路径
        language: 语言代码
        max_concurrent: 最大并发数
    """
    try:
        logger = setup_logging()
        main_logger = logger.get_logger('story_generator.batch')
        
        # 读取主题列表
        themes_path = Path(themes_file)
        if not themes_path.exists():
            main_logger.error(f"Themes file not found: {themes_file}")
            return False
        
        with open(themes_path, 'r', encoding='utf-8') as f:
            themes = [line.strip() for line in f if line.strip()]
        
        if not themes:
            main_logger.error("No themes found in file")
            return False
        
        main_logger.info(f"Starting batch generation: {len(themes)} stories, max_concurrent={max_concurrent}")
        
        # 使用信号量限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(theme):
            async with semaphore:
                return await generate_single_story(theme, language)
        
        # 并发执行
        tasks = [generate_with_semaphore(theme) for theme in themes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful
        
        main_logger.info(f"Batch generation completed: {successful} successful, {failed} failed")
        
        return successful > 0
        
    except Exception as e:
        main_logger.error(f"Batch generation failed: {e}")
        return False


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="历史故事生成器")
    
    parser.add_argument("--theme", type=str, help="故事主题")
    parser.add_argument("--language", type=str, default="zh", choices=["zh", "en", "es"], 
                       help="语言代码 (默认: zh)")
    parser.add_argument("--batch", type=str, help="批量生成，指定主题文件路径")
    parser.add_argument("--concurrent", type=int, default=2, help="批量生成时的最大并发数 (默认: 2)")
    parser.add_argument("--test", action="store_true", help="测试模式，生成示例故事")
    
    args = parser.parse_args()
    
    if args.test:
        # 测试模式
        test_themes = [
            "秦始皇统一六国的传奇故事",
            "汉武帝开疆拓土的辉煌历史", 
            "唐太宗贞观之治的盛世传奇"
        ]
        print("测试模式 - 生成示例故事:")
        for i, theme in enumerate(test_themes, 1):
            print(f"{i}. {theme}")
            success = asyncio.run(generate_single_story(theme, args.language))
            if success:
                print(f"✅ 故事 {i} 生成成功")
            else:
                print(f"❌ 故事 {i} 生成失败")
            print()
    
    elif args.batch:
        # 批量生成
        success = asyncio.run(batch_generate_stories(args.batch, args.language, args.concurrent))
        if success:
            print("✅ 批量生成完成")
        else:
            print("❌ 批量生成失败")
    
    elif args.theme:
        # 单个生成
        success = asyncio.run(generate_single_story(args.theme, args.language))
        if success:
            print("✅ 故事生成成功")
        else:
            print("❌ 故事生成失败")
    
    else:
        # 交互式模式
        print("历史故事生成器 v1.0.0")
        print("=" * 50)
        
        while True:
            print("\n请选择操作：")
            print("1. 生成单个故事")
            print("2. 批量生成故事")
            print("3. 查看配置信息")
            print("4. 退出")
            
            choice = input("请输入选择 (1-4): ").strip()
            
            if choice == "1":
                theme = input("请输入故事主题: ").strip()
                language = input("请输入语言 (zh/en/es，默认zh): ").strip() or "zh"
                
                if theme:
                    print(f"正在生成故事: {theme}")
                    success = asyncio.run(generate_single_story(theme, language))
                    if success:
                        print("✅ 故事生成成功")
                    else:
                        print("❌ 故事生成失败")
                else:
                    print("主题不能为空")
            
            elif choice == "2":
                batch_file = input("请输入主题文件路径: ").strip()
                language = input("请输入语言 (zh/en/es，默认zh): ").strip() or "zh"
                concurrent = input("请输入最大并发数 (默认2): ").strip() or "2"
                
                try:
                    concurrent = int(concurrent)
                    print(f"正在批量生成故事...")
                    success = asyncio.run(batch_generate_stories(batch_file, language, concurrent))
                    if success:
                        print("✅ 批量生成完成")
                    else:
                        print("❌ 批量生成失败")
                except ValueError:
                    print("并发数必须是数字")
            
            elif choice == "3":
                try:
                    config = ConfigManager()
                    cache = CacheManager()
                    print("\n配置信息:")
                    print(f"支持的语言: {config.get_supported_languages()}")
                    print(f"输出目录: {config.get('general.output_dir')}")
                    print(f"缓存统计: {cache.get_cache_stats()}")
                except Exception as e:
                    print(f"获取配置信息失败: {e}")
            
            elif choice == "4":
                print("再见！")
                break
            
            else:
                print("无效选择，请重新输入")


if __name__ == "__main__":
    main()