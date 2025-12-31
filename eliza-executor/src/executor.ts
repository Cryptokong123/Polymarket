/**
 * Signal Executor - Watches for signals from Python and executes trades
 * This is the main entry point for the TypeScript executor layer.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as chokidar from 'chokidar';
import { ethers } from 'ethers';

import { loadConfig, validateConfig } from './config';
import { logger } from './logger';
import type {
  TradingSignal,
  ExecutionResult,
  Position,
  ExecutorConfig,
  OrderParams,
} from './types';

/**
 * Signal Executor class
 * Watches for signals from Python research layer and executes trades
 */
class SignalExecutor {
  private config: ExecutorConfig;
  private wallet: ethers.Wallet;
  private activePositions: Map<string, Position>;
  private processingSignals: Set<string>;
  private watcher: chokidar.FSWatcher | null = null;

  constructor() {
    // Load and validate configuration
    this.config = loadConfig();
    const validation = validateConfig(this.config);

    if (!validation.valid) {
      validation.errors.forEach((err) => logger.error(err));
      throw new Error('Invalid configuration');
    }

    // Initialize wallet
    this.wallet = new ethers.Wallet(this.config.privateKey);

    // Initialize tracking
    this.activePositions = new Map();
    this.processingSignals = new Set();

    // Ensure directories exist
    this.ensureDirectories();

    logger.info('Signal Executor initialized', {
      wallet: this.wallet.address,
      maxPositions: this.config.maxPositions,
      dryRun: this.config.dryRun,
    });
  }

