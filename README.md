# Polymarket Autonomous Trading Bot

A fully autonomous Polymarket prediction market trading bot that combines AI-powered research and signal generation with automated trade execution.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   POLYMARKET TRADING BOT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐        ┌──────────────────────┐       │
│  │  PYTHON RESEARCH     │        │  TYPESCRIPT EXECUTOR │       │
│  │  (Signal Generator)  │        │  (Trade Executor)    │       │
│  ├──────────────────────┤        ├──────────────────────┤       │
│  │                      │        │                      │       │
│  │  1. Fetch Markets    │        │  1. Watch Signals    │       │
│  │  2. RAG News Query   │        │  2. Validate Signal  │       │
│  │  3. LLM Analysis     │   →    │  3. Check Prices     │       │
│  │  4. Calculate EV     │ JSON   │  4. Execute Order    │       │
│  │  5. Generate Signal  │ File   │  5. Track Position   │       │
│  │                      │        │                      │       │
│  └──────────────────────┘        └──────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **AI-Powered Analysis**: Uses LLMs (Claude/GPT-4) to analyze prediction markets
- **RAG Integration**: Vector store for news and context retrieval
- **Expected Value Trading**: Only trades when expected value exceeds threshold
- **Risk Management**: Position limits, price limits, and slippage protection
- **Dual-Layer Architecture**: Python for research, TypeScript for execution
- **Docker Support**: Easy deployment with Docker Compose
- **Telegram Notifications**: Optional alerts for signals and trades
- **Dry Run Mode**: Test without risking real funds

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker (optional, for containerized deployment)
- Polygon wallet with USDC.e
- LLM API key (OpenAI or Anthropic)

### Installation

1. Clone and setup:
```bash
git clone <repository-url>
cd polymarket-trading-bot
./scripts/setup.sh
```

2. Configure environment:
```bash
cp .env.example .env
nano .env  # Add your keys
```

3. Start the bot:
```bash
# With Docker (recommended)
./scripts/start.sh docker

# Or manually
./scripts/start.sh manual
```

### Dry Run Mode

Test without executing real trades:
```bash
./scripts/start.sh dry-run
```

## Configuration

### Required Settings

| Variable | Description |
|----------|-------------|
| `POLYGON_WALLET_PRIVATE_KEY` | Your Polygon wallet private key |
| `WALLET_ADDRESS` | Your wallet address |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | LLM API key |

### Trading Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_POSITION_SIZE` | 100 | Maximum USDC per trade |
| `MIN_EXPECTED_VALUE` | 0.05 | Minimum EV to trigger trade (5%) |
| `MAX_POSITIONS` | 10 | Maximum concurrent positions |
| `MIN_LIQUIDITY` | 1000 | Minimum market liquidity |
| `SCAN_INTERVAL` | 300 | Seconds between market scans |

### Optional Features

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot for notifications |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `NEWSAPI_KEY` | NewsAPI.org for news research |
| `TAVILY_API_KEY` | Tavily for web search |

## Project Structure

```
polymarket-trading-bot/
├── python-research/          # Signal generation layer
│   ├── agents/               # AI agents and analyzers
│   ├── scripts/              # Utility scripts
│   ├── signal_generator.py   # Main entry point
│   ├── config.py             # Configuration
│   └── requirements.txt      # Python dependencies
├── eliza-executor/           # Trade execution layer
│   ├── src/                  # TypeScript source
│   │   ├── executor.ts       # Main executor
│   │   ├── types.ts          # Type definitions
│   │   └── config.ts         # Configuration
│   ├── package.json          # Node dependencies
│   └── tsconfig.json         # TypeScript config
├── shared/                   # Shared data between layers
│   ├── signals/              # Pending signals (JSON)
│   ├── executed/             # Processed signals
│   └── results/              # Execution results
├── docker/                   # Docker configuration
│   ├── docker-compose.yml
│   ├── Dockerfile.research
│   └── Dockerfile.executor
├── scripts/                  # Utility scripts
│   ├── setup.sh              # Installation script
│   └── start.sh              # Launch script
├── .env.example              # Environment template
└── README.md                 # This file
```

## How It Works

### Signal Generation (Python)

1. **Market Scanning**: Fetches active markets from Polymarket's Gamma API
2. **Liquidity Filtering**: Filters markets by minimum liquidity
3. **Context Gathering**: Uses RAG to fetch relevant news and data
4. **LLM Analysis**: Sends market + context to LLM for probability estimation
5. **EV Calculation**: Calculates expected value for YES and NO positions
6. **Signal Output**: Writes signals to `shared/signals/` as JSON files

### Trade Execution (TypeScript)

1. **Signal Watching**: Monitors `shared/signals/` for new files
2. **Validation**: Checks signal expiry, position limits, price bounds
3. **Price Check**: Verifies current price against signal limits
4. **Order Execution**: Places order via Polymarket CLOB API
5. **Position Tracking**: Tracks open positions and P&L
6. **Result Logging**: Writes execution results to `shared/results/`

## API Rate Limits

Polymarket has rate limits on their APIs. Default scan interval is 5 minutes to avoid hitting limits. Adjust `SCAN_INTERVAL` carefully.

## Risk Management

- **Position Limits**: `MAX_POSITIONS` limits concurrent trades
- **Size Limits**: `MAX_POSITION_SIZE` caps individual trade size
- **EV Threshold**: `MIN_EXPECTED_VALUE` filters low-conviction trades
- **Price Limits**: Each signal includes `max_price` and `min_price`
- **Slippage Protection**: `MAX_SLIPPAGE` prevents execution at bad prices
- **Daily Loss Limit**: `MAX_DAILY_LOSS` stops trading after losses

## Monitoring

### Check Signals
```bash
# Pending signals
ls -la shared/signals/

# Executed signals
ls -la shared/executed/

# Results
cat shared/results/*.json
```

### Docker Logs
```bash
# All services
docker-compose logs -f

# Research only
docker-compose logs -f research

# Executor only
docker-compose logs -f executor
```

## Troubleshooting

### Common Issues

1. **No signals generated**: Check LLM API key and MIN_EXPECTED_VALUE threshold
2. **Orders not executing**: Verify wallet has USDC.e and allowances are set
3. **Rate limiting**: Increase SCAN_INTERVAL
4. **Price too high errors**: Market moved, signal expired

### Debug Mode
```bash
# Set in .env
LOG_LEVEL=DEBUG
```

## Legal Disclaimer

⚠️ **IMPORTANT NOTICES**:

1. **Regulatory Compliance**: Polymarket's Terms of Service prohibit US persons from trading. Ensure you comply with your local regulations.

2. **Financial Risk**: This is experimental software. Prediction markets are risky. Never trade more than you can afford to lose.

3. **No Warranty**: This software is provided "as is" without warranty. The authors are not responsible for any losses.

4. **Not Financial Advice**: This tool does not provide financial advice. Always do your own research.

## Contributing

Contributions are welcome! Please open an issue or pull request.

## License

MIT License - see LICENSE file for details.

## Resources

- [Polymarket Docs](https://docs.polymarket.com)
- [py-clob-client](https://github.com/Polymarket/py-clob-client)
- [Polymarket Agents](https://github.com/Polymarket/agents)
- [ElizaOS](https://github.com/elizaOS/eliza)
