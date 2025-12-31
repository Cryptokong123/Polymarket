/**
 * Configuration for the Polymarket Executor
 */

import * as path from 'path';
import * as fs from 'fs';
import * as dotenv from 'dotenv';
import type { ExecutorConfig } from './types';

// Try multiple .env locations
const envPaths = [
  path.join(__dirname, '../../.env'),      // From dist/ folder
  path.join(__dirname, '../.env'),          // From src/ folder (ts-node)
  path.join(process.cwd(), '.env'),         // Current working directory
  path.join(process.cwd(), '../.env'),      // Parent of working directory
];

let envLoaded = false;
for (const envPath of envPaths) {
  if (fs.existsSync(envPath)) {
    const result = dotenv.config({ path: envPath });
    if (!result.error) {
      envLoaded = true;
      break;
    }
  }
}

if (!envLoaded) {
  // Try default dotenv loading (looks in process.cwd())
  dotenv.config();
}

/**
 * Get environment variable with optional default
 */
function getEnv(key: string, defaultValue?: string): string {
  const value = process.env[key];
  if (value === undefined || value === '') {
    if (defaultValue !== undefined) {
      return defaultValue;
    }
    // Return empty string for required fields - will be caught by validateConfig
    return '';
  }
  return value;
}

/**
 * Get numeric environment variable
 */
function getEnvNumber(key: string, defaultValue: number): number {
  const value = process.env[key];
  if (value === undefined) {
    return defaultValue;
  }
  const parsed = parseFloat(value);
  if (isNaN(parsed)) {
    return defaultValue;
  }
  return parsed;
}

/**
 * Get boolean environment variable
 */
function getEnvBool(key: string, defaultValue: boolean): boolean {
  const value = process.env[key];
  if (value === undefined) {
    return defaultValue;
  }
  return value.toLowerCase() === 'true';
}

/**
 * Load and validate executor configuration
 */
export function loadConfig(): ExecutorConfig {
  const baseDir = path.join(__dirname, '../..');

  const config: ExecutorConfig = {
    // Wallet
    privateKey: getEnv('POLYGON_WALLET_PRIVATE_KEY'),
    walletAddress: getEnv('WALLET_ADDRESS'),

    // API
    clobUrl: getEnv('CLOB_API_URL', 'https://clob.polymarket.com'),
    chainId: 137, // Polygon mainnet

    // Trading
    maxPositions: getEnvNumber('MAX_POSITIONS', 10),
    maxSlippage: getEnvNumber('MAX_SLIPPAGE', 0.02),
    dryRun: getEnvBool('DRY_RUN', false),

    // Paths
    signalsDir: path.join(baseDir, 'shared/signals'),
    executedDir: path.join(baseDir, 'shared/executed'),
    resultsDir: path.join(baseDir, 'shared/results'),

    // Retry
    maxRetries: 3,
    retryDelayMs: 1000,
  };

  return config;
}

/**
 * Validate configuration
 */
export function validateConfig(config: ExecutorConfig): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!config.privateKey) {
    errors.push('POLYGON_WALLET_PRIVATE_KEY is required - please add your private key to .env');
  } else if (!config.privateKey.startsWith('0x')) {
    // Auto-fix common issue
    config.privateKey = '0x' + config.privateKey;
  }

  if (!config.walletAddress) {
    errors.push('WALLET_ADDRESS is required - please add your wallet address to .env');
  } else if (!config.walletAddress.startsWith('0x')) {
    errors.push('WALLET_ADDRESS must start with 0x');
  }

  if (config.maxPositions < 1) {
    errors.push('MAX_POSITIONS must be at least 1');
  }

  if (config.maxSlippage < 0 || config.maxSlippage > 1) {
    errors.push('MAX_SLIPPAGE must be between 0 and 1');
  }

  if (errors.length > 0) {
    console.log('\n[CONFIG ERROR] Missing required wallet configuration.');
    console.log('Please edit your .env file and add:');
    console.log('  POLYGON_WALLET_PRIVATE_KEY=0x...');
    console.log('  WALLET_ADDRESS=0x...\n');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export default loadConfig;
