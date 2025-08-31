"""
历史故事生成器 - 主程序入口
"""
import asyncio
import argparse
import sys
from pathlib import Path
import logging
import time
import json
from typing import Dict, List, Any
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量 - 静默加载防止输出污染
from tools.load_env import load_env_file
load_env_file(verbose=False)  # 静默加载

from utils.i18n import get_i18n_manager, set_global_language, t
from content.content_pipeline import ContentPipeline, ContentGenerationRequest
from media.media_pipeline import MediaPipeline, MediaGenerationRequest
from services.story_video_service import StoryVideoService


# 注意：原_format_time函数已移至SubtitleUtils工具类
# 注意：_fallback_to_tts_timestamps 函数已整合到 SubtitleAlignmentManager 中


async def generate_single_story(theme: str, language: str = "zh"):
    """
    生成单个历史故事 - 使用服务化架构
    
    Args:
        theme: 故事主题
        language: 语言代码 (zh, en, es)
    """
    try:
        # 设置语言
        set_global_language(language)
        i18n = get_i18n_manager()
        
        # 初始化服务
        service = StoryVideoService()
        
        service.logger.info(f"Starting story generation: {theme} ({language})")
        
        # 第一步：生成内容
        service.logger.info("Phase 1: Generating content...")
        
        content_request = ContentGenerationRequest(
            theme=theme,
            language=language,
            style="horror",
            target_length=800,
            target_scene_count=8,
            scene_duration=3.0,
            max_characters=3
        )
        
        content_result = await service.content_pipeline.generate_content_async(content_request)
        
        service.logger.info(f"Content generated: {content_result.script.word_count} chars, "
                        f"{len(content_result.scenes.scenes)} scenes, "
                        f"{len(content_result.characters.characters)} characters")
        
        # 保存内容文件
        content_files = service.content_pipeline.save_complete_content(content_result)
        service.logger.info(f"Content files saved: {list(content_files.keys())}")
        
        # 第二步：生成媒体
        service.logger.info("Phase 2: Generating media...")
        
        media_request = MediaGenerationRequest(
            scenes=content_result.scenes.scenes,
            characters=content_result.characters.characters,
            main_character=content_result.characters.main_character,
            language=language,
            script_title=content_result.script.title,
            full_script=content_result.script.content
        )
        
        # 估算成本
        cost_estimate = service.media_pipeline.estimate_costs(media_request)
        service.logger.info(f"Estimated cost: ${cost_estimate['total']:.2f}")
        
        media_result = await service.media_pipeline.generate_media_async(media_request)
        
        service.logger.info(f"Media generated: {len(media_result.scene_media)} scene media, "
                        f"{len(media_result.character_images)} character images")
        
        # 保存媒体文件
        media_files = service.media_pipeline.save_media_files(media_result)
        service.logger.info(f"Media files saved: {media_files['manifest']}")
        
        # 第三步：合成最终视频
        service.logger.info("Phase 3: Composing final video...")
        
        # 准备场景图像列表
        images = []
        for scene_media in media_result.scene_media:
            images.append(scene_media.image)
        
        # 为完整脚本生成单一音频文件（使用服务类）
        audio_result = await service.generate_complete_audio(content_result.script.content, language)
        
        if audio_result['success']:
            main_audio_file = audio_result['audio_file']
            full_audio_result = audio_result['audio_result']
            
            # 使用服务类处理字幕对齐
            subtitle_result = await service.process_subtitle_alignment(
                main_audio_file,
                content_result.script.content,
                full_audio_result.subtitles,
                language
            )
            
            if subtitle_result['success']:
                all_subtitle_segments = subtitle_result['segments']
            else:
                all_subtitle_segments = []
        else:
            main_audio_file = None
            full_audio_result = None
            all_subtitle_segments = []
        
        # 生成输出路径（使用服务类）
        output_paths = service.generate_output_paths(theme)
        output_video = output_paths['video_path']
        
        # 保存字幕文件（使用服务类）
        saved_subtitle_path = service.save_subtitle_file(all_subtitle_segments, theme)
        
        # 合成最终视频（使用服务类）
        video_path = await service.compose_final_video(
            scenes=content_result.scenes.scenes,
            images=images,
            audio_file=main_audio_file,
            subtitle_file=saved_subtitle_path,
            output_path=str(output_video),
            audio_duration=full_audio_result.duration_seconds if full_audio_result else None
        )
        
        # 输出完成信息（使用服务类）
        service.log_completion_summary(content_result, media_result, video_path, content_files, media_files)
        
        # 检查最终视频是否成功生成
        if video_path and Path(video_path).exists():
            return True
        else:
            service.logger.error("Final video file was not created - generation failed")
            return False
        
    except Exception as e:
        print(f"Story generation failed: {e}")
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


