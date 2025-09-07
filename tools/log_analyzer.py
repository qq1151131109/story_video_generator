#!/usr/bin/env python3
"""
日志分析工具 - 快速定位和排查问题
使用新的增强型日志系统分析项目运行状态
"""
import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import argparse

class LogAnalyzer:
    """日志分析器"""
    
    def __init__(self, log_dir: str = "output/logs"):
        self.log_dir = Path(log_dir)
        self.log_files = {
            'main': self.log_dir / 'story_generator.log',
            'errors': self.log_dir / 'errors.log',
            'performance': self.log_dir / 'performance.log'
        }
    
    def analyze_errors(self, hours: int = 24) -> Dict[str, Any]:
        """分析错误日志"""
        print(f"🔍 分析最近 {hours} 小时的错误...")
        
        errors_file = self.log_files['errors']
        if not errors_file.exists():
            return {"status": "no_errors_file", "message": "错误日志文件不存在"}
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        error_stats = defaultdict(int)
        error_details = []
        
        try:
            with open(errors_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        log_entry = json.loads(line.strip())
                        
                        # 解析时间戳
                        timestamp = datetime.fromisoformat(log_entry.get('timestamp', ''))
                        if timestamp < cutoff_time:
                            continue
                        
                        # 提取错误信息
                        context = log_entry.get('context', {})
                        error_type = context.get('error_type', 'Unknown')
                        error_message = context.get('error_message', log_entry.get('message', ''))
                        
                        error_key = f"{error_type}: {error_message}"
                        error_stats[error_key] += 1
                        
                        error_details.append({
                            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'type': error_type,
                            'message': error_message,
                            'component': log_entry.get('component', ''),
                            'line': line_num
                        })
                        
                    except (json.JSONDecodeError, ValueError) as e:
                        continue  # 跳过无法解析的行
        
        except Exception as e:
            return {"status": "error", "message": f"读取错误日志失败: {e}"}
        
        # 按发生次数排序
        top_errors = sorted(error_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "status": "success",
            "total_errors": len(error_details),
            "unique_errors": len(error_stats),
            "top_errors": top_errors,
            "recent_errors": error_details[-5:] if error_details else [],
            "error_trend": self._analyze_error_trend(error_details)
        }
    
    def analyze_performance(self, hours: int = 24) -> Dict[str, Any]:
        """分析性能日志"""
        print(f"⚡ 分析最近 {hours} 小时的性能...")
        
        perf_file = self.log_files['performance']
        if not perf_file.exists():
            return {"status": "no_performance_file", "message": "性能日志文件不存在"}
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        api_calls = []
        operations = []
        
        try:
            with open(perf_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        
                        # 解析时间戳
                        timestamp = datetime.fromisoformat(log_entry.get('timestamp', ''))
                        if timestamp < cutoff_time:
                            continue
                        
                        performance = log_entry.get('performance', {})
                        
                        # API调用性能
                        if 'method' in performance:
                            api_calls.append({
                                'timestamp': timestamp,
                                'method': performance.get('method'),
                                'url': performance.get('url', ''),
                                'status_code': performance.get('status_code'),
                                'response_time': performance.get('response_time'),
                                'success': performance.get('success', True)
                            })
                        
                        # 操作性能
                        elif 'duration' in performance:
                            operations.append({
                                'timestamp': timestamp,
                                'duration': performance.get('duration'),
                                'success': performance.get('success', True)
                            })
                            
                    except (json.JSONDecodeError, ValueError):
                        continue
        
        except Exception as e:
            return {"status": "error", "message": f"读取性能日志失败: {e}"}
        
        # 分析API性能
        api_stats = self._analyze_api_performance(api_calls)
        
        # 分析操作性能
        op_stats = self._analyze_operation_performance(operations)
        
        return {
            "status": "success",
            "api_performance": api_stats,
            "operation_performance": op_stats,
            "performance_summary": {
                "total_api_calls": len(api_calls),
                "total_operations": len(operations),
                "avg_api_time": api_stats.get('avg_response_time', 0),
                "slow_operations": len([op for op in operations if op['duration'] > 10.0])
            }
        }
    
    def analyze_system_health(self) -> Dict[str, Any]:
        """分析系统健康状态"""
        print("🏥 分析系统健康状态...")
        
        health = {
            "status": "healthy",
            "issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        # 检查日志文件大小
        for name, log_file in self.log_files.items():
            if log_file.exists():
                size_mb = log_file.stat().st_size / 1024 / 1024
                if size_mb > 50:  # 超过50MB
                    health["issues"].append(f"{name}日志文件过大: {size_mb:.1f}MB")
                    health["recommendations"].append(f"清理{name}日志或增加轮转频率")
                elif size_mb > 20:  # 超过20MB
                    health["warnings"].append(f"{name}日志文件较大: {size_mb:.1f}MB")
        
        # 分析错误率
        error_analysis = self.analyze_errors(hours=1)
        if error_analysis["status"] == "success" and error_analysis["total_errors"] > 50:
            health["issues"].append(f"过去1小时错误过多: {error_analysis['total_errors']}个")
            health["status"] = "warning"
        
        # 检查性能问题
        perf_analysis = self.analyze_performance(hours=1)
        if perf_analysis["status"] == "success":
            slow_ops = perf_analysis["performance_summary"].get("slow_operations", 0)
            if slow_ops > 5:
                health["warnings"].append(f"检测到{slow_ops}个慢操作")
        
        # 设置总体状态
        if health["issues"]:
            health["status"] = "unhealthy"
        elif health["warnings"]:
            health["status"] = "warning"
        
        return health
    
    def _analyze_error_trend(self, error_details: List[Dict]) -> Dict[str, Any]:
        """分析错误趋势"""
        if not error_details:
            return {"trend": "stable", "message": "无错误记录"}
        
        # 按小时分组
        hourly_errors = defaultdict(int)
        for error in error_details:
            hour = error['timestamp'][:13]  # YYYY-MM-DD HH
            hourly_errors[hour] += 1
        
        if len(hourly_errors) < 2:
            return {"trend": "insufficient_data", "message": "数据不足以分析趋势"}
        
        # 简单趋势分析
        recent_hours = sorted(hourly_errors.items())[-3:]  # 最近3小时
        if len(recent_hours) >= 2:
            if recent_hours[-1][1] > recent_hours[-2][1] * 1.5:
                return {"trend": "increasing", "message": "错误数量快速增加"}
            elif recent_hours[-1][1] < recent_hours[-2][1] * 0.5:
                return {"trend": "decreasing", "message": "错误数量显著减少"}
        
        return {"trend": "stable", "message": "错误数量相对稳定"}
    
    def _analyze_api_performance(self, api_calls: List[Dict]) -> Dict[str, Any]:
        """分析API性能"""
        if not api_calls:
            return {"message": "无API调用记录"}
        
        # 响应时间统计
        response_times = [call['response_time'] for call in api_calls if call['response_time']]
        success_rate = sum(1 for call in api_calls if call['success']) / len(api_calls)
        
        # 按URL分组统计
        url_stats = defaultdict(list)
        for call in api_calls:
            if call['response_time']:
                url_stats[call['url']].append(call['response_time'])
        
        # 找出最慢的API
        slow_apis = []
        for url, times in url_stats.items():
            avg_time = sum(times) / len(times)
            if avg_time > 5.0:  # 超过5秒
                slow_apis.append({"url": url, "avg_time": avg_time, "calls": len(times)})
        
        return {
            "total_calls": len(api_calls),
            "success_rate": success_rate,
            "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "slow_apis": sorted(slow_apis, key=lambda x: x['avg_time'], reverse=True)[:5]
        }
    
    def _analyze_operation_performance(self, operations: List[Dict]) -> Dict[str, Any]:
        """分析操作性能"""
        if not operations:
            return {"message": "无操作记录"}
        
        durations = [op['duration'] for op in operations]
        success_rate = sum(1 for op in operations if op['success']) / len(operations)
        
        return {
            "total_operations": len(operations),
            "success_rate": success_rate,
            "avg_duration": sum(durations) / len(durations),
            "max_duration": max(durations),
            "slow_operations": len([d for d in durations if d > 10.0])
        }
    
    def generate_report(self, hours: int = 24) -> str:
        """生成完整的分析报告"""
        print(f"📊 生成最近 {hours} 小时的完整报告...")
        
        # 执行各项分析
        error_analysis = self.analyze_errors(hours)
        perf_analysis = self.analyze_performance(hours)
        health_analysis = self.analyze_system_health()
        
        # 生成报告
        report = []
        report.append("=" * 60)
        report.append(f"📊 故事视频生成器 - 日志分析报告")
        report.append(f"📅 分析时间范围: 最近 {hours} 小时")
        report.append(f"🕐 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        
        # 系统健康状态
        report.append(f"\n🏥 系统健康状态: {health_analysis['status'].upper()}")
        if health_analysis['issues']:
            report.append("❌ 发现的问题:")
            for issue in health_analysis['issues']:
                report.append(f"   • {issue}")
        
        if health_analysis['warnings']:
            report.append("⚠️  警告:")
            for warning in health_analysis['warnings']:
                report.append(f"   • {warning}")
        
        if health_analysis['recommendations']:
            report.append("💡 建议:")
            for rec in health_analysis['recommendations']:
                report.append(f"   • {rec}")
        
        # 错误分析
        report.append(f"\n🚨 错误分析:")
        if error_analysis['status'] == 'success':
            report.append(f"   总错误数: {error_analysis['total_errors']}")
            report.append(f"   独特错误: {error_analysis['unique_errors']}")
            report.append(f"   错误趋势: {error_analysis['error_trend']['message']}")
            
            if error_analysis['top_errors']:
                report.append("   🔥 高频错误:")
                for error, count in error_analysis['top_errors'][:5]:
                    report.append(f"      • {error}: {count}次")
        else:
            report.append(f"   状态: {error_analysis['message']}")
        
        # 性能分析
        report.append(f"\n⚡ 性能分析:")
        if perf_analysis['status'] == 'success':
            summary = perf_analysis['performance_summary']
            report.append(f"   API调用数: {summary['total_api_calls']}")
            report.append(f"   操作数: {summary['total_operations']}")
            report.append(f"   平均API响应时间: {summary['avg_api_time']:.2f}s")
            report.append(f"   慢操作数: {summary['slow_operations']}")
            
            # API性能详情
            api_perf = perf_analysis['api_performance']
            if 'success_rate' in api_perf:
                report.append(f"   API成功率: {api_perf['success_rate']*100:.1f}%")
                
                if api_perf.get('slow_apis'):
                    report.append("   🐌 慢API:")
                    for api in api_perf['slow_apis'][:3]:
                        report.append(f"      • {api['url']}: {api['avg_time']:.2f}s ({api['calls']}次调用)")
        else:
            report.append(f"   状态: {perf_analysis['message']}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="日志分析工具 - 快速定位问题")
    parser.add_argument('--hours', '-t', type=int, default=24, help='分析时间范围（小时）')
    parser.add_argument('--errors', '-e', action='store_true', help='只分析错误')
    parser.add_argument('--performance', '-p', action='store_true', help='只分析性能')
    parser.add_argument('--health', action='store_true', help='只检查系统健康')
    parser.add_argument('--log-dir', '-d', default='output/logs', help='日志目录路径')
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer(args.log_dir)
    
    if args.errors:
        result = analyzer.analyze_errors(args.hours)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.performance:
        result = analyzer.analyze_performance(args.hours)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.health:
        result = analyzer.analyze_system_health()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # 生成完整报告
        report = analyzer.generate_report(args.hours)
        print(report)
        
        # 保存报告到文件
        report_file = Path(args.log_dir) / f'analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n📄 报告已保存到: {report_file}")
        except Exception as e:
            print(f"\n❌ 保存报告失败: {e}")

if __name__ == "__main__":
    main()