#!/usr/bin/env python3
"""
测试自动化运行脚本
提供多种测试运行模式和配置选项
"""
import argparse
import subprocess
import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import shutil


class TestRunner:
    """测试运行器"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent
        self.test_results = {}
    
    def run_command(self, command: List[str], description: str) -> Dict[str, Any]:
        """执行命令并返回结果"""
        if self.verbose:
            print(f"🔄 {description}")
            print(f"   Command: {' '.join(command)}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            duration = time.time() - start_time
            
            success = result.returncode == 0
            
            if self.verbose or not success:
                print(f"{'✅' if success else '❌'} {description} ({'成功' if success else '失败'}) - {duration:.2f}s")
                
                if not success:
                    print("STDOUT:", result.stdout)
                    print("STDERR:", result.stderr)
            
            return {
                'command': ' '.join(command),
                'description': description,
                'success': success,
                'returncode': result.returncode,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ {description} - 执行异常: {e}")
            
            return {
                'command': ' '.join(command),
                'description': description,
                'success': False,
                'exception': str(e),
                'duration': duration
            }
    
    def check_dependencies(self) -> bool:
        """检查测试依赖"""
        print("🔍 检查测试依赖...")
        
        # 检查pytest
        pytest_result = self.run_command(['python', '-m', 'pytest', '--version'], "检查pytest版本")
        if not pytest_result['success']:
            print("❌ pytest未安装，请运行: pip install pytest")
            return False
        
        # 检查必要的测试包
        required_packages = [
            'pytest-asyncio',
            'pytest-cov', 
            'pytest-mock'
        ]
        
        for package in required_packages:
            import_result = self.run_command(['python', '-c', f'import {package.replace("-", "_")}'], f"检查{package}")
            if not import_result['success']:
                print(f"⚠️  {package}未安装，建议运行: pip install {package}")
        
        # 检查项目结构
        required_dirs = ['tests', 'tests/unit', 'tests/integration', 'tests/e2e', 'tests/performance']
        for dir_path in required_dirs:
            if not (self.project_root / dir_path).exists():
                print(f"⚠️  测试目录不存在: {dir_path}")
        
        return True
    
    def run_unit_tests(self, pattern: str = None, coverage: bool = True) -> Dict[str, Any]:
        """运行单元测试"""
        print("🧪 运行单元测试...")
        
        command = ['python', '-m', 'pytest', 'tests/unit/', '-v', '-m', 'unit']
        
        if pattern:
            command.extend(['-k', pattern])
        
        if coverage:
            command.extend([
                '--cov=.',
                '--cov-report=html:htmlcov/unit',
                '--cov-report=term-missing'
            ])
        
        result = self.run_command(command, "单元测试")
        self.test_results['unit'] = result
        return result
    
    def run_integration_tests(self, pattern: str = None) -> Dict[str, Any]:
        """运行集成测试"""
        print("🔗 运行集成测试...")
        
        command = ['python', '-m', 'pytest', 'tests/integration/', '-v', '-m', 'integration']
        
        if pattern:
            command.extend(['-k', pattern])
        
        result = self.run_command(command, "集成测试")
        self.test_results['integration'] = result
        return result
    
    def run_e2e_tests(self, pattern: str = None, slow: bool = False) -> Dict[str, Any]:
        """运行端到端测试"""
        print("🎯 运行端到端测试...")
        
        command = ['python', '-m', 'pytest', 'tests/e2e/', '-v', '-m', 'e2e']
        
        if pattern:
            command.extend(['-k', pattern])
        
        if not slow:
            command.extend(['-m', 'not slow'])
        
        result = self.run_command(command, "端到端测试")
        self.test_results['e2e'] = result
        return result
    
    def run_performance_tests(self, pattern: str = None, benchmark: bool = False) -> Dict[str, Any]:
        """运行性能测试"""
        print("⚡ 运行性能测试...")
        
        command = ['python', '-m', 'pytest', 'tests/performance/', '-v', '-m', 'performance']
        
        if pattern:
            command.extend(['-k', pattern])
        
        if benchmark:
            command.extend(['-m', 'benchmark'])
        
        # 性能测试通常需要更多时间
        command.extend(['--tb=short'])
        
        result = self.run_command(command, "性能测试")
        self.test_results['performance'] = result
        return result
    
    def run_all_tests(self, fast_only: bool = False, skip_slow: bool = True) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 运行完整测试套件...")
        
        command = ['python', '-m', 'pytest', 'tests/', '-v']
        
        if fast_only:
            command.extend(['--fast-only'])
        
        if skip_slow:
            command.extend(['-m', 'not slow'])
        
        # 生成完整报告
        command.extend([
            '--cov=.',
            '--cov-report=html:htmlcov/full',
            '--cov-report=term-missing',
            '--cov-report=xml'
        ])
        
        result = self.run_command(command, "完整测试套件")
        self.test_results['all'] = result
        return result
    
    def run_smoke_tests(self) -> Dict[str, Any]:
        """运行冒烟测试"""
        print("💨 运行冒烟测试...")
        
        command = [
            'python', '-m', 'pytest', 
            'tests/', '-v', 
            '-m', 'not slow and not performance',
            '-k', 'test_basic or test_simple or test_smoke',
            '--tb=short'
        ]
        
        result = self.run_command(command, "冒烟测试")
        self.test_results['smoke'] = result
        return result
    
    def run_specific_test(self, test_path: str, verbose: bool = True) -> Dict[str, Any]:
        """运行特定测试"""
        print(f"🎯 运行特定测试: {test_path}")
        
        command = ['python', '-m', 'pytest', test_path]
        
        if verbose:
            command.append('-v')
        
        result = self.run_command(command, f"特定测试: {test_path}")
        return result
    
    def generate_test_report(self, output_file: str = None) -> str:
        """生成测试报告"""
        if not self.test_results:
            return "No test results available"
        
        report = []
        report.append("=" * 60)
        report.append("📊 测试执行报告")
        report.append("=" * 60)
        report.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        total_tests = 0
        passed_tests = 0
        total_duration = 0
        
        for test_type, result in self.test_results.items():
            status = "✅ 通过" if result['success'] else "❌ 失败"
            report.append(f"{test_type.upper()}: {status} ({result['duration']:.2f}s)")
            
            total_duration += result['duration']
            
            if 'stdout' in result:
                # 尝试从pytest输出中提取测试数量
                stdout = result['stdout']
                if 'passed' in stdout:
                    # 简单的测试计数解析
                    lines = stdout.split('\n')
                    for line in lines:
                        if 'passed' in line and 'failed' in line:
                            # pytest 输出格式解析
                            pass
        
        report.append("")
        report.append(f"总执行时间: {total_duration:.2f}s")
        report.append("")
        
        # 添加失败详情
        failed_tests = [(k, v) for k, v in self.test_results.items() if not v['success']]
        if failed_tests:
            report.append("❌ 失败详情:")
            for test_type, result in failed_tests:
                report.append(f"  {test_type}: {result.get('stderr', 'No error details')[:200]}...")
        
        report_text = "\n".join(report)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"📄 测试报告已保存: {output_file}")
        
        return report_text
    
    def clean_test_artifacts(self):
        """清理测试产物"""
        print("🧹 清理测试产物...")
        
        artifacts_to_clean = [
            '.pytest_cache',
            '__pycache__',
            '*.pyc',
            'htmlcov',
            'coverage.xml',
            '.coverage',
            'test_output'
        ]
        
        for artifact in artifacts_to_clean:
            if '*' in artifact:
                # 通配符清理
                import glob
                for file_path in glob.glob(f"**/{artifact}", recursive=True):
                    try:
                        os.remove(file_path)
                        if self.verbose:
                            print(f"  Removed: {file_path}")
                    except Exception:
                        pass
            else:
                # 目录/文件清理
                artifact_path = Path(artifact)
                if artifact_path.exists():
                    try:
                        if artifact_path.is_dir():
                            shutil.rmtree(artifact_path)
                        else:
                            artifact_path.unlink()
                        if self.verbose:
                            print(f"  Removed: {artifact}")
                    except Exception as e:
                        if self.verbose:
                            print(f"  Failed to remove {artifact}: {e}")
        
        print("✅ 测试产物清理完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="故事视频生成器测试运行器")
    
    # 基本选项
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('--clean', action='store_true', help='清理测试产物')
    
    # 测试类型选择
    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument('--unit', action='store_true', help='只运行单元测试')
    test_group.add_argument('--integration', action='store_true', help='只运行集成测试')  
    test_group.add_argument('--e2e', action='store_true', help='只运行端到端测试')
    test_group.add_argument('--performance', action='store_true', help='只运行性能测试')
    test_group.add_argument('--smoke', action='store_true', help='只运行冒烟测试')
    test_group.add_argument('--all', action='store_true', help='运行所有测试')
    
    # 测试过滤
    parser.add_argument('-k', '--pattern', help='测试名称匹配模式')
    parser.add_argument('--file', help='运行特定测试文件')
    
    # 测试选项
    parser.add_argument('--no-cov', action='store_true', help='禁用覆盖率统计')
    parser.add_argument('--slow', action='store_true', help='包含慢速测试')
    parser.add_argument('--fast-only', action='store_true', help='只运行快速测试')
    parser.add_argument('--benchmark', action='store_true', help='运行基准测试')
    
    # 报告选项
    parser.add_argument('--report', help='生成测试报告到指定文件')
    
    args = parser.parse_args()
    
    # 创建测试运行器
    runner = TestRunner(verbose=args.verbose)
    
    # 清理选项
    if args.clean:
        runner.clean_test_artifacts()
        return
    
    # 检查依赖
    if not runner.check_dependencies():
        print("❌ 依赖检查失败，请安装必要的测试依赖")
        sys.exit(1)
    
    # 执行测试
    try:
        if args.file:
            # 运行特定文件
            result = runner.run_specific_test(args.file)
            success = result['success']
            
        elif args.unit:
            result = runner.run_unit_tests(
                pattern=args.pattern,
                coverage=not args.no_cov
            )
            success = result['success']
            
        elif args.integration:
            result = runner.run_integration_tests(pattern=args.pattern)
            success = result['success']
            
        elif args.e2e:
            result = runner.run_e2e_tests(
                pattern=args.pattern,
                slow=args.slow
            )
            success = result['success']
            
        elif args.performance:
            result = runner.run_performance_tests(
                pattern=args.pattern,
                benchmark=args.benchmark
            )
            success = result['success']
            
        elif args.smoke:
            result = runner.run_smoke_tests()
            success = result['success']
            
        elif args.all:
            result = runner.run_all_tests(
                fast_only=args.fast_only,
                skip_slow=not args.slow
            )
            success = result['success']
            
        else:
            # 默认运行冒烟测试
            result = runner.run_smoke_tests()
            success = result['success']
        
        # 生成报告
        if args.report:
            runner.generate_test_report(args.report)
        elif runner.test_results:
            print("\n" + runner.generate_test_report())
        
        # 返回适当的退出代码
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        sys.exit(130)
    
    except Exception as e:
        print(f"❌ 测试执行异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()