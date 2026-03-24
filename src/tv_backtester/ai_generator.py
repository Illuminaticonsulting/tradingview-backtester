"""
AI Strategy Generator Module
============================
Uses Claude or DeepSeek R1 to generate and iterate on Pine Script trading strategies.
"""

import os
import json
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import yaml


@dataclass
class StrategyRequest:
    """Request for strategy generation."""
    strategy_type: str  # trend_following, mean_reversion, breakout, momentum, sma_bounce
    timeframe: str  # e.g., "15" for 15min
    symbol: str  # e.g., "BYBIT:BTCUSDT.P"
    risk_params: Dict[str, float]  # sl_atr_mult, tp_rr, etc.
    additional_context: str = ""  # User hints or requirements
    previous_results: Optional[Dict] = None  # For iteration


@dataclass
class StrategyResponse:
    """Response from strategy generation."""
    pine_script: str
    strategy_name: str
    description: str
    parameters: Dict[str, Any]
    reasoning: str  # AI's reasoning for the strategy
    iteration: int


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    def generate_strategy(self, request: StrategyRequest) -> StrategyResponse:
        """Generate a Pine Script strategy."""
        pass
    
    @abstractmethod
    def improve_strategy(self, 
                         current_strategy: str,
                         backtest_results: Dict,
                         target_metrics: Dict) -> StrategyResponse:
        """Improve an existing strategy based on backtest results."""
        pass


class ClaudeProvider(AIProvider):
    """Claude API provider for strategy generation."""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022", 
                 max_tokens: int = 4096, temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Import anthropic only when needed
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("Please install anthropic: pip install anthropic")
    
    def _get_system_prompt(self) -> str:
        return """You are an expert Pine Script developer and quantitative trading strategist.
Your task is to generate profitable, well-structured Pine Script v5 trading strategies.

CRITICAL RULES:
1. ALWAYS use Pine Script version 5 (start with //@version=5)
2. Use strategy() for backtestable strategies, NOT indicator()
3. ALL function calls MUST be on a SINGLE LINE - no multiline function calls
4. Conditions with 'and' must be on ONE line: condition = a and b and c
5. Include proper risk management (stop loss, take profit)
6. Use ATR for dynamic position sizing
7. Include strategy.exit() calls with proper naming

SINGLE LINE FORMAT EXAMPLES (REQUIRED):
✅ strategy("My Strategy", overlay=true, initial_capital=10000, default_qty_type=strategy.percent_of_equity, default_qty_value=100, commission_type=strategy.commission.percent, commission_value=0.06)
✅ longCondition = close > sma45 and slope > 0.002 and proximity < atrVal * 0.8
✅ strategy.exit("Long Exit", "Long", stop=longStop, limit=longTP, comment="SL/TP")

❌ NEVER DO THIS:
strategy("My Strategy",
    overlay=true,
    initial_capital=10000)

Output your Pine Script code in a ```pinescript code block.
Also provide a JSON block with strategy metadata:
```json
{
    "name": "Strategy Name",
    "description": "Brief description",
    "parameters": {"param1": value1},
    "reasoning": "Why this strategy should work"
}
```"""

    def generate_strategy(self, request: StrategyRequest) -> StrategyResponse:
        """Generate a new Pine Script strategy."""
        
        prompt = self._build_generation_prompt(request)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self._get_system_prompt(),
            messages=[{"role": "user", "content": prompt}]
        )
        
        return self._parse_response(response.content[0].text, iteration=1)
    
    def improve_strategy(self, 
                         current_strategy: str,
                         backtest_results: Dict,
                         target_metrics: Dict) -> StrategyResponse:
        """Improve strategy based on backtest results."""
        
        prompt = self._build_improvement_prompt(
            current_strategy, backtest_results, target_metrics
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self._get_system_prompt(),
            messages=[{"role": "user", "content": prompt}]
        )
        
        iteration = backtest_results.get("iteration", 1) + 1
        return self._parse_response(response.content[0].text, iteration=iteration)
    
    def _build_generation_prompt(self, request: StrategyRequest) -> str:
        return f"""Generate a Pine Script v5 trading strategy with these requirements:

STRATEGY TYPE: {request.strategy_type}
TIMEFRAME: {request.timeframe} minutes
SYMBOL: {request.symbol}

RISK PARAMETERS:
- Stop Loss: {request.risk_params.get('sl_atr_mult', 1.8)} x ATR
- Take Profit RR: {request.risk_params.get('tp_rr', 2.0)}
- Break-even at: {request.risk_params.get('be_trigger_pct', 0.9)}%
- Trailing stop at: {request.risk_params.get('trail_trigger_pct', 1.5)}%

ADDITIONAL CONTEXT:
{request.additional_context or "None"}

Generate a complete, working Pine Script v5 strategy. Remember:
- ALL function calls must be on ONE LINE
- Include proper entry/exit logic
- Use ATR-based stops
- Include clear comments"""

    def _build_improvement_prompt(self, current_strategy: str, 
                                   backtest_results: Dict,
                                   target_metrics: Dict) -> str:
        return f"""Improve this Pine Script strategy based on backtest results:

CURRENT STRATEGY:
```pinescript
{current_strategy}
```

BACKTEST RESULTS:
- Net Profit: {backtest_results.get('net_profit', 'N/A')}
- Win Rate: {backtest_results.get('win_rate', 'N/A')}%
- Profit Factor: {backtest_results.get('profit_factor', 'N/A')}
- Max Drawdown: {backtest_results.get('max_drawdown', 'N/A')}%
- Total Trades: {backtest_results.get('total_trades', 'N/A')}
- Sharpe Ratio: {backtest_results.get('sharpe_ratio', 'N/A')}

TARGET METRICS:
- Min Win Rate: {target_metrics.get('min_win_rate', 45)}%
- Min Profit Factor: {target_metrics.get('min_profit_factor', 1.3)}
- Max Drawdown: {target_metrics.get('max_drawdown', 25)}%
- Min Trades: {target_metrics.get('min_trades', 50)}

AREAS TO IMPROVE:
{self._identify_weaknesses(backtest_results, target_metrics)}

Generate an improved version that addresses these weaknesses.
Remember: ALL function calls must be on ONE LINE."""

    def _identify_weaknesses(self, results: Dict, targets: Dict) -> str:
        weaknesses = []
        
        win_rate = results.get('win_rate', 0)
        if isinstance(win_rate, str):
            win_rate = float(win_rate.replace('%', ''))
        if win_rate < targets.get('min_win_rate', 45):
            weaknesses.append(f"- Win rate ({win_rate}%) below target ({targets.get('min_win_rate', 45)}%)")
        
        pf = results.get('profit_factor', 0)
        if isinstance(pf, str):
            pf = float(pf)
        if pf < targets.get('min_profit_factor', 1.3):
            weaknesses.append(f"- Profit factor ({pf}) below target ({targets.get('min_profit_factor', 1.3)})")
        
        dd = results.get('max_drawdown', 100)
        if isinstance(dd, str):
            dd = float(dd.replace('%', ''))
        if dd > targets.get('max_drawdown', 25):
            weaknesses.append(f"- Drawdown ({dd}%) exceeds target ({targets.get('max_drawdown', 25)}%)")
        
        trades = results.get('total_trades', 0)
        if isinstance(trades, str):
            trades = int(trades)
        if trades < targets.get('min_trades', 50):
            weaknesses.append(f"- Too few trades ({trades}) for statistical significance")
        
        return "\n".join(weaknesses) if weaknesses else "Strategy meets all targets - optimize for better performance"

    def _parse_response(self, text: str, iteration: int) -> StrategyResponse:
        """Parse AI response to extract Pine Script and metadata."""
        
        # Extract Pine Script
        pine_match = re.search(r'```pinescript\s*(.*?)\s*```', text, re.DOTALL)
        if not pine_match:
            pine_match = re.search(r'```pine\s*(.*?)\s*```', text, re.DOTALL)
        if not pine_match:
            pine_match = re.search(r'```\s*(//@version=5.*?)\s*```', text, re.DOTALL)
        
        pine_script = pine_match.group(1).strip() if pine_match else ""
        
        # Extract JSON metadata
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        metadata = {}
        if json_match:
            try:
                metadata = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        return StrategyResponse(
            pine_script=pine_script,
            strategy_name=metadata.get("name", f"AI_Strategy_v{iteration}"),
            description=metadata.get("description", "AI-generated strategy"),
            parameters=metadata.get("parameters", {}),
            reasoning=metadata.get("reasoning", ""),
            iteration=iteration
        )


class DeepSeekProvider(AIProvider):
    """DeepSeek R1 API provider for strategy generation."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1",
                 model: str = "deepseek-reasoner", max_tokens: int = 8192,
                 temperature: float = 0.6):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Use OpenAI client for DeepSeek (compatible API)
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
    
    def _get_system_prompt(self) -> str:
        # Same as Claude but optimized for DeepSeek R1's reasoning
        return """You are an expert Pine Script developer and quantitative trading strategist.
Generate profitable, well-structured Pine Script v5 trading strategies.

CRITICAL RULES:
1. Use Pine Script version 5 (//@version=5)
2. Use strategy() for backtestable strategies
3. ALL function calls MUST be on a SINGLE LINE
4. Conditions must be on ONE line: condition = a and b and c
5. Include ATR-based risk management

REQUIRED FORMAT:
- strategy() call on ONE line
- strategy.entry() on ONE line
- strategy.exit() on ONE line

Output Pine Script in ```pinescript block and metadata in ```json block."""

    def generate_strategy(self, request: StrategyRequest) -> StrategyResponse:
        """Generate using DeepSeek R1."""
        
        prompt = f"""Generate a {request.strategy_type} Pine Script v5 strategy for:
- Timeframe: {request.timeframe}min
- Symbol: {request.symbol}
- Stop Loss: {request.risk_params.get('sl_atr_mult', 1.8)} x ATR
- TP RR: {request.risk_params.get('tp_rr', 2.0)}

{request.additional_context or ""}

Use deep reasoning to design an effective strategy."""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ]
        )
        
        return self._parse_response(response.choices[0].message.content, iteration=1)
    
    def improve_strategy(self, current_strategy: str, backtest_results: Dict,
                         target_metrics: Dict) -> StrategyResponse:
        """Improve strategy using DeepSeek R1."""
        
        prompt = f"""Improve this strategy based on backtest results:

```pinescript
{current_strategy}
```

Results: Win Rate {backtest_results.get('win_rate')}%, PF {backtest_results.get('profit_factor')}, DD {backtest_results.get('max_drawdown')}%

Targets: WR>{target_metrics.get('min_win_rate')}%, PF>{target_metrics.get('min_profit_factor')}, DD<{target_metrics.get('max_drawdown')}%

Use deep reasoning to identify improvements."""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ]
        )
        
        iteration = backtest_results.get("iteration", 1) + 1
        return self._parse_response(response.choices[0].message.content, iteration=iteration)
    
    def _parse_response(self, text: str, iteration: int) -> StrategyResponse:
        """Parse response - same logic as Claude."""
        
        pine_match = re.search(r'```pinescript\s*(.*?)\s*```', text, re.DOTALL)
        if not pine_match:
            pine_match = re.search(r'```pine\s*(.*?)\s*```', text, re.DOTALL)
        
        pine_script = pine_match.group(1).strip() if pine_match else ""
        
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        metadata = {}
        if json_match:
            try:
                metadata = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        return StrategyResponse(
            pine_script=pine_script,
            strategy_name=metadata.get("name", f"DeepSeek_Strategy_v{iteration}"),
            description=metadata.get("description", "DeepSeek R1 generated strategy"),
            parameters=metadata.get("parameters", {}),
            reasoning=metadata.get("reasoning", ""),
            iteration=iteration
        )


def create_ai_provider(config: Dict) -> AIProvider:
    """Factory function to create the appropriate AI provider."""
    
    provider_name = config.get("ai_provider", "claude")
    
    if provider_name == "claude":
        claude_config = config.get("claude", {})
        api_key = claude_config.get("api_key", "")
        
        # Resolve environment variable
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        
        if not api_key:
            raise ValueError("Claude API key not found. Set ANTHROPIC_API_KEY environment variable.")
        
        return ClaudeProvider(
            api_key=api_key,
            model=claude_config.get("model", "claude-3-5-sonnet-20241022"),
            max_tokens=claude_config.get("max_tokens", 4096),
            temperature=claude_config.get("temperature", 0.7)
        )
    
    elif provider_name == "deepseek":
        ds_config = config.get("deepseek", {})
        api_key = ds_config.get("api_key", "")
        
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        
        if not api_key:
            raise ValueError("DeepSeek API key not found. Set DEEPSEEK_API_KEY environment variable.")
        
        return DeepSeekProvider(
            api_key=api_key,
            base_url=ds_config.get("base_url", "https://api.deepseek.com/v1"),
            model=ds_config.get("model", "deepseek-reasoner"),
            max_tokens=ds_config.get("max_tokens", 8192),
            temperature=ds_config.get("temperature", 0.6)
        )
    
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}")


if __name__ == "__main__":
    # Quick test
    import yaml
    
    with open("config/backtester_config.yaml") as f:
        config = yaml.safe_load(f)
    
    provider = create_ai_provider(config)
    
    request = StrategyRequest(
        strategy_type="sma_bounce",
        timeframe="15",
        symbol="BYBIT:BTCUSDT.P",
        risk_params={"sl_atr_mult": 1.8, "tp_rr": 2.0}
    )
    
    response = provider.generate_strategy(request)
    print(f"Generated: {response.strategy_name}")
    print(response.pine_script[:500])
