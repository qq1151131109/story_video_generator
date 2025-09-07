"""
性能优化工具 - 系统性能分析和优化建议
"""
import asyncio
import sys
import time
import psutil
import gc
from pathlib import Path
from typing import Dict, List, Any, Tuple
import json
import os

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from utils.file_manager import FileManager
from utils.logger import setup_logging
from utils.i18n import get_i18n_manager


class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self):
        self.logger = setup_logging().get_logger('story_generator.performance')
        self.metrics = {}
        self.start_time = None
        self.memory_samples = []
        
    def start_profiling(self, test_name: str):
        """开始性能分析"""
        self.start_time = time.time()
        self.metrics[test_name] = {
            'start_time': self.start_time,
            'start_memory': psutil.Process().memory_info().rss,
            'start_cpu': psutil.cpu_percent(),
            'memory_samples': []
        }
        
        # 强制垃圾回收，确保测试环境一致
        gc.collect()
        
        self.logger.info(f"Started profiling: {test_name}")
    
    def sample_memory(self, test_name: str):
        """采样内存使用"""
        if test_name in self.metrics:
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
            self.metrics[test_name]['memory_samples'].append(memory_mb)
    
    def end_profiling(self, test_name: str) -> Dict[str, Any]:
        """结束性能分析并返回指标"""
        if test_name not in self.metrics:
            return {}
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss
        end_cpu = psutil.cpu_percent()
        
        metrics = self.metrics[test_name]
        
        result = {
            'duration_seconds': end_time - metrics['start_time'],
            'memory_start_mb': metrics['start_memory'] / 1024 / 1024,
            'memory_end_mb': end_memory / 1024 / 1024,
            'memory_peak_mb': max(metrics['memory_samples']) if metrics['memory_samples'] else end_memory / 1024 / 1024,
            'memory_delta_mb': (end_memory - metrics['start_memory']) / 1024 / 1024,
            'cpu_start': metrics['start_cpu'],
            'cpu_end': end_cpu,
            'memory_samples': metrics['memory_samples']
        }
        
        self.logger.info(f"Completed profiling: {test_name}")
        self.logger.info(f"Duration: {result['duration_seconds']:.3f}s, Memory delta: {result['memory_delta_mb']:.2f}MB")
        
        return result


async def benchmark_cache_performance():
    """基准测试：缓存性能（已禁用，缓存功能已移除）"""
    print("\n🔍 缓存性能基准测试")
    print("-" * 40)
    print("⚠️  缓存功能已移除，跳过缓存性能测试")
    
    return {}


def benchmark_i18n_performance():
    """基准测试：国际化性能"""
    print("\n🌍 国际化性能基准测试")
    print("-" * 40)
    
    profiler = PerformanceProfiler()
    i18n = get_i18n_manager()
    
    languages = ['zh', 'en', 'es']
    message_types = [
        ('common', 'success'),
        ('common', 'processing'),
        ('content', 'generating_script'),
        ('media', 'generating_image'),
        ('errors', 'api_key_missing')
    ]
    
    profiler.start_profiling("i18n_performance")
    
    # 语言切换性能
    switch_start = time.time()
    for i in range(1000):
        lang = languages[i % len(languages)]
        i18n.set_language(lang)
        profiler.sample_memory("i18n_performance")
    
    switch_time = time.time() - switch_start
    
    # 消息获取性能
    message_start = time.time()
    for i in range(1000):
        lang = languages[i % len(languages)]
        category, key = message_types[i % len(message_types)]
        i18n.set_language(lang)
        message = i18n.get_message(category, key)
        
        if i % 200 == 0:
            profiler.sample_memory("i18n_performance")
    
    message_time = time.time() - message_start
    
    metrics = profiler.end_profiling("i18n_performance")
    
    print(f"语言切换 (1000次): {switch_time:.3f}s")
    print(f"消息获取 (1000次): {message_time:.3f}s")
    print(f"内存使用变化: {metrics['memory_delta_mb']:+.2f}MB")
    
    return {
        'switch_time': switch_time,
        'message_time': message_time,
        'memory_delta': metrics['memory_delta_mb']
    }


