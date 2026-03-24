# TradingView AI Backtester 🤖📈

**Autonomous AI-powered trading strategy generation and backtesting for TradingView.**

This tool uses Claude or DeepSeek R1 to generate Pine Script trading strategies, automatically backtest them in TradingView, analyze results, and iteratively improve until performance targets are met.

## ✨ Features

- **AI Strategy Generation**: Generate Pine Script strategies using Claude (Anthropic) or DeepSeek R1
- **Automatic Backtesting**: Browser automation to run backtests in TradingView
- **Intelligent Iteration**: Analyzes results and improves strategies until targets are met
- **Multi-Symbol Testing**: Test across multiple symbols automatically
- **Pine Script Validation**: Pre-flight syntax checking to catch errors before compilation
- **Comprehensive Reporting**: CSV exports, screenshots, and evolution history

## 🚀 Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/Illuminaticonsulting/tradingview-backtester.git
cd tradingview-backtester

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Configuration

1. Copy the example config:
```bash
cp config/backtester_config.yaml config/my_config.yaml
```

2. Set your API key:
```bash
# For Claude (recommended)
export ANTHROPIC_API_KEY=your_key_here

# OR for DeepSeek R1
export DEEPSEEK_API_KEY=your_key_here
```

3. Edit the config to select your provider and settings.

### Run the Agent

```bash
# Run with default settings (uses config file)
python -m tv_backtester.main

# Generate and test a specific strategy type
python -m tv_backtester.main run --strategy sma_bounce

# Use DeepSeek R1 instead of Claude
python -m tv_backtester.main run --provider deepseek

# Run in headless mode (for servers)
python -m tv_backtester.main run --headless

# Test on specific symbols
python -m tv_backtester.main run --symbols BYBIT:BTCUSDT.P BYBIT:ETHUSDT.P
```

## 📋 Commands

### `run` - Run Autonomous Agent (default)
```bash
python -m tv_backtester.main run [options]
```

Options:
- `--strategy`, `-s`: Strategy types to generate (e.g., `sma_bounce trend_following`)
- `--symbols`: Symbols to test (e.g., `BYBIT:BTCUSDT.P`)
- `--provider`, `-p`: AI provider (`claude` or `deepseek`)
- `--model`, `-m`: Specific model to use
- `--iterations`, `-i`: Max iterations per strategy
- `--headless`: Run browser headlessly
- `--output`, `-o`: Results output directory

### `generate` - Generate Strategy Only
```bash
python -m tv_backtester.main generate --strategy momentum
```

Generates a strategy without running backtests.

### `validate` - Validate Pine Script
```bash
python -m tv_backtester.main validate my_strategy.pine --fix
```

Validates a Pine Script file and optionally fixes common issues.

### `backtest` - Backtest Existing Strategy
```bash
python -m tv_backtester.main backtest my_strategy.pine --symbols BYBIT:BTCUSDT.P
```

Backtests an existing Pine Script file.

## ⚙️ Configuration

Edit `config/backtester_config.yaml`:

```yaml
# AI Provider: "claude" or "deepseek"
ai_provider: "claude"

# Claude settings
claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-3-5-sonnet-20241022"  # Options: claude-3-haiku (cheap), claude-3-5-sonnet (balanced)
  
# DeepSeek settings
deepseek:
  api_key: "${DEEPSEEK_API_KEY}"
  model: "deepseek-reasoner"  # DeepSeek R1

# Target metrics (strategy must meet these)
strategy_generation:
  min_win_rate: 45.0
  min_profit_factor: 1.3
  max_drawdown: 25.0
  min_trades: 50
  max_iterations: 10

# Symbols to test
symbols:
  - "BYBIT:BTCUSDT.P"
  - "BYBIT:ETHUSDT.P"
  # ... more symbols
```

## 💰 AI Provider Pricing

### Claude (Anthropic)
| Model | Input | Output | Best For |
|-------|-------|--------|----------|
| claude-3-haiku | $0.25/M | $1.25/M | Fast iteration, low cost |
| claude-3-5-sonnet | $3/M | $15/M | Production quality |
| claude-sonnet-4 | $3/M | $15/M | Most capable |

### DeepSeek R1
| Model | Input | Output | Best For |
|-------|-------|--------|----------|
| deepseek-reasoner | $0.55/M | $2.19/M | Deep reasoning, balanced cost |

**Recommended**: Start with `claude-3-haiku` for development, use `claude-3-5-sonnet` for production strategies.

## 📁 Project Structure

```
tradingview-backtester/
├── config/
│   └── backtester_config.yaml   # Main configuration
├── src/tv_backtester/
│   ├── __init__.py
│   ├── main.py                  # CLI entry point
│   ├── ai_generator.py          # Claude/DeepSeek strategy generation
│   ├── pine_validator.py        # Pine Script syntax validation
│   ├── browser_controller.py    # Playwright TradingView automation
│   ├── metric_analyzer.py       # Backtest result analysis
│   └── agent.py                 # Autonomous orchestration loop
├── strategies/                   # Generated Pine Scripts
├── results/                      # Backtest results and reports
├── tests/                        # Unit tests
├── requirements.txt
└── README.md
```

## 🔧 How It Works

1. **Generate**: AI creates a Pine Script strategy based on specified type and parameters
2. **Validate**: Pre-flight checks catch syntax errors before TradingView
3. **Compile**: Browser automation pastes and compiles the script in TradingView
4. **Backtest**: Extract metrics from TradingView's Strategy Tester
5. **Analyze**: Compare metrics against targets (win rate, profit factor, drawdown)
6. **Iterate**: If targets not met, AI improves the strategy based on analysis
7. **Repeat**: Continue until targets are met or max iterations reached

## 📊 Output

Results are saved to the `results/` directory:
- `backtest_results.csv`: Metrics for all tested strategies
- `{strategy}_evolution.json`: Full iteration history
- `{strategy}_best.pine`: Best performing Pine Script
- `{strategy}_v{n}.png`: Screenshots of each iteration
- `summary.json`: Overall summary

## 🛠️ Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Type checking
mypy src/
```

## 📝 License

MIT License - see LICENSE file.

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md first.
