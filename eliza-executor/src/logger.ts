/**
 * Logging configuration for the executor
 */

import * as winston from 'winston';
import * as path from 'path';

const logLevel = process.env.LOG_LEVEL || 'info';
const logFile = process.env.LOG_FILE || path.join(__dirname, '../../data/executor.log');

/**
 * Custom format for console output
 */
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.colorize(),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    let msg = `${timestamp} [${level}] ${message}`;
    if (Object.keys(meta).length > 0) {
      msg += ` ${JSON.stringify(meta)}`;
    }
    return msg;
  })
);

/**
 * Format for file output
 */
const fileFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.json()
);

/**
 * Create logger instance
 */
export const logger = winston.createLogger({
  level: logLevel,
  transports: [
    // Console transport
    new winston.transports.Console({
      format: consoleFormat,
    }),
    // File transport
    new winston.transports.File({
      filename: logFile,
      format: fileFormat,
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 5,
    }),
  ],
});

/**
 * Create child logger with context
 */
export function createChildLogger(context: string): winston.Logger {
  return logger.child({ context });
}

export default logger;