def _convert_simple_format(config: Dict) -> Dict:
    """将简化格式转换为完整格式"""
    stories_list = []
    simple_stories = config.get('stories', [])
    settings = config.get('settings', {})
    
    for i, title in enumerate(simple_stories):
        if isinstance(title, str):
            stories_list.append({
                'id': f"story_{i+1:03d}",
                'title': title,
                'language': settings.get('language', 'zh'),
                'style': 'horror',
                'priority': i + 1
            })
    
    # 构建完整格式配置
    full_config = {
        'batch_info': {
            'name': f"简化批量生成-{datetime.now().strftime('%Y%m%d')}",
            'description': f"包含{len(simple_stories)}个故事的简化配置",
            'created_at': datetime.now().strftime('%Y-%m-%d'),
            'total_stories': len(simple_stories)
        },
        'settings': {
            'default_language': settings.get('language', 'zh'),
            'output_format': 'mp4',
            'enable_subtitles': True
        },
        'stories': stories_list
    }
    
    return full_config


async def batch_generate_from_json(json_file_path: str):
    """
    从JSON文件批量生成故事视频 - 支持简化格式
    
    简化格式示例:
    {
      "settings": {"language": "zh", "concurrent": 2},
      "stories": ["故事1", "故事2", "故事3"]
    }
    
    完整格式保持不变
    """
    main_logger = logging.getLogger('story_generator')
    
    try:
        # 读取JSON配置文件
        json_path = Path(json_file_path)
        if not json_path.exists():
            main_logger.error(f"JSON文件不存在: {json_file_path}")
            return False
            
        with open(json_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 检测并转换简化格式
        if 'stories' in config and isinstance(config['stories'], list):
            if len(config['stories']) > 0 and isinstance(config['stories'][0], str):
                # 简化格式：stories是字符串数组
                config = _convert_simple_format(config)
        
        # 解析配置（兼容完整格式）
        batch_info = config.get('batch_info', {
            'name': f"批量生成-{datetime.now().strftime('%Y%m%d')}",
            'description': f"包含{len(config.get('stories', []))}个故事"
        })
        settings = config.get('settings', {})
        stories = config.get('stories', [])
        
        if not stories:
            main_logger.error("JSON文件中未找到故事配置")
            return False
        
        # 获取设置 - 强制串行生成
        concurrent_limit = 1  # 固定为1，强制串行生成
        default_language = settings.get('default_language', settings.get('language', 'zh'))
        
        # 打印批量信息
        print(f"\n🚀 开始批量生成: {batch_info.get('name')}")
        print(f"📝 描述: {batch_info.get('description')}")
        print(f"📊 总数: {len(stories)} 个故事")
        print(f"⚡ 生成模式: 串行生成 (逐个生成)")
        print(f"🌐 默认语言: {default_language}")
        print("=" * 60)
        
        # 按优先级排序故事
        stories_sorted = sorted(stories, key=lambda x: x.get('priority', 999))
        
        # 生成统计
        total_stories = len(stories_sorted)
        success_count = 0
        failed_count = 0
        results = []
        
        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def generate_story_with_semaphore(story_config):
            """带信号量控制的故事生成"""
            async with semaphore:
                story_id = story_config.get('id', 'unknown')
                title = story_config.get('title', 'Unknown Title')
                language = story_config.get('language', default_language)
                style = story_config.get('style', 'horror')
                priority = story_config.get('priority', 999)
                
                print(f"\n🎬 开始生成 [{story_id}]: {title}")
                print(f"   语言: {language}, 风格: {style}, 优先级: {priority}")
                
                start_time = time.time()
                try:
                    success = await generate_single_story(title, language)
                    duration = time.time() - start_time
                    
                    result = {
                        'id': story_id,
                        'title': title,
                        'language': language,
                        'style': style,
                        'priority': priority,
                        'success': success,
                        'duration': duration,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    if success:
                        print(f"✅ [{story_id}] 生成成功 (耗时: {duration:.1f}s)")
                        nonlocal success_count
                        success_count += 1
                    else:
                        print(f"❌ [{story_id}] 生成失败 (耗时: {duration:.1f}s)")
                        nonlocal failed_count
                        failed_count += 1
                    
                    return result
                    
                except Exception as e:
                    duration = time.time() - start_time
                    main_logger.error(f"故事 {story_id} 生成异常: {e}")
                    print(f"💥 [{story_id}] 生成异常: {e} (耗时: {duration:.1f}s)")
                    
                    failed_count += 1
                    return {
                        'id': story_id,
                        'title': title,
                        'language': language,
                        'style': style,
                        'priority': priority,
                        'success': False,
                        'duration': duration,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
        
        # 串行执行所有故事生成
        print(f"\n🔄 开始串行生成 {total_stories} 个故事...")
        tasks = [generate_story_with_semaphore(story) for story in stories_sorted]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 生成总结报告
        print("\n" + "=" * 60)
        print("📊 批量生成完成总结")
        print("=" * 60)
        print(f"✅ 成功: {success_count}/{total_stories}")
        print(f"❌ 失败: {failed_count}/{total_stories}")
        print(f"📈 成功率: {(success_count/total_stories*100):.1f}%")
        
        # 保存结果报告
        report = {
            'batch_info': batch_info,
            'settings': settings,
            'summary': {
                'total_stories': total_stories,
                'success_count': success_count,
                'failed_count': failed_count,
                'success_rate': success_count/total_stories*100,
                'completion_time': datetime.now().isoformat()
            },
            'results': [r for r in results if not isinstance(r, Exception)]
        }
        
        # 保存报告文件
        report_path = Path('output') / 'reports' / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"📄 详细报告已保存: {report_path}")
        
        return success_count == total_stories
        
    except Exception as e:
        main_logger.error(f"JSON批量生成失败: {e}")
        print(f"💥 JSON批量生成失败: {e}")
        return False


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description="历史故事生成器 - 支持单个生成和JSON批量生成",
        epilog="""
使用示例:
  默认JSON模式: python main.py (使用 config/default_stories.json)
  单个生成:     python main.py --theme '秦始皇统一六国'
  JSON批量生成: python main.py --json example_batch.json  
  文本批量生成: python main.py --batch themes.txt --language zh
  测试模式:     python main.py --test
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--theme", type=str, help="故事主题")
    parser.add_argument("--language", type=str, default="zh", choices=["zh", "en", "es"], 
                       help="语言代码 (默认: zh)")
    parser.add_argument("--batch", type=str, help="批量生成，指定主题文件路径")
    parser.add_argument("--json", type=str, help="JSON批量生成，指定JSON配置文件路径")
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
    
    elif args.json:
        # JSON批量生成
        success = asyncio.run(batch_generate_from_json(args.json))
        if success:
            print("\n🎉 JSON批量生成完成!")
        else:
            print("\n💔 JSON批量生成失败!")
    
    elif args.batch:
        # 文本文件批量生成
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
        # 默认JSON模式
        default_json = "config/default_stories.json"
        if Path(default_json).exists():
            print(f"🎯 使用默认配置文件: {default_json}")
            success = asyncio.run(batch_generate_from_json(default_json))
            if success:
                print("\n🎉 默认批量生成完成!")
            else:
                print("\n💔 默认批量生成失败!")
        else:
            # 创建默认配置文件
            print(f"📝 创建默认配置文件: {default_json}")
            default_config = {
                "settings": {
                    "language": "zh"
                },
                "stories": [
                    "秦始皇统一六国",
                    "汉武帝北击匈奴", 
                    "唐太宗贞观之治",
                    "康熙智擒鳌拜"
                ]
            }
            with open(default_json, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 已创建默认配置文件，再次运行 python main.py 开始生成")
            print(f"💡 可编辑 {default_json} 自定义故事列表")


if __name__ == "__main__":
    main()