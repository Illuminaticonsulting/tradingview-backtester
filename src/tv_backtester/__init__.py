"""
TradingView AI Backtester
=========================
Autonomous AI-powered strategy generation and backtesting for TradingView.
"""

from .ai_generator import create_ai_provider, StrategyRequest, StrategyResponse
from .pine_validator import PineValidator, validate_pine_script, fix_pine_script
from .browser_controller import BrowserController, run_backtest
from .metric_analyzer import MetricAnalyzer, ResultAggregator
from .agent import AutonomousAgent, run_agent


__version__ = "1.0.0"
__all__ = [
    "create_ai_provider",
    "StrategyRequest",
    "StrategyResponse",
    "PineValidator",
    "validate_pine_script",
    "fix_pine_script",
    "BrowserController",
    "run_backtest",
    "MetricAnalyzer",
    "ResultAggregator",
    "AutonomousAgent",
    "run_agent",
]