def benchmark_file_operations():
    """基准测试：文件操作性能"""
    print("\n📁 文件操作性能基准测试")
    print("-" * 40)
    
    profiler = PerformanceProfiler()
    file_manager = FileManager(output_dir="output/temp_files")
    
    # 确保目录存在
    os.makedirs("output/temp_files", exist_ok=True)
    
    test_sizes = [
        ("small", "x" * 1000),       # 1KB
        ("medium", "x" * 100000),    # 100KB
        ("large", "x" * 1000000)     # 1MB
    ]
    
    results = {}
    
    for size_name, content in test_sizes:
        profiler.start_profiling(f"file_{size_name}")
        
        # 写入测试
        write_start = time.time()
        file_paths = []
        for i in range(10):
            filename = f"test_{size_name}_{i}.txt"
            file_path = Path("output/temp_files") / filename
            success = file_manager.save_text(content, file_path)
            file_paths.append(file_path)
            
            if i % 3 == 0:
                profiler.sample_memory(f"file_{size_name}")
        
        write_time = time.time() - write_start
        
        # 读取测试
        read_start = time.time()
        for file_path in file_paths:
            loaded_content = file_manager.load_text(file_path)
            
        read_time = time.time() - read_start
        
        # 清理测试文件
        for file_path in file_paths:
            file_path.unlink(missing_ok=True)
        
        metrics = profiler.end_profiling(f"file_{size_name}")
        
        results[size_name] = {
            'write_time': write_time,
            'read_time': read_time,
            'memory_delta': metrics['memory_delta_mb']
        }
        
        print(f"{size_name:>6} ({len(content):>7} bytes): 写入 {write_time:.3f}s, 读取 {read_time:.3f}s")
    
    return results


def analyze_system_resources():
    """分析系统资源"""
    print("\n💻 系统资源分析")
    print("-" * 40)
    
    # CPU信息
    cpu_count = psutil.cpu_count(logical=False)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    cpu_percent = psutil.cpu_percent(interval=1)
    
    print(f"CPU核心数: {cpu_count} 物理, {cpu_count_logical} 逻辑")
    if cpu_freq:
        print(f"CPU频率: {cpu_freq.current:.0f}MHz (最大 {cpu_freq.max:.0f}MHz)")
    print(f"CPU使用率: {cpu_percent}%")
    
    # 内存信息
    memory = psutil.virtual_memory()
    print(f"内存总量: {memory.total / 1024**3:.2f}GB")
    print(f"内存可用: {memory.available / 1024**3:.2f}GB ({memory.percent}% 已使用)")
    
    # 磁盘信息
    disk = psutil.disk_usage('/')
    print(f"磁盘总量: {disk.total / 1024**3:.2f}GB")
    print(f"磁盘可用: {disk.free / 1024**3:.2f}GB ({disk.used / disk.total * 100:.1f}% 已使用)")
    
    # Python进程信息
    process = psutil.Process()
    process_memory = process.memory_info()
    print(f"当前进程内存: {process_memory.rss / 1024**2:.2f}MB")
    
    return {
        'cpu': {
            'physical_cores': cpu_count,
            'logical_cores': cpu_count_logical,
            'frequency_mhz': cpu_freq.current if cpu_freq else None,
            'usage_percent': cpu_percent
        },
        'memory': {
            'total_gb': memory.total / 1024**3,
            'available_gb': memory.available / 1024**3,
            'usage_percent': memory.percent
        },
        'disk': {
            'total_gb': disk.total / 1024**3,
            'free_gb': disk.free / 1024**3,
            'usage_percent': disk.used / disk.total * 100
        },
        'process': {
            'memory_mb': process_memory.rss / 1024**2
        }
    }


