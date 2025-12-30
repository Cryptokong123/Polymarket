"""
Notifications - Telegram and other notification integrations
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

import aiohttp

from .signal_types import TradingSignal, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Telegram configuration"""
    bot_token: str
    chat_id: str
    enabled: bool = True


class TelegramNotifier:
    """
    Sends notifications via Telegram bot.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled: bool = True,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        disable_notification: bool = False,
    ) -> bool:
        """
        Send a message via Telegram.

        Args:
            text: Message text
            parse_mode: "Markdown" or "HTML"
            disable_notification: Send silently

        Returns:
            True if successful
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled")
            return False

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured")
            return False

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_notification": disable_notification,
                },
            ) as response:
                if response.status == 200:
                    logger.debug("Telegram message sent")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Telegram API error: {error}")
                    return False

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def notify_signal(self, signal: TradingSignal) -> bool:
        """
        Send notification about a new trading signal.
        """
        message = f"""🎯 *New Trading Signal*

*Market:* {signal.market_question[:100]}

*Action:* {signal.side} {signal.token_type}
*Price:* ${signal.current_price:.4f}
*Predicted:* {signal.predicted_probability:.1%}
*EV:* {signal.expected_value:.1%}
*Confidence:* {signal.confidence:.1%}

*Size:* ${signal.suggested_size:.2f}
*Max Price:* ${signal.max_price:.4f}

*Reasoning:*
_{signal.reasoning}_

Signal ID: `{signal.signal_id}`"""

        return await self.send_message(message)

    async def notify_execution(self, result: ExecutionResult) -> bool:
        """
        Send notification about trade execution.
        """
        if result.success:
            emoji = "✅"
            status = "EXECUTED"
        else:
            emoji = "❌"
            status = "FAILED"

        message = f"""{emoji} *Trade {status}*

*Signal:* `{result.signal_id}`
*Order ID:* `{result.order_id or 'N/A'}`

"""
        if result.success:
            message += f"""*Filled Price:* ${result.filled_price:.4f}
*Filled Size:* ${result.filled_size:.2f}"""
        else:
            message += f"""*Error:* {result.error}"""

        return await self.send_message(message)

    async def notify_error(self, error: str, context: str = "") -> bool:
        """
        Send notification about an error.
        """
        message = f"""⚠️ *Error Alert*

*Context:* {context or 'General'}

*Error:*
```
{error}
```"""

        return await self.send_message(message)

    async def notify_daily_summary(
        self,
        signals_generated: int,
        trades_executed: int,
        pnl: float,
        positions: int,
    ) -> bool:
        """
        Send daily summary notification.
        """
        pnl_emoji = "📈" if pnl >= 0 else "📉"

        message = f"""📊 *Daily Summary*

*Signals Generated:* {signals_generated}
*Trades Executed:* {trades_executed}
*Open Positions:* {positions}

{pnl_emoji} *P&L:* ${pnl:+.2f}"""

        return await self.send_message(message)


class NotificationManager:
    """
    Manages all notification channels.
    """

    def __init__(
        self,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        telegram_enabled: bool = False,
    ):
        self.telegram: Optional[TelegramNotifier] = None

        if telegram_enabled and telegram_token and telegram_chat_id:
            self.telegram = TelegramNotifier(
                bot_token=telegram_token,
                chat_id=telegram_chat_id,
                enabled=True,
            )
            logger.info("Telegram notifications enabled")

    async def close(self):
        """Close all notification channels"""
        if self.telegram:
            await self.telegram.close()

    async def notify_signal(self, signal: TradingSignal):
        """Notify all channels about a new signal"""
        if self.telegram:
            await self.telegram.notify_signal(signal)

    async def notify_execution(self, result: ExecutionResult):
        """Notify all channels about trade execution"""
        if self.telegram:
            await self.telegram.notify_execution(result)

    async def notify_error(self, error: str, context: str = ""):
        """Notify all channels about an error"""
        if self.telegram:
            await self.telegram.notify_error(error, context)

    async def notify_daily_summary(
        self,
        signals_generated: int,
        trades_executed: int,
        pnl: float,
        positions: int,
    ):
        """Send daily summary to all channels"""
        if self.telegram:
            await self.telegram.notify_daily_summary(
                signals_generated, trades_executed, pnl, positions
            )
