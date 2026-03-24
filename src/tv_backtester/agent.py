"""
Autonomous Strategy Agent
=========================
Main orchestration loop that autonomously generates, tests, and iterates on trading strategies.
"""

import asyncio
import os
import time
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from .ai_generator import create_ai_provider, StrategyRequest, StrategyResponse
from .pine_validator import PineValidator, fix_pine_script
from .browser_controller import BrowserController
from .metric_analyzer import MetricAnalyzer, ResultAggregator, AnalysisResult


logger = logging.getLogger(__name__)


@dataclass
class StrategyVersion:
    """A single version of a strategy."""
    version: int
    pine_script: str
    name: str
    description: str
    parameters: Dict[str, Any]
    reasoning: str
    backtest_results: Dict[str, Any] = field(default_factory=dict)
    analysis: Optional[AnalysisResult] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StrategyEvolution:
    """Complete evolution history of a strategy."""
    strategy_type: str
    symbol: str
    timeframe: str
    versions: List[StrategyVersion] = field(default_factory=list)
    best_version: Optional[int] = None
    total_iterations: int = 0
    success: bool = False


class AutonomousAgent:
    """
    Autonomous agent that generates, tests, and iterates on trading strategies.
    
    Workflow:
    1. Generate initial strategy using AI
    2. Validate Pine Script syntax
    3. Run backtest in TradingView
    4. Analyze results
    5. If targets not met and iterations remaining, improve and repeat
    """
    
    def __init__(self, config_path: str = "config/backtester_config.yaml"):
        self.config = self._load_config(config_path)
        self.ai_provider = None
        self.validator = PineValidator()
        self.analyzer = MetricAnalyzer(self._get_target_metrics())
        self.aggregator = ResultAggregator()
        
        # Results storage
        self.results_dir = Path(self.config.get('results', {}).get('output_dir', './results'))
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Evolution tracking
        self.evolutions: Dict[str, StrategyEvolution] = {}
    
    def _load_config(self, path: str) -> Dict:
        """Load configuration from YAML."""
        with open(path) as f:
            config = yaml.safe_load(f)
        
        # Expand environment variables
        return self._expand_env_vars(config)
    
    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand environment variables in config."""
        if isinstance(obj, str):
            if obj.startswith('${') and obj.endswith('}'):
                env_var = obj[2:-1]
                return os.environ.get(env_var, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(v) for v in obj]
        return obj
    
    def _get_target_metrics(self) -> Dict[str, float]:
        """Get target metrics from config."""
        gen_config = self.config.get('strategy_generation', {})
        return {
            'win_rate': gen_config.get('min_win_rate', 45.0),
            'profit_factor': gen_config.get('min_profit_factor', 1.3),
            'max_drawdown': gen_config.get('max_drawdown', 25.0),
            'min_trades': gen_config.get('min_trades', 50),
        }
    
    async def run(self, strategy_types: Optional[List[str]] = None,
                  symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run the autonomous strategy generation and testing loop.
        
        Args:
            strategy_types: List of strategy types to generate (or use config)
            symbols: List of symbols to test (or use config)
        
        Returns:
            Summary of results
        """
        
        # Initialize AI provider
        self.ai_provider = create_ai_provider(self.config)
        
        # Get settings
        strategy_types = strategy_types or self.config.get(
            'strategy_generation', {}
        ).get('strategy_types', ['sma_bounce'])
        
        symbols = symbols or self.config.get('symbols', ['BYBIT:BTCUSDT.P'])
        
        max_iterations = self.config.get('strategy_generation', {}).get('max_iterations', 10)
        timeframe = self.config.get('tradingview', {}).get('default_timeframe', '15')
        headless = self.config.get('tradingview', {}).get('headless', False)
        
        logger.info(f"Starting autonomous agent")
        logger.info(f"Strategy types: {strategy_types}")
        logger.info(f"Symbols: {symbols}")
        logger.info(f"Max iterations: {max_iterations}")
        
        # Process each strategy type
        for strategy_type in strategy_types:
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing strategy type: {strategy_type}")
            logger.info(f"{'='*50}")
            
            # Generate and evolve strategy
            evolution = await self._evolve_strategy(
                strategy_type=strategy_type,
                symbols=symbols,
                timeframe=timeframe,
                max_iterations=max_iterations,
                headless=headless
            )
            
            self.evolutions[strategy_type] = evolution
            
            # Save results
            self._save_evolution(evolution)
        
        # Generate summary
        summary = self._generate_summary()
        
        # Export results
        self.aggregator.export_csv(str(self.results_dir / 'backtest_results.csv'))
        
        return summary
    
    async def _evolve_strategy(self, strategy_type: str, symbols: List[str],
                                timeframe: str, max_iterations: int,
                                headless: bool) -> StrategyEvolution:
        """
        Evolve a strategy through multiple iterations until it meets targets.
        """
        
        evolution = StrategyEvolution(
            strategy_type=strategy_type,
            symbol=symbols[0],  # Primary symbol for evolution
            timeframe=timeframe
        )
        
        # Get risk parameters from config
        backtest_config = self.config.get('backtest', {})
        risk_params = {
            'sl_atr_mult': backtest_config.get('default_sl_atr_mult', 1.8),
            'tp_rr': backtest_config.get('default_tp_rr', 2.0),
            'be_trigger_pct': 0.9,
            'trail_trigger_pct': 1.5,
        }
        
        # Generate initial strategy
        logger.info(f"Generating initial {strategy_type} strategy...")
        
        request = StrategyRequest(
            strategy_type=strategy_type,
            timeframe=timeframe,
            symbol=symbols[0],
            risk_params=risk_params,
            additional_context=f"Focus on {strategy_type} patterns for crypto futures."
        )
        
        response = self.ai_provider.generate_strategy(request)
        
        # Validate and fix
        pine_script = self._validate_and_fix(response.pine_script)
        
        # Create version 1
        version = StrategyVersion(
            version=1,
            pine_script=pine_script,
            name=response.strategy_name,
            description=response.description,
            parameters=response.parameters,
            reasoning=response.reasoning
        )
        
        evolution.versions.append(version)
        evolution.total_iterations = 1
        
        # Iterate until success or max iterations
        while evolution.total_iterations <= max_iterations:
            current_version = evolution.versions[-1]
            
            logger.info(f"\n--- Iteration {evolution.total_iterations} ---")
            logger.info(f"Testing: {current_version.name}")
            
            # Run backtest on primary symbol
            async with BrowserController(headless=headless) as browser:
                # Navigate to chart
                await browser.navigate_to_chart(symbols[0], timeframe)
                
                # Paste and compile
                await browser.paste_pine_script(current_version.pine_script)
                success, error = await browser.compile_script()
                
                if not success:
                    logger.error(f"Compilation failed: {error}")
                    
                    # Try to fix and retry once
                    fixed_script = fix_pine_script(current_version.pine_script)
                    if fixed_script != current_version.pine_script:
                        current_version.pine_script = fixed_script
                        await browser.paste_pine_script(fixed_script)
                        success, error = await browser.compile_script()
                
                if not success:
                    logger.error("Could not compile strategy, aborting evolution")
                    break
                
                # Get backtest metrics
                metrics = await browser.get_backtest_metrics()
                current_version.backtest_results = metrics
                
                # Take screenshot
                if self.config.get('results', {}).get('save_screenshots', True):
                    screenshot_path = self.results_dir / f"{strategy_type}_v{current_version.version}.png"
                    await browser.take_screenshot(str(screenshot_path))
            
            # Analyze results
            analysis = self.analyzer.analyze(metrics)
            current_version.analysis = analysis
            
            logger.info(f"Score: {analysis.overall_score:.1f}")
            logger.info(f"Meets targets: {analysis.meets_targets}")
            
            # Add to aggregator
            self.aggregator.add_result(f"{strategy_type}_v{current_version.version}", 
                                       metrics, analysis)
            
            # Check if successful
            if analysis.meets_targets:
                logger.info("✅ Strategy meets all targets!")
                evolution.success = True
                evolution.best_version = current_version.version
                break
            
            # Check if we should iterate
            if not analysis.should_iterate:
                logger.info("Strategy cannot be improved further")
                break
            
            # Check if max iterations reached
            if evolution.total_iterations >= max_iterations:
                logger.info(f"Max iterations ({max_iterations}) reached")
                break
            
            # Generate improved version
            logger.info(f"Generating improved version...")
            logger.info(f"Focus areas: {analysis.iteration_priority}")
            
            improved_response = self.ai_provider.improve_strategy(
                current_strategy=current_version.pine_script,
                backtest_results=metrics,
                target_metrics=self._get_target_metrics()
            )
            
            # Validate and fix
            improved_script = self._validate_and_fix(improved_response.pine_script)
            
            # Create new version
            new_version = StrategyVersion(
                version=current_version.version + 1,
                pine_script=improved_script,
                name=improved_response.strategy_name,
                description=improved_response.description,
                parameters=improved_response.parameters,
                reasoning=improved_response.reasoning
            )
            
            evolution.versions.append(new_version)
            evolution.total_iterations += 1
        
        # Find best version if not already set
        if evolution.best_version is None and evolution.versions:
            best_score = -1
            for v in evolution.versions:
                if v.analysis and v.analysis.overall_score > best_score:
                    best_score = v.analysis.overall_score
                    evolution.best_version = v.version
        
        return evolution
    
    def _validate_and_fix(self, script: str) -> str:
        """Validate Pine Script and fix common issues."""
        
        is_valid, errors = self.validator.validate(script)
        
        if not is_valid:
            logger.warning(f"Validation found {len(errors)} issues, attempting fix")
            for error in errors[:5]:  # Log first 5
                logger.warning(f"  {error.message}")
            
            script = fix_pine_script(script)
        
        return script
    
    def _save_evolution(self, evolution: StrategyEvolution) -> None:
        """Save evolution history to disk."""
        
        filepath = self.results_dir / f"{evolution.strategy_type}_evolution.json"
        
        # Convert to serializable format
        data = {
            'strategy_type': evolution.strategy_type,
            'symbol': evolution.symbol,
            'timeframe': evolution.timeframe,
            'total_iterations': evolution.total_iterations,
            'success': evolution.success,
            'best_version': evolution.best_version,
            'versions': []
        }
        
        for v in evolution.versions:
            version_data = {
                'version': v.version,
                'name': v.name,
                'description': v.description,
                'parameters': v.parameters,
                'reasoning': v.reasoning,
                'backtest_results': v.backtest_results,
                'timestamp': v.timestamp
            }
            
            if v.analysis:
                version_data['analysis'] = {
                    'overall_score': v.analysis.overall_score,
                    'meets_targets': v.analysis.meets_targets,
                    'recommendations': v.analysis.recommendations
                }
            
            data['versions'].append(version_data)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Save best Pine Script separately
        if evolution.best_version:
            best_v = next(v for v in evolution.versions if v.version == evolution.best_version)
            pine_path = self.results_dir / f"{evolution.strategy_type}_best.pine"
            with open(pine_path, 'w') as f:
                f.write(best_v.pine_script)
        
        logger.info(f"Saved evolution to {filepath}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary of all evolutions."""
        
        summary = {
            'total_strategies': len(self.evolutions),
            'successful': sum(1 for e in self.evolutions.values() if e.success),
            'total_iterations': sum(e.total_iterations for e in self.evolutions.values()),
            'strategies': {},
            'aggregated': self.aggregator.get_summary()
        }
        
        for strategy_type, evolution in self.evolutions.items():
            summary['strategies'][strategy_type] = {
                'success': evolution.success,
                'iterations': evolution.total_iterations,
                'best_version': evolution.best_version,
                'best_score': max(
                    (v.analysis.overall_score for v in evolution.versions if v.analysis),
                    default=0
                )
            }
        
        # Save summary
        summary_path = self.results_dir / 'summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary


async def run_agent(config_path: str = "config/backtester_config.yaml",
                    strategy_types: Optional[List[str]] = None,
                    symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convenience function to run the autonomous agent.
    
    Args:
        config_path: Path to configuration file
        strategy_types: List of strategy types to generate
        symbols: List of symbols to test
    
    Returns:
        Summary of results
    """
    
    agent = AutonomousAgent(config_path)
    return await agent.run(strategy_types, symbols)


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        result = await run_agent(
            strategy_types=['sma_bounce'],
            symbols=['BYBIT:BTCUSDT.P']
        )
        
        print("\n" + "="*50)
        print("AGENT COMPLETED")
        print("="*50)
        print(json.dumps(result, indent=2))
    
    asyncio.run(main())
