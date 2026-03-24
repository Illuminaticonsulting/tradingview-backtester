#!/usr/bin/env python3
"""
TradingView AI Backtester CLI
=============================
Command-line interface for autonomous strategy generation and backtesting.

Usage:
    # Run with default settings
    python -m tv_backtester.main
    
    # Run specific strategy type
    python -m tv_backtester.main --strategy sma_bounce
    
    # Run with specific symbols
    python -m tv_backtester.main --symbols BYBIT:BTCUSDT.P BYBIT:ETHUSDT.P
    
    # Run in headless mode
    python -m tv_backtester.main --headless
    
    # Validate Pine Script only
    python -m tv_backtester.main validate my_strategy.pine
    
    # Generate strategy only (no backtest)
    python -m tv_backtester.main generate --strategy trend_following
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml

from .agent import AutonomousAgent, run_agent
from .pine_validator import validate_pine_script, fix_pine_script
from .ai_generator import create_ai_provider, StrategyRequest


def setup_logging(level: str = "INFO", log_file: str = None):
    """Setup logging configuration."""
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def parse_args():
    """Parse command-line arguments."""
    
    parser = argparse.ArgumentParser(
        description='TradingView AI Backtester - Autonomous strategy generation and testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Run with default config
  %(prog)s --strategy sma_bounce        # Generate SMA bounce strategy
  %(prog)s --provider deepseek          # Use DeepSeek R1 for generation
  %(prog)s validate strategy.pine       # Validate Pine Script file
  %(prog)s generate --strategy momentum # Generate without testing
        """
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # === Main run command (default) ===
    run_parser = subparsers.add_parser('run', help='Run autonomous agent')
    run_parser.add_argument(
        '--config', '-c',
        default='config/backtester_config.yaml',
        help='Path to config file'
    )
    run_parser.add_argument(
        '--strategy', '-s',
        nargs='+',
        help='Strategy types to generate (e.g., sma_bounce trend_following)'
    )
    run_parser.add_argument(
        '--symbols',
        nargs='+',
        help='Symbols to test (e.g., BYBIT:BTCUSDT.P BYBIT:ETHUSDT.P)'
    )
    run_parser.add_argument(
        '--provider', '-p',
        choices=['claude', 'deepseek'],
        help='AI provider to use'
    )
    run_parser.add_argument(
        '--model', '-m',
        help='AI model to use (e.g., claude-3-haiku-20240307)'
    )
    run_parser.add_argument(
        '--iterations', '-i',
        type=int,
        help='Maximum iterations per strategy'
    )
    run_parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    run_parser.add_argument(
        '--output', '-o',
        default='./results',
        help='Output directory for results'
    )
    run_parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    # === Validate command ===
    validate_parser = subparsers.add_parser('validate', help='Validate Pine Script file')
    validate_parser.add_argument(
        'file',
        help='Pine Script file to validate'
    )
    validate_parser.add_argument(
        '--fix',
        action='store_true',
        help='Attempt to fix issues and save'
    )
    
    # === Generate command ===
    generate_parser = subparsers.add_parser('generate', help='Generate strategy without testing')
    generate_parser.add_argument(
        '--config', '-c',
        default='config/backtester_config.yaml',
        help='Path to config file'
    )
    generate_parser.add_argument(
        '--strategy', '-s',
        required=True,
        help='Strategy type to generate'
    )
    generate_parser.add_argument(
        '--symbol',
        default='BYBIT:BTCUSDT.P',
        help='Target symbol'
    )
    generate_parser.add_argument(
        '--timeframe',
        default='15',
        help='Timeframe in minutes'
    )
    generate_parser.add_argument(
        '--output', '-o',
        help='Output file for Pine Script'
    )
    generate_parser.add_argument(
        '--provider', '-p',
        choices=['claude', 'deepseek'],
        help='AI provider to use'
    )
    
    # === Backtest command ===
    backtest_parser = subparsers.add_parser('backtest', help='Backtest existing Pine Script')
    backtest_parser.add_argument(
        'file',
        help='Pine Script file to backtest'
    )
    backtest_parser.add_argument(
        '--symbols',
        nargs='+',
        default=['BYBIT:BTCUSDT.P'],
        help='Symbols to test'
    )
    backtest_parser.add_argument(
        '--timeframe',
        default='15',
        help='Timeframe in minutes'
    )
    backtest_parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    
    # If no subcommand, default to 'run'
    args = parser.parse_args()
    
    if args.command is None:
        # Parse again with 'run' as default
        sys.argv.insert(1, 'run')
        args = parser.parse_args()
    
    return args


def cmd_validate(args):
    """Handle validate command."""
    
    filepath = Path(args.file)
    
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    
    with open(filepath) as f:
        script = f.read()
    
    print(f"Validating: {filepath}")
    print("-" * 40)
    
    is_valid, errors = validate_pine_script(script)
    
    if is_valid:
        print("✅ Script is valid!")
    else:
        print(f"❌ Found {len(errors)} issues:")
        for error in errors:
            severity_icon = "❌" if error.severity.value == "error" else "⚠️"
            print(f"  {severity_icon} Line {error.line_number}: {error.message}")
            if error.suggestion:
                print(f"     Suggestion: {error.suggestion}")
    
    if args.fix and not is_valid:
        print("\nAttempting to fix issues...")
        fixed_script = fix_pine_script(script)
        
        # Validate fixed version
        is_fixed, fixed_errors = validate_pine_script(fixed_script)
        
        if len(fixed_errors) < len(errors):
            output_path = filepath.with_suffix('.fixed.pine')
            with open(output_path, 'w') as f:
                f.write(fixed_script)
            print(f"✅ Fixed script saved to: {output_path}")
            print(f"   Errors reduced: {len(errors)} → {len(fixed_errors)}")
        else:
            print("⚠️ Could not automatically fix all issues")
    
    sys.exit(0 if is_valid else 1)


def cmd_generate(args):
    """Handle generate command."""
    
    setup_logging('INFO')
    
    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        sys.exit(1)
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Override provider if specified
    if args.provider:
        config['ai_provider'] = args.provider
    
    # Create provider
    try:
        provider = create_ai_provider(config)
    except ValueError as e:
        print(f"Error: {e}")
        print("\nMake sure you have set the appropriate API key:")
        print("  export ANTHROPIC_API_KEY=your_key")
        print("  export DEEPSEEK_API_KEY=your_key")
        sys.exit(1)
    
    # Generate strategy
    print(f"Generating {args.strategy} strategy for {args.symbol}...")
    
    request = StrategyRequest(
        strategy_type=args.strategy,
        timeframe=args.timeframe,
        symbol=args.symbol,
        risk_params={
            'sl_atr_mult': 1.8,
            'tp_rr': 2.0,
        }
    )
    
    response = provider.generate_strategy(request)
    
    print(f"\n{'='*50}")
    print(f"Generated: {response.strategy_name}")
    print(f"Description: {response.description}")
    print(f"{'='*50}\n")
    
    # Validate
    is_valid, errors = validate_pine_script(response.pine_script)
    if not is_valid:
        print("⚠️ Validation found issues, fixing...")
        response.pine_script = fix_pine_script(response.pine_script)
    
    # Output
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            f.write(response.pine_script)
        print(f"✅ Saved to: {output_path}")
    else:
        print(response.pine_script)


async def cmd_backtest(args):
    """Handle backtest command."""
    
    from .browser_controller import BrowserController
    from .metric_analyzer import MetricAnalyzer, ResultAggregator
    
    setup_logging('INFO')
    
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    
    with open(filepath) as f:
        script = f.read()
    
    # Validate first
    is_valid, errors = validate_pine_script(script)
    if not is_valid:
        print("⚠️ Script has issues, attempting fix...")
        script = fix_pine_script(script)
    
    analyzer = MetricAnalyzer()
    aggregator = ResultAggregator()
    
    async with BrowserController(headless=args.headless) as browser:
        for symbol in args.symbols:
            print(f"\nBacktesting on {symbol}...")
            
            await browser.navigate_to_chart(symbol, args.timeframe)
            await browser.paste_pine_script(script)
            success, error = await browser.compile_script()
            
            if not success:
                print(f"❌ Compilation failed: {error}")
                continue
            
            metrics = await browser.get_backtest_metrics()
            analysis = analyzer.analyze(metrics)
            aggregator.add_result(symbol, metrics, analysis)
            
            print(f"  Score: {analysis.overall_score:.1f}")
            print(f"  Meets targets: {'✅' if analysis.meets_targets else '❌'}")
    
    # Print summary
    summary = aggregator.get_summary()
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"Symbols tested: {summary['total_symbols']}")
    print(f"Average score: {summary['average_score']:.1f}")
    print(f"Meeting targets: {summary['symbols_meeting_targets']}")
    print(f"Recommendation: {summary['overall_recommendation']}")


async def cmd_run(args):
    """Handle run command."""
    
    setup_logging(args.log_level)
    
    # Load and modify config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        sys.exit(1)
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Apply CLI overrides
    if args.provider:
        config['ai_provider'] = args.provider
    
    if args.model:
        if config.get('ai_provider') == 'claude':
            config['claude']['model'] = args.model
        else:
            config['deepseek']['model'] = args.model
    
    if args.headless:
        config['tradingview']['headless'] = True
    
    if args.iterations:
        config['strategy_generation']['max_iterations'] = args.iterations
    
    if args.output:
        config['results']['output_dir'] = args.output
    
    # Save modified config to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        temp_config = f.name
    
    try:
        # Run agent
        result = await run_agent(
            config_path=temp_config,
            strategy_types=args.strategy,
            symbols=args.symbols
        )
        
        # Print summary
        print(f"\n{'='*50}")
        print("AGENT COMPLETED")
        print(f"{'='*50}")
        print(f"Total strategies: {result['total_strategies']}")
        print(f"Successful: {result['successful']}")
        print(f"Total iterations: {result['total_iterations']}")
        
        for strategy_type, data in result['strategies'].items():
            status = "✅" if data['success'] else "❌"
            print(f"\n{status} {strategy_type}:")
            print(f"   Iterations: {data['iterations']}")
            print(f"   Best score: {data['best_score']:.1f}")
        
        print(f"\nResults saved to: {config['results']['output_dir']}")
        
    finally:
        # Cleanup temp config
        os.remove(temp_config)


def main():
    """Main entry point."""
    
    args = parse_args()
    
    if args.command == 'validate':
        cmd_validate(args)
    elif args.command == 'generate':
        cmd_generate(args)
    elif args.command == 'backtest':
        asyncio.run(cmd_backtest(args))
    elif args.command == 'run':
        asyncio.run(cmd_run(args))
    else:
        print("Unknown command. Use --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
