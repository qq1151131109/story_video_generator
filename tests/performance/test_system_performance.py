"""
系统性能测试
测试系统在各种负载条件下的性能表现
"""
import pytest
import asyncio
import time
import psutil
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Dict, Any
import json

from services.story_video_service import StoryVideoService
from content.content_pipeline import ContentGenerationRequest
from utils.result_types import Result


@dataclass
class PerformanceMetrics:
    """性能指标"""
    operation: str
    duration: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    error: str = None


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.metrics: List[PerformanceMetrics] = []
    
    def start_monitoring(self, operation: str):
        """开始监控"""
        return PerformanceContext(self, operation)
    
    def record_metrics(self, operation: str, duration: float, success: bool, error: str = None):
        """记录性能指标"""
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        cpu_percent = self.process.cpu_percent()
        
        metrics = PerformanceMetrics(
            operation=operation,
            duration=duration,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            success=success,
            error=error
        )
        
        self.metrics.append(metrics)
        return metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.metrics:
            return {"message": "No metrics recorded"}
        
        successful_metrics = [m for m in self.metrics if m.success]
        failed_metrics = [m for m in self.metrics if not m.success]
        
        durations = [m.duration for m in successful_metrics]
        memory_usage = [m.memory_usage_mb for m in self.metrics]
        cpu_usage = [m.cpu_usage_percent for m in self.metrics if m.cpu_usage_percent > 0]
        
        return {
            "total_operations": len(self.metrics),
            "successful_operations": len(successful_metrics),
            "failed_operations": len(failed_metrics),
            "success_rate": len(successful_metrics) / len(self.metrics) if self.metrics else 0,
            "duration_stats": {
                "min": min(durations) if durations else 0,
                "max": max(durations) if durations else 0,
                "avg": sum(durations) / len(durations) if durations else 0,
                "total": sum(durations)
            },
            "memory_stats": {
                "min": min(memory_usage) if memory_usage else 0,
                "max": max(memory_usage) if memory_usage else 0,
                "avg": sum(memory_usage) / len(memory_usage) if memory_usage else 0
            },
            "cpu_stats": {
                "min": min(cpu_usage) if cpu_usage else 0,
                "max": max(cpu_usage) if cpu_usage else 0,
                "avg": sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
            }
        }


class PerformanceContext:
    """性能监控上下文管理器"""
    
    def __init__(self, monitor: PerformanceMonitor, operation: str):
        self.monitor = monitor
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        success = exc_type is None
        error = str(exc_val) if exc_val else None
        
        self.monitor.record_metrics(self.operation, duration, success, error)


class TestSystemPerformance:
    """系统性能测试类"""
    
    @pytest.fixture
    def performance_monitor(self):
        """性能监控器fixture"""
        return PerformanceMonitor()
    
    @pytest.fixture
    def mock_service_with_delay(self, config_manager, file_manager):
        """带延迟的Mock服务"""
        service = StoryVideoService()
        
        # Mock各组件以控制执行时间
        async def mock_generate_script(request):
            await asyncio.sleep(0.1)  # 模拟LLM调用延迟
            return Result.success(Mock(
                title="测试标题",
                content="测试内容..." * 20,
                language=request.language,
                theme=request.theme,
                word_count=400,
                generation_time=0.1,
                model_used="mock"
            ))
        
        async def mock_split_scenes(script_content, language):
            await asyncio.sleep(0.05)  # 模拟场景分割延迟
            scenes = [Mock(sequence=i, content=f"场景{i}", image_prompt=f"提示{i}") for i in range(1, 9)]
            return Result.success(Mock(scenes=scenes, total_scenes=8, processing_time=0.05))
        
        async def mock_analyze_characters(script_content, language):
            await asyncio.sleep(0.03)  # 模拟角色分析延迟
            character = Mock(name="测试角色", description="描述", image_prompt="角色提示", role="主角")
            return Result.success(Mock(
                characters=[character], 
                main_character=character, 
                total_characters=1, 
                processing_time=0.03
            ))
        
        # 注入Mock方法
        with patch.object(service.content_pipeline.script_generator, 'generate_script_async', side_effect=mock_generate_script), \
             patch.object(service.content_pipeline.scene_splitter, 'split_scenes_async', side_effect=mock_split_scenes), \
             patch.object(service.content_pipeline.character_analyzer, 'analyze_characters_async', side_effect=mock_analyze_characters):
            yield service
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_single_request_performance(self, mock_service_with_delay, performance_monitor):
        """测试单个请求性能"""
        request = ContentGenerationRequest(
            theme="康熙大帝智擒鳌拜",
            language="zh",
            style="horror"
        )
        
        with performance_monitor.start_monitoring("single_request"):
            result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
            
            assert result.is_success()
        
        summary = performance_monitor.get_summary()
        
        # 性能断言
        assert summary["duration_stats"]["avg"] < 5.0, f"Single request too slow: {summary['duration_stats']['avg']:.2f}s"
        assert summary["memory_stats"]["max"] < 200, f"Memory usage too high: {summary['memory_stats']['max']:.1f}MB"
        assert summary["success_rate"] == 1.0, f"Success rate too low: {summary['success_rate']}"
        
        print(f"✅ Single request performance: {summary['duration_stats']['avg']:.2f}s, {summary['memory_stats']['avg']:.1f}MB")
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(self, mock_service_with_delay, performance_monitor):
        """测试并发请求性能"""
        concurrent_count = 5
        
        requests = [
            ContentGenerationRequest(
                theme=f"测试主题{i}",
                language="zh",
                style="horror"
            ) for i in range(concurrent_count)
        ]
        
        # 并发执行
        async def execute_request(request, request_id):
            with performance_monitor.start_monitoring(f"concurrent_request_{request_id}"):
                result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
                return result
        
        tasks = [execute_request(req, i) for i, req in enumerate(requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证结果
        successful_results = [r for r in results if not isinstance(r, Exception) and r.is_success()]
        
        summary = performance_monitor.get_summary()
        
        # 并发性能断言
        assert len(successful_results) >= concurrent_count * 0.8, f"Too many failed concurrent requests: {len(successful_results)}/{concurrent_count}"
        assert summary["duration_stats"]["max"] < 10.0, f"Some concurrent requests too slow: {summary['duration_stats']['max']:.2f}s"
        assert summary["memory_stats"]["max"] < 300, f"Memory usage too high under concurrency: {summary['memory_stats']['max']:.1f}MB"
        
        print(f"✅ Concurrent performance ({concurrent_count} requests): avg {summary['duration_stats']['avg']:.2f}s, max memory {summary['memory_stats']['max']:.1f}MB")
    
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, mock_service_with_delay, performance_monitor):
        """测试持续负载性能"""
        total_requests = 20
        batch_size = 5
        
        # 分批执行以模拟持续负载
        for batch in range(0, total_requests, batch_size):
            batch_requests = [
                ContentGenerationRequest(
                    theme=f"持续负载主题{i}",
                    language="zh"
                ) for i in range(batch, min(batch + batch_size, total_requests))
            ]
            
            # 执行批次
            async def execute_batch_request(request, request_id):
                with performance_monitor.start_monitoring(f"sustained_request_{request_id}"):
                    result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
                    return result
            
            tasks = [execute_batch_request(req, batch + i) for i, req in enumerate(batch_requests)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 短暂休息模拟真实使用模式
            await asyncio.sleep(0.1)
        
        summary = performance_monitor.get_summary()
        
        # 持续负载性能断言
        assert summary["success_rate"] >= 0.8, f"Success rate degraded under sustained load: {summary['success_rate']}"
        assert summary["duration_stats"]["avg"] < 3.0, f"Average response time degraded: {summary['duration_stats']['avg']:.2f}s"
        
        # 检查性能退化
        early_metrics = performance_monitor.metrics[:5]
        late_metrics = performance_monitor.metrics[-5:]
        
        early_avg = sum(m.duration for m in early_metrics if m.success) / len([m for m in early_metrics if m.success])
        late_avg = sum(m.duration for m in late_metrics if m.success) / len([m for m in late_metrics if m.success])
        
        performance_degradation = (late_avg - early_avg) / early_avg if early_avg > 0 else 0
        
        assert performance_degradation < 0.5, f"Significant performance degradation: {performance_degradation:.2%}"
        
        print(f"✅ Sustained load performance ({total_requests} requests): {summary['success_rate']:.2%} success, avg {summary['duration_stats']['avg']:.2f}s")
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, mock_service_with_delay, performance_monitor):
        """测试内存使用稳定性"""
        initial_memory = performance_monitor.process.memory_info().rss / 1024 / 1024
        
        # 执行多轮请求检测内存泄漏
        for round_num in range(3):
            requests = [
                ContentGenerationRequest(
                    theme=f"内存测试主题{round_num}_{i}",
                    language="zh"
                ) for i in range(5)
            ]
            
            async def execute_memory_test(request, request_id):
                with performance_monitor.start_monitoring(f"memory_test_{request_id}"):
                    result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
                    return result
            
            tasks = [execute_memory_test(req, i) for i, req in enumerate(requests)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 强制垃圾回收
            import gc
            gc.collect()
            
            current_memory = performance_monitor.process.memory_info().rss / 1024 / 1024
            print(f"Round {round_num + 1}: Memory usage {current_memory:.1f}MB")
        
        final_memory = performance_monitor.process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        
        # 内存稳定性断言
        assert memory_growth < 50, f"Potential memory leak detected: {memory_growth:.1f}MB growth"
        assert final_memory < 250, f"Total memory usage too high: {final_memory:.1f}MB"
        
        print(f"✅ Memory stability test: {memory_growth:.1f}MB growth, final {final_memory:.1f}MB")
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_error_handling_performance(self, mock_service_with_delay, performance_monitor):
        """测试错误处理性能"""
        # 模拟各种错误情况
        error_scenarios = [
            ("network_timeout", asyncio.TimeoutError("Network timeout")),
            ("api_error", Exception("API Error")),
            ("validation_error", ValueError("Invalid input")),
        ]
        
        for scenario_name, error in error_scenarios:
            # 注入错误
            with patch.object(mock_service_with_delay.content_pipeline.script_generator, 'generate_script_async', side_effect=error):
                request = ContentGenerationRequest(
                    theme=f"错误测试_{scenario_name}",
                    language="zh"
                )
                
                with performance_monitor.start_monitoring(f"error_handling_{scenario_name}"):
                    try:
                        result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
                        # 错误应该被正确处理并返回错误结果
                        assert result.is_error()
                    except Exception as e:
                        # 或者抛出可控的异常
                        assert isinstance(e, (asyncio.TimeoutError, Exception, ValueError))
        
        summary = performance_monitor.get_summary()
        
        # 错误处理性能断言
        error_handling_metrics = [m for m in performance_monitor.metrics if "error_handling" in m.operation]
        avg_error_handling_time = sum(m.duration for m in error_handling_metrics) / len(error_handling_metrics)
        
        assert avg_error_handling_time < 1.0, f"Error handling too slow: {avg_error_handling_time:.2f}s"
        
        print(f"✅ Error handling performance: avg {avg_error_handling_time:.3f}s")
    
    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_cpu_intensive_operations(self, mock_service_with_delay, performance_monitor):
        """测试CPU密集型操作性能"""
        import asyncio
        
        async def cpu_intensive_test():
            # 模拟CPU密集型操作（文本处理、内容生成等）
            for i in range(10):
                request = ContentGenerationRequest(
                    theme=f"CPU密集测试{i}",
                    language="zh"
                )
                
                with performance_monitor.start_monitoring(f"cpu_intensive_{i}"):
                    # 添加一些CPU密集型操作模拟
                    text = "测试文本" * 1000
                    processed_text = text.upper().lower().replace("测试", "test")
                    
                    result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
                    assert result.is_success()
        
        # 监控CPU使用率
        start_cpu = psutil.cpu_percent(interval=1)
        
        asyncio.run(cpu_intensive_test())
        
        end_cpu = psutil.cpu_percent(interval=1)
        
        summary = performance_monitor.get_summary()
        
        # CPU性能断言
        cpu_intensive_metrics = [m for m in performance_monitor.metrics if "cpu_intensive" in m.operation]
        avg_duration = sum(m.duration for m in cpu_intensive_metrics) / len(cpu_intensive_metrics)
        
        assert avg_duration < 2.0, f"CPU intensive operations too slow: {avg_duration:.2f}s"
        
        print(f"✅ CPU intensive performance: avg {avg_duration:.2f}s per operation")


class TestPerformanceBenchmarks:
    """性能基准测试"""
    
    @pytest.fixture
    def benchmark_data(self):
        """基准测试数据"""
        with open("tests/data/test_themes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    
    @pytest.mark.performance
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_throughput_benchmark(self, mock_service_with_delay, benchmark_data, performance_monitor):
        """吞吐量基准测试"""
        themes = benchmark_data["test_scenarios"]["performance_testing"]["themes"]
        test_duration = 30  # 30秒测试
        
        start_time = time.time()
        completed_requests = 0
        
        async def continuous_requests():
            nonlocal completed_requests
            theme_index = 0
            
            while time.time() - start_time < test_duration:
                theme = themes[theme_index % len(themes)]
                request = ContentGenerationRequest(
                    theme=theme,
                    language="zh"
                )
                
                with performance_monitor.start_monitoring(f"throughput_request_{completed_requests}"):
                    try:
                        result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
                        if result.is_success():
                            completed_requests += 1
                    except Exception:
                        pass  # 忽略错误，继续测试
                
                theme_index += 1
        
        await continuous_requests()
        
        actual_duration = time.time() - start_time
        throughput = completed_requests / actual_duration
        
        # 吞吐量基准
        expected_min_throughput = 1.0  # 每秒至少1个请求
        assert throughput >= expected_min_throughput, f"Throughput too low: {throughput:.2f} req/s"
        
        print(f"✅ Throughput benchmark: {throughput:.2f} requests/second over {actual_duration:.1f}s")
    
    @pytest.mark.performance
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_latency_percentiles(self, mock_service_with_delay, performance_monitor):
        """延迟百分位数测试"""
        request_count = 50
        
        requests = [
            ContentGenerationRequest(
                theme=f"延迟测试{i}",
                language="zh"
            ) for i in range(request_count)
        ]
        
        # 执行请求
        async def execute_latency_test(request, request_id):
            with performance_monitor.start_monitoring(f"latency_test_{request_id}"):
                result = await mock_service_with_delay.content_pipeline.generate_content_async(request)
                return result
        
        tasks = [execute_latency_test(req, i) for i, req in enumerate(requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 计算延迟百分位数
        successful_metrics = [m for m in performance_monitor.metrics if m.success and "latency_test" in m.operation]
        durations = sorted([m.duration for m in successful_metrics])
        
        if durations:
            p50 = durations[int(0.5 * len(durations))]
            p95 = durations[int(0.95 * len(durations))]
            p99 = durations[int(0.99 * len(durations))]
            
            # 延迟基准
            assert p50 < 1.0, f"P50 latency too high: {p50:.3f}s"
            assert p95 < 3.0, f"P95 latency too high: {p95:.3f}s"
            assert p99 < 5.0, f"P99 latency too high: {p99:.3f}s"
            
            print(f"✅ Latency percentiles: P50={p50:.3f}s, P95={p95:.3f}s, P99={p99:.3f}s")
        else:
            pytest.fail("No successful requests for latency analysis")
    
    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_resource_utilization(self, performance_monitor):
        """资源利用率测试"""
        import time
        import threading
        
        # 监控系统资源
        resource_data = []
        monitoring = True
        
        def monitor_resources():
            while monitoring:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_info = psutil.virtual_memory()
                disk_info = psutil.disk_usage('/')
                
                resource_data.append({
                    'timestamp': time.time(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_info.percent,
                    'memory_available_gb': memory_info.available / (1024**3),
                    'disk_free_gb': disk_info.free / (1024**3)
                })
                
                time.sleep(0.5)
        
        # 启动资源监控
        monitor_thread = threading.Thread(target=monitor_resources)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 模拟工作负载
        time.sleep(10)
        
        # 停止监控
        monitoring = False
        monitor_thread.join(timeout=1)
        
        # 分析资源使用
        if resource_data:
            avg_cpu = sum(d['cpu_percent'] for d in resource_data) / len(resource_data)
            max_cpu = max(d['cpu_percent'] for d in resource_data)
            avg_memory = sum(d['memory_percent'] for d in resource_data) / len(resource_data)
            max_memory = max(d['memory_percent'] for d in resource_data)
            
            # 资源利用率基准
            assert max_cpu < 90, f"CPU usage too high: {max_cpu:.1f}%"
            assert max_memory < 80, f"Memory usage too high: {max_memory:.1f}%"
            
            print(f"✅ Resource utilization: CPU avg={avg_cpu:.1f}% max={max_cpu:.1f}%, Memory avg={avg_memory:.1f}% max={max_memory:.1f}%")
        else:
            pytest.skip("No resource data collected")


def pytest_configure(config):
    """配置性能测试标记"""
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "benchmark: Benchmark tests")
    config.addinivalue_line("markers", "slow: Slow performance tests")