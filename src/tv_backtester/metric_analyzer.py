"""
Metric Parser and Analyzer Module
=================================
Parses backtest results and provides analysis for strategy improvement.
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MetricStatus(Enum):
    """Status of a metric relative to target."""
    EXCELLENT = "excellent"  # Exceeds target by >20%
    GOOD = "good"           # Meets target
    WARNING = "warning"     # Within 10% of target
    POOR = "poor"           # Below target


@dataclass
class MetricResult:
    """Result of evaluating a single metric."""
    name: str
    value: float
    target: float
    status: MetricStatus
    improvement_needed: float  # Percentage improvement needed to hit target


@dataclass
class AnalysisResult:
    """Complete analysis of backtest results."""
    overall_score: float  # 0-100
    meets_targets: bool
    metrics: List[MetricResult]
    recommendations: List[str]
    should_iterate: bool
    iteration_priority: List[str]  # Ordered list of what to improve


class MetricParser:
    """Parses raw metric strings into normalized values."""
    
    @staticmethod
    def parse_percentage(value: str) -> Optional[float]:
        """Parse percentage string to float."""
        if not value:
            return None
        
        # Remove % sign and convert
        clean = value.replace('%', '').replace(',', '').strip()
        
        # Handle negative with different dash types
        clean = clean.replace('−', '-').replace('–', '-')
        
        try:
            return float(clean)
        except ValueError:
            return None
    
    @staticmethod
    def parse_currency(value: str) -> Optional[float]:
        """Parse currency string to float."""
        if not value:
            return None
        
        # Remove $ and commas
        clean = value.replace('$', '').replace(',', '').strip()
        clean = clean.replace('−', '-').replace('–', '-')
        
        # Handle percentage suffix
        is_percent = False
        if '%' in clean:
            clean = clean.replace('%', '')
            is_percent = True
        
        try:
            result = float(clean)
            return result
        except ValueError:
            return None
    
    @staticmethod
    def parse_integer(value: str) -> Optional[int]:
        """Parse integer string."""
        if not value:
            return None
        
        clean = value.replace(',', '').strip()
        
        try:
            return int(float(clean))
        except ValueError:
            return None
    
    @staticmethod
    def parse_float(value: str) -> Optional[float]:
        """Parse float string."""
        if not value:
            return None
        
        clean = value.replace(',', '').strip()
        clean = clean.replace('−', '-').replace('–', '-')
        
        try:
            return float(clean)
        except ValueError:
            return None


class MetricAnalyzer:
    """
    Analyzes backtest metrics against targets.
    Provides recommendations for strategy improvement.
    """
    
    def __init__(self, targets: Optional[Dict[str, float]] = None):
        self.targets = targets or {
            'win_rate': 45.0,        # Minimum win rate %
            'profit_factor': 1.3,    # Minimum profit factor
            'max_drawdown': 25.0,    # Maximum drawdown %
            'min_trades': 50,        # Minimum trades for statistical significance
            'sharpe_ratio': 0.5,     # Minimum Sharpe ratio
        }
        
        self.parser = MetricParser()
    
    def analyze(self, raw_metrics: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze raw metrics from backtest.
        Returns comprehensive analysis with recommendations.
        """
        
        # Parse raw metrics
        parsed = self._parse_metrics(raw_metrics)
        
        # Evaluate each metric
        results = []
        
        # Win Rate
        if 'win_rate' in parsed:
            results.append(self._evaluate_metric(
                'win_rate', parsed['win_rate'], self.targets['win_rate'],
                higher_is_better=True
            ))
        
        # Profit Factor
        if 'profit_factor' in parsed:
            results.append(self._evaluate_metric(
                'profit_factor', parsed['profit_factor'], self.targets['profit_factor'],
                higher_is_better=True
            ))
        
        # Max Drawdown (lower is better)
        if 'max_drawdown' in parsed:
            results.append(self._evaluate_metric(
                'max_drawdown', parsed['max_drawdown'], self.targets['max_drawdown'],
                higher_is_better=False
            ))
        
        # Total Trades
        if 'total_trades' in parsed:
            results.append(self._evaluate_metric(
                'total_trades', parsed['total_trades'], self.targets['min_trades'],
                higher_is_better=True
            ))
        
        # Sharpe Ratio
        if 'sharpe_ratio' in parsed:
            results.append(self._evaluate_metric(
                'sharpe_ratio', parsed['sharpe_ratio'], self.targets['sharpe_ratio'],
                higher_is_better=True
            ))
        
        # Calculate overall score
        overall_score = self._calculate_score(results)
        
        # Check if meets all targets
        meets_targets = all(
            r.status in [MetricStatus.GOOD, MetricStatus.EXCELLENT]
            for r in results
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(results, parsed)
        
        # Determine if we should iterate
        should_iterate = not meets_targets and any(
            r.status in [MetricStatus.WARNING, MetricStatus.POOR]
            for r in results
        )
        
        # Prioritize what to improve
        priority = self._prioritize_improvements(results)
        
        return AnalysisResult(
            overall_score=overall_score,
            meets_targets=meets_targets,
            metrics=results,
            recommendations=recommendations,
            should_iterate=should_iterate,
            iteration_priority=priority
        )
    
    def _parse_metrics(self, raw: Dict[str, Any]) -> Dict[str, float]:
        """Parse raw metric strings to floats."""
        
        parsed = {}
        
        # Win rate
        if 'win_rate' in raw:
            val = self.parser.parse_percentage(str(raw['win_rate']))
            if val is not None:
                parsed['win_rate'] = val
        
        # Profit factor
        if 'profit_factor' in raw:
            val = self.parser.parse_float(str(raw['profit_factor']))
            if val is not None:
                parsed['profit_factor'] = val
        
        # Max drawdown
        if 'max_drawdown' in raw:
            val = self.parser.parse_percentage(str(raw['max_drawdown']))
            if val is not None:
                parsed['max_drawdown'] = abs(val)  # Always positive
        
        # Total trades
        if 'total_trades' in raw:
            val = self.parser.parse_integer(str(raw['total_trades']))
            if val is not None:
                parsed['total_trades'] = val
        
        # Sharpe ratio
        if 'sharpe_ratio' in raw:
            val = self.parser.parse_float(str(raw['sharpe_ratio']))
            if val is not None:
                parsed['sharpe_ratio'] = val
        
        # Net profit (for reference)
        if 'net_profit' in raw:
            val = self.parser.parse_currency(str(raw['net_profit']))
            if val is not None:
                parsed['net_profit'] = val
        
        return parsed
    
    def _evaluate_metric(self, name: str, value: float, target: float,
                         higher_is_better: bool) -> MetricResult:
        """Evaluate a single metric against its target."""
        
        if higher_is_better:
            ratio = value / target if target > 0 else 1.0
            improvement_needed = ((target - value) / target * 100) if value < target else 0
            
            if ratio >= 1.2:
                status = MetricStatus.EXCELLENT
            elif ratio >= 1.0:
                status = MetricStatus.GOOD
            elif ratio >= 0.9:
                status = MetricStatus.WARNING
            else:
                status = MetricStatus.POOR
        else:
            # Lower is better (e.g., drawdown)
            ratio = target / value if value > 0 else 1.0
            improvement_needed = ((value - target) / value * 100) if value > target else 0
            
            if ratio >= 1.2:
                status = MetricStatus.EXCELLENT
            elif ratio >= 1.0:
                status = MetricStatus.GOOD
            elif ratio >= 0.9:
                status = MetricStatus.WARNING
            else:
                status = MetricStatus.POOR
        
        return MetricResult(
            name=name,
            value=value,
            target=target,
            status=status,
            improvement_needed=improvement_needed
        )
    
    def _calculate_score(self, results: List[MetricResult]) -> float:
        """Calculate overall score 0-100."""
        
        if not results:
            return 0.0
        
        scores = []
        for result in results:
            if result.status == MetricStatus.EXCELLENT:
                scores.append(100)
            elif result.status == MetricStatus.GOOD:
                scores.append(80)
            elif result.status == MetricStatus.WARNING:
                scores.append(60)
            else:
                scores.append(40)
        
        return sum(scores) / len(scores)
    
    def _generate_recommendations(self, results: List[MetricResult],
                                   parsed: Dict[str, float]) -> List[str]:
        """Generate improvement recommendations."""
        
        recommendations = []
        
        for result in results:
            if result.status in [MetricStatus.POOR, MetricStatus.WARNING]:
                if result.name == 'win_rate':
                    recommendations.append(
                        f"Win rate ({result.value:.1f}%) below target ({result.target:.1f}%). "
                        "Consider: stricter entry filters, trend alignment, or avoiding ranging markets."
                    )
                
                elif result.name == 'profit_factor':
                    recommendations.append(
                        f"Profit factor ({result.value:.2f}) below target ({result.target:.2f}). "
                        "Consider: wider take profit, tighter stop loss, or better risk:reward ratio."
                    )
                
                elif result.name == 'max_drawdown':
                    recommendations.append(
                        f"Drawdown ({result.value:.1f}%) exceeds target ({result.target:.1f}%). "
                        "Consider: smaller position sizes, tighter stops, or adding drawdown limits."
                    )
                
                elif result.name == 'total_trades':
                    recommendations.append(
                        f"Only {result.value:.0f} trades - need {result.target:.0f}+ for significance. "
                        "Consider: relaxing entry conditions or testing longer time period."
                    )
                
                elif result.name == 'sharpe_ratio':
                    recommendations.append(
                        f"Sharpe ratio ({result.value:.2f}) below target ({result.target:.2f}). "
                        "Consider: reducing trade frequency or improving risk-adjusted returns."
                    )
        
        # Add general recommendations based on patterns
        if 'win_rate' in parsed and 'profit_factor' in parsed:
            if parsed['win_rate'] > 60 and parsed['profit_factor'] < 1.5:
                recommendations.append(
                    "High win rate but low profit factor suggests exits are too tight. "
                    "Consider letting winners run longer."
                )
            elif parsed['win_rate'] < 40 and parsed['profit_factor'] > 1.5:
                recommendations.append(
                    "Low win rate but good profit factor - typical trend following. "
                    "Focus on capital preservation during losing streaks."
                )
        
        return recommendations
    
    def _prioritize_improvements(self, results: List[MetricResult]) -> List[str]:
        """Order metrics by improvement priority."""
        
        # Filter to only poor/warning metrics
        poor_metrics = [r for r in results if r.status in [MetricStatus.POOR, MetricStatus.WARNING]]
        
        # Sort by improvement needed (descending)
        poor_metrics.sort(key=lambda x: x.improvement_needed, reverse=True)
        
        # Return names in priority order
        return [r.name for r in poor_metrics]


class ResultAggregator:
    """Aggregates results across multiple symbols."""
    
    def __init__(self):
        self.results: Dict[str, Dict] = {}
    
    def add_result(self, symbol: str, metrics: Dict[str, Any],
                   analysis: AnalysisResult) -> None:
        """Add result for a symbol."""
        
        self.results[symbol] = {
            'metrics': metrics,
            'analysis': analysis
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get aggregated summary across all symbols."""
        
        if not self.results:
            return {}
        
        # Calculate averages
        all_scores = [r['analysis'].overall_score for r in self.results.values()]
        symbols_meeting_targets = sum(
            1 for r in self.results.values() if r['analysis'].meets_targets
        )
        
        # Find best and worst performers
        sorted_results = sorted(
            self.results.items(),
            key=lambda x: x[1]['analysis'].overall_score,
            reverse=True
        )
        
        return {
            'total_symbols': len(self.results),
            'average_score': sum(all_scores) / len(all_scores),
            'symbols_meeting_targets': symbols_meeting_targets,
            'best_performers': [s for s, _ in sorted_results[:3]],
            'worst_performers': [s for s, _ in sorted_results[-3:]],
            'overall_recommendation': self._get_overall_recommendation()
        }
    
    def _get_overall_recommendation(self) -> str:
        """Generate overall recommendation based on all results."""
        
        all_analyses = [r['analysis'] for r in self.results.values()]
        
        if not all_analyses:
            return "No results to analyze"
        
        avg_score = sum(a.overall_score for a in all_analyses) / len(all_analyses)
        meeting_targets = sum(1 for a in all_analyses if a.meets_targets)
        
        if meeting_targets == len(all_analyses):
            return "Strategy meets targets on all symbols. Consider live testing."
        elif meeting_targets > len(all_analyses) * 0.7:
            return "Strategy performs well on most symbols. Review underperformers."
        elif avg_score > 60:
            return "Strategy shows promise but needs improvement. Focus on weak metrics."
        else:
            return "Strategy needs significant improvement. Consider alternative approach."
    
    def export_csv(self, filepath: str) -> None:
        """Export results to CSV."""
        
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'Symbol', 'Score', 'Meets Targets', 'Win Rate', 'Profit Factor',
                'Max Drawdown', 'Total Trades', 'Sharpe', 'Top Recommendation'
            ])
            
            for symbol, data in self.results.items():
                metrics = data['metrics']
                analysis = data['analysis']
                
                writer.writerow([
                    symbol,
                    f"{analysis.overall_score:.1f}",
                    'Yes' if analysis.meets_targets else 'No',
                    metrics.get('win_rate', 'N/A'),
                    metrics.get('profit_factor', 'N/A'),
                    metrics.get('max_drawdown', 'N/A'),
                    metrics.get('total_trades', 'N/A'),
                    metrics.get('sharpe_ratio', 'N/A'),
                    analysis.recommendations[0] if analysis.recommendations else ''
                ])
        
        logger.info(f"Results exported to {filepath}")


if __name__ == "__main__":
    # Test with sample data
    analyzer = MetricAnalyzer()
    
    sample_metrics = {
        'net_profit': '$1,234.56',
        'total_trades': '87',
        'win_rate': '52.3%',
        'profit_factor': '1.45',
        'max_drawdown': '-18.5%',
        'sharpe_ratio': '0.78'
    }
    
    result = analyzer.analyze(sample_metrics)
    
    print(f"Overall Score: {result.overall_score:.1f}")
    print(f"Meets Targets: {result.meets_targets}")
    print(f"Should Iterate: {result.should_iterate}")
    print(f"\nMetrics:")
    for m in result.metrics:
        print(f"  {m.name}: {m.value} (target: {m.target}) - {m.status.value}")
    print(f"\nRecommendations:")
    for r in result.recommendations:
        print(f"  - {r}")