  /**
   * Ensure required directories exist
   */
  private ensureDirectories(): void {
    const dirs = [
      this.config.signalsDir,
      this.config.executedDir,
      this.config.resultsDir,
    ];

    for (const dir of dirs) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
        logger.info(`Created directory: ${dir}`);
      }
    }
  }

  /**
   * Read and parse a signal file
   */
  private readSignal(filepath: string): TradingSignal | null {
    try {
      const content = fs.readFileSync(filepath, 'utf-8');
      return JSON.parse(content) as TradingSignal;
    } catch (error) {
      logger.error(`Failed to read signal file: ${filepath}`, { error });
      return null;
    }
  }

  /**
   * Validate if signal is still valid
   */
  private validateSignal(signal: TradingSignal): { valid: boolean; reason?: string } {
    // Check expiration
    const expiresAt = new Date(signal.expires_at);
    if (expiresAt < new Date()) {
      return { valid: false, reason: 'Signal expired' };
    }

    // Check if already processing
    if (this.processingSignals.has(signal.signal_id)) {
      return { valid: false, reason: 'Signal already processing' };
    }

    // Check position limits
    if (this.activePositions.size >= this.config.maxPositions) {
      return { valid: false, reason: 'Max positions reached' };
    }

    // Check if we already have a position in this market
    if (this.activePositions.has(signal.market_id)) {
      return { valid: false, reason: 'Already have position in this market' };
    }

    // Check token ID
    if (!signal.token_id) {
      return { valid: false, reason: 'Missing token ID' };
    }

    return { valid: true };
  }

  /**
   * Get current price for a token
   * Uses the CLOB API midpoint endpoint
   */
  private async getCurrentPrice(tokenId: string): Promise<number> {
    try {
      const response = await fetch(
        `${this.config.clobUrl}/midpoint?token_id=${tokenId}`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return parseFloat(data.mid || '0.5');
    } catch (error) {
      logger.error(`Failed to get current price for ${tokenId}`, { error });
      return 0.5; // Default fallback
    }
  }

  /**
   * Execute a trading signal
   */
  async executeSignal(signal: TradingSignal): Promise<ExecutionResult> {
    const result: ExecutionResult = {
      signal_id: signal.signal_id,
      success: false,
      timestamp: new Date().toISOString(),
    };

    // Mark as processing
    this.processingSignals.add(signal.signal_id);

    try {
      // Validate signal
      const validation = this.validateSignal(signal);
      if (!validation.valid) {
        result.error = validation.reason;
        return result;
      }

      // Get current price
      const currentPrice = await this.getCurrentPrice(signal.token_id);
      logger.info(`Current price for ${signal.token_type}: ${currentPrice}`);

      // Check price limits
      if (signal.side === 'BUY' && currentPrice > signal.max_price) {
        result.error = `Price too high: ${currentPrice} > ${signal.max_price}`;
        return result;
      }

      if (signal.side === 'SELL' && currentPrice < signal.min_price) {
        result.error = `Price too low: ${currentPrice} < ${signal.min_price}`;
        return result;
      }

      // Calculate adjusted size considering slippage
      const adjustedPrice =
        signal.side === 'BUY'
          ? Math.min(currentPrice * (1 + this.config.maxSlippage), signal.max_price)
          : Math.max(currentPrice * (1 - this.config.maxSlippage), signal.min_price);

      logger.info(`Executing ${signal.side} order for ${signal.token_type}`, {
        market: signal.market_question.substring(0, 50),
        size: signal.suggested_size,
        price: adjustedPrice,
      });

      if (this.config.dryRun) {
        // Simulate successful trade
        logger.info('[DRY RUN] Simulating trade execution');
        result.success = true;
        result.order_id = `dry_run_${Date.now()}`;
        result.filled_price = currentPrice;
        result.filled_size = signal.suggested_size;
      } else {
        // Execute real trade
        const orderResult = await this.placeOrder({
          tokenID: signal.token_id,
          price: adjustedPrice,
          size: signal.suggested_size,
          side: signal.side,
        });

        if (orderResult.success) {
          result.success = true;
          result.order_id = orderResult.orderId;
          result.filled_price = currentPrice;
          result.filled_size = signal.suggested_size;

          // Track position
          this.activePositions.set(signal.market_id, {
            market_id: signal.market_id,
            token_id: signal.token_id,
            token_type: signal.token_type,
            size: signal.suggested_size,
            entry_price: currentPrice,
            current_price: currentPrice,
            unrealized_pnl: 0,
            entry_time: new Date().toISOString(),
            signal_id: signal.signal_id,
          });

          logger.info('[OK] Order placed successfully', { orderId: orderResult.orderId });
        } else {
          result.error = orderResult.error;
          logger.error('[ERROR] Order failed', { error: orderResult.error });
        }
      }
    } catch (error) {
      result.error = error instanceof Error ? error.message : 'Unknown error';
      logger.error('[ERROR] Execution failed', { error: result.error });
    } finally {
      // Remove from processing
      this.processingSignals.delete(signal.signal_id);
    }

    return result;
  }

  /**
   * Place an order via CLOB API
   */
  private async placeOrder(
    params: OrderParams
  ): Promise<{ success: boolean; orderId?: string; error?: string }> {
    try {
      // Note: This is a simplified implementation
      // Real implementation would use @polymarket/clob-client
      // which handles signing and authentication

      // For now, we'll use direct API calls with signing
      logger.info('Placing order', params);

      // The actual implementation would:
      // 1. Create order object
      // 2. Sign with wallet
      // 3. Submit to CLOB API
      // 4. Return order ID

      // Placeholder for real implementation
      return {
        success: false,
        error: 'Direct API order placement requires @polymarket/clob-client setup',
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Order placement failed',
      };
    }
  }

  /**
   * Save execution result
   */
  private saveResult(result: ExecutionResult): void {
    const filename = `${result.signal_id}_result.json`;
    const filepath = path.join(this.config.resultsDir, filename);

    try {
      fs.writeFileSync(filepath, JSON.stringify(result, null, 2));
      logger.info(`Result saved: ${filepath}`);
    } catch (error) {
      logger.error(`Failed to save result: ${filepath}`, { error });
    }
  }

  /**
   * Move signal to executed directory
   */
  private moveToExecuted(signalPath: string): void {
    const filename = path.basename(signalPath);
    const destPath = path.join(this.config.executedDir, filename);

    try {
      fs.renameSync(signalPath, destPath);
      logger.debug(`Moved signal to: ${destPath}`);
    } catch (error) {
      logger.error(`Failed to move signal: ${signalPath}`, { error });
    }
  }

  /**
   * Process a signal file
   */
  async processSignalFile(filepath: string): Promise<void> {
    const filename = path.basename(filepath);
    logger.info(`Processing signal file: ${filename}`);

    // Read signal
    const signal = this.readSignal(filepath);
    if (!signal) {
      return;
    }

    logger.info(`Signal: ${signal.signal_id}`, {
      market: signal.market_question.substring(0, 50),
      side: signal.side,
      type: signal.token_type,
      ev: `${(signal.expected_value * 100).toFixed(2)}%`,
    });

    // Execute signal
    const result = await this.executeSignal(signal);

    // Save result
    this.saveResult(result);

    // Move signal to executed directory
    this.moveToExecuted(filepath);

    if (result.success) {
      logger.info('[OK] Signal executed successfully');
    } else {
      logger.warn(`[WARN] Signal execution failed: ${result.error}`);
    }
  }

  /**
   * Process existing signals in directory
   */
  async processExistingSignals(): Promise<void> {
    const files = fs.readdirSync(this.config.signalsDir).filter((f) => f.endsWith('.json'));

    logger.info(`Found ${files.length} existing signals`);

    for (const file of files) {
      const filepath = path.join(this.config.signalsDir, file);
      await this.processSignalFile(filepath);
    }
  }

  /**
   * Start watching for new signals
   */
  watch(): void {
    logger.info(`Watching for signals in: ${this.config.signalsDir}`);

    this.watcher = chokidar.watch(this.config.signalsDir, {
      persistent: true,
      ignoreInitial: true,
      awaitWriteFinish: {
        stabilityThreshold: 500,
        pollInterval: 100,
      },
    });

    this.watcher.on('add', async (filepath) => {
      if (filepath.endsWith('.json') && !filepath.includes('.gitkeep')) {
        // Small delay to ensure file is fully written
        await new Promise((resolve) => setTimeout(resolve, 500));
        await this.processSignalFile(filepath);
      }
    });

    this.watcher.on('error', (error) => {
      logger.error('Watcher error', { error });
    });
  }

  /**
   * Stop watching
   */
  async stop(): Promise<void> {
    if (this.watcher) {
      await this.watcher.close();
      this.watcher = null;
    }
    logger.info('Executor stopped');
  }

  /**
   * Main run loop
   */
  async run(): Promise<void> {
    logger.info('=' .repeat(60));
    logger.info('POLYMARKET SIGNAL EXECUTOR STARTED');
    logger.info('='.repeat(60));
    logger.info(`Wallet: ${this.wallet.address}`);
    logger.info(`CLOB URL: ${this.config.clobUrl}`);
    logger.info(`Max Positions: ${this.config.maxPositions}`);
    logger.info(`Dry Run: ${this.config.dryRun}`);
    logger.info('='.repeat(60));

    // Process existing signals
    await this.processExistingSignals();

    // Start watching for new signals
    this.watch();

    logger.info('[BOT] Signal Executor is running...');
    logger.info('Waiting for signals from Python research layer...');

    // Keep process alive
    process.on('SIGINT', async () => {
      logger.info('\nShutting down...');
      await this.stop();
      process.exit(0);
    });

    process.on('SIGTERM', async () => {
      logger.info('\nReceived SIGTERM...');
      await this.stop();
      process.exit(0);
    });

    // Keep the process running
    await new Promise(() => {});
  }

  /**
   * Get current portfolio state
   */
  getPortfolioState() {
    return {
      positions: Array.from(this.activePositions.values()),
      position_count: this.activePositions.size,
      processing_count: this.processingSignals.size,
    };
  }
}

// Main entry point
async function main() {
  try {
    const executor = new SignalExecutor();
    await executor.run();
  } catch (error) {
    logger.error('Failed to start executor', { error });
    process.exit(1);
  }
}

main();