def generate_optimization_recommendations(benchmark_results: Dict[str, Any], 
                                       system_info: Dict[str, Any]) -> List[str]:
    """生成优化建议"""
    recommendations = []
    
    # 内存优化建议
    if system_info['memory']['usage_percent'] > 80:
        recommendations.append("⚠️  系统内存使用率较高，建议关闭不必要的程序或增加内存")
    
    if system_info['process']['memory_mb'] > 500:
        recommendations.append("💾 当前进程内存使用较大，建议优化缓存配置或减少并发数")
    
    # 缓存优化建议
    if 'cache' in benchmark_results:
        cache_results = benchmark_results['cache']
        
        # 检查大数据缓存性能
        if 'large_data' in cache_results:
            large_data = cache_results['large_data']
            if large_data['write_time'] > 1.0:
                recommendations.append("🗄️  大数据缓存写入较慢，建议增加缓存大小限制或使用异步缓存")
            
            if large_data['memory_delta'] > 50:
                recommendations.append("📈 缓存内存占用较大，建议调整内存缓存大小限制")
    
    # CPU优化建议
    if system_info['cpu']['usage_percent'] > 80:
        recommendations.append("⚡ CPU使用率较高，建议降低并发任务数量")
    
    if system_info['cpu']['logical_cores'] >= 4:
        recommendations.append("🚀 多核CPU可用，建议在批量处理时增加并发数以提高效率")
    
    # 磁盘优化建议
    if system_info['disk']['usage_percent'] > 90:
        recommendations.append("💽 磁盘空间不足，建议清理缓存或增加存储空间")
    
    # I18n优化建议
    if 'i18n' in benchmark_results:
        i18n_results = benchmark_results['i18n']
        if i18n_results['message_time'] > 0.5:
            recommendations.append("🌍 多语言消息获取较慢，建议预加载常用消息")
    
    # 文件操作优化建议
    if 'files' in benchmark_results:
        file_results = benchmark_results['files']
        if any(result['write_time'] > 1.0 for result in file_results.values()):
            recommendations.append("📝 文件写入较慢，建议使用SSD或优化磁盘IO")
    
    # 通用优化建议
    recommendations.extend([
        "⚙️  根据系统性能调整config/settings.json中的max_concurrent_tasks",
        "🎯 使用缓存功能避免重复API调用以节省时间和成本",
        "📊 定期运行性能测试以监控系统性能变化",
        "🔧 在生产环境中使用uvloop等高性能事件循环"
    ])
    
    return recommendations


async def run_performance_analysis():
    """运行完整的性能分析"""
    print("历史故事生成器 - 性能优化分析")
    print("=" * 60)
    
    # 1. 系统资源分析
    system_info = analyze_system_resources()
    
    # 2. 运行基准测试
    benchmark_results = {}
    
    try:
        benchmark_results['cache'] = await benchmark_cache_performance()
    except Exception as e:
        print(f"缓存性能测试失败: {e}")
    
    try:
        benchmark_results['i18n'] = benchmark_i18n_performance()
    except Exception as e:
        print(f"国际化性能测试失败: {e}")
    
    try:
        benchmark_results['files'] = benchmark_file_operations()
    except Exception as e:
        print(f"文件操作性能测试失败: {e}")
    
    # 3. 生成优化建议
    recommendations = generate_optimization_recommendations(benchmark_results, system_info)
    
    # 4. 输出报告
    print("\n" + "=" * 60)
    print("性能优化建议")
    print("=" * 60)
    
    for i, recommendation in enumerate(recommendations, 1):
        print(f"{i:2d}. {recommendation}")
    
    # 5. 保存详细报告
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'system_info': system_info,
        'benchmark_results': benchmark_results,
        'recommendations': recommendations
    }
    
    report_file = Path("output/performance_report.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 详细报告已保存到: {report_file}")
    
    return len(recommendations)


def main():
    """主函数"""
    try:
        recommendation_count = asyncio.run(run_performance_analysis())
        
        if recommendation_count <= 5:
            print("\n🎉 系统性能良好，优化建议较少！")
        elif recommendation_count <= 10:
            print("\n⚠️  系统性能一般，建议关注性能优化。")
        else:
            print("\n❌ 发现较多性能问题，建议优先处理关键问题。")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  性能分析已中断")
    except Exception as e:
        print(f"\n❌ 性能分析出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()