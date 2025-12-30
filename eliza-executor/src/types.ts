/**
 * Types for the Polymarket Trading Bot Executor
 */

/**
 * Trading signal from the Python research layer
 */
export interface TradingSignal {
  signal_id: string;
  timestamp: string;
  market_id: string;
  token_id: string;
  market_question: string;
  side: 'BUY' | 'SELL';
  token_type: 'YES' | 'NO';
  current_price: number;
  predicted_probability: number;
  expected_value: number;
  confidence: number;
  reasoning: string;
  suggested_size: number;
  max_price: number;
  min_price: number;
  expires_at: string;
  status?: string;
  metadata: {
    liquidity?: number;
    volume_24h?: number;
    key_factors?: string[];
    risk_factors?: string[];
    sentiment?: string;
    [key: string]: unknown;
  };
}

/**
 * Result of executing a trading signal
 */
export interface ExecutionResult {
  signal_id: string;
  success: boolean;
  order_id?: string;
  filled_price?: number;
  filled_size?: number;
  error?: string;
  timestamp: string;
  gas_used?: number;
  transaction_hash?: string;
}

/**
 * Current position in a market
 */
export interface Position {
  market_id: string;
  token_id: string;
  token_type: 'YES' | 'NO';
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  entry_time: string;
  signal_id: string;
}

/**
 * Order book entry
 */
export interface OrderBookEntry {
  price: string;
  size: string;
}

/**
 * Order book
 */
export interface OrderBook {
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  market: string;
  asset_id: string;
  timestamp: string;
}

/**
 * CLOB API credentials
 */
export interface ApiCredentials {
  apiKey: string;
  apiSecret: string;
  apiPassphrase: string;
}

/**
 * Executor configuration
 */
export interface ExecutorConfig {
  // Wallet
  privateKey: string;
  walletAddress: string;

  // API
  clobUrl: string;
  chainId: number;

  // Trading
  maxPositions: number;
  maxSlippage: number;
  dryRun: boolean;

  // Paths
  signalsDir: string;
  executedDir: string;
  resultsDir: string;

  // Retry
  maxRetries: number;
  retryDelayMs: number;
}

/**
 * Order parameters
 */
export interface OrderParams {
  tokenID: string;
  price: number;
  size: number;
  side: 'BUY' | 'SELL';
  feeRateBps?: number;
}

/**
 * Order response from CLOB API
 */
export interface OrderResponse {
  orderID: string;
  status: string;
  [key: string]: unknown;
}

/**
 * Portfolio state
 */
export interface PortfolioState {
  positions: Position[];
  total_value: number;
  available_balance: number;
  total_pnl: number;
  daily_pnl: number;
  timestamp: string;
}

/**
 * Signal processing status
 */
export enum SignalStatus {
  PENDING = 'pending',
  EXECUTING = 'executing',
  EXECUTED = 'executed',
  FAILED = 'failed',
  EXPIRED = 'expired',
  CANCELLED = 'cancelled',
}
