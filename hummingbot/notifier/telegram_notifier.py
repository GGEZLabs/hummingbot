#!/usr/bin/env python

import asyncio
import logging
import sys
from os.path import join, realpath
from typing import Any, List, Optional

import pandas as pd
from telegram import Bot, ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import NetworkError, TelegramError, TimedOut

import hummingbot
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.notifier.notifier_base import NotifierBase

sys.path.insert(0, realpath(join(__file__, "../../../")))

DISABLED_COMMANDS = {
    "connect",  # disabled because telegram can't display secondary prompt
    "create",   # disabled because telegram can't display secondary prompt
    "import",   # disabled because telegram can't display secondary prompt
    "export",   # disabled for security
}

# Telegram does not allow sending messages longer than 4096 characters
TELEGRAM_MSG_LENGTH_LIMIT = 3000


class TelegramNotifier(NotifierBase):
    tn_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.tn_logger is None:
            cls.tn_logger = logging.getLogger(__name__)
        return cls.tn_logger

    def __init__(
        self, token: str, chat_id: str, hb: "hummingbot.client.hummingbot_application.HummingbotApplication"
    ) -> None:
        super().__init__()
        self._token = token
        self._chat_id = chat_id
        self._hb = hb
        self._ev_loop = asyncio.get_event_loop()
        self._msg_queue: asyncio.Queue = asyncio.Queue()
        self._send_msg_task: Optional[asyncio.Task] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._bot: Optional[Bot] = None
        self._last_update_id: int = 0

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self._token == other._token
            and self._chat_id == other._chat_id
            and id(self._hb) == id(other._hb)
        )

    def start(self):
        if not self._started:
            self._started = True
            self._bot = Bot(token=self._token)

            # Start manual polling and message sending tasks
            self._polling_task = safe_ensure_future(self._poll_updates(), loop=self._ev_loop)
            self._send_msg_task = safe_ensure_future(self._send_msg_from_queue(), loop=self._ev_loop)
            self.logger().info("Telegram is listening...")

    async def _poll_updates(self):
        """Manually poll for updates from Telegram."""
        self.logger().info("Starting Telegram polling loop...")

        # Clear any pending updates on startup
        try:
            updates = await self._bot.get_updates(timeout=1)
            if updates:
                self._last_update_id = updates[-1].update_id + 1
                self.logger().info(f"Cleared {len(updates)} pending updates")
        except Exception as e:
            self.logger().warning(f"Error clearing pending updates: {e}")

        while self._started:
            try:
                updates = await self._bot.get_updates(
                    offset=self._last_update_id,
                    timeout=30,
                    allowed_updates=["message"]
                )

                for update in updates:
                    self._last_update_id = update.update_id + 1

                    if update.message and update.message.text:
                        # Check authorization
                        if str(update.message.chat_id) == str(self._chat_id):
                            await self._handle_message(update)
                        else:
                            self.logger().info(
                                f"Rejected unauthorized message from chat_id: {update.message.chat_id}"
                            )

            except TimedOut:
                # This is normal for long polling
                pass
            except NetworkError as e:
                self.logger().warning(f"Telegram network error: {e}, retrying in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                self.logger().error(f"Error polling Telegram updates: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _handle_message(self, update: Update) -> None:
        """Handle an incoming message."""
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        try:
            input_text = update.message.text.strip()
            output = f"\n[Telegram Input] {input_text}"

            self.logger().info(f"Received Telegram message: {input_text}")

            if not self._hb.headless_mode:
                self._hb.app.log(output)

            # Check if command is disabled
            if any(input_text.lower().startswith(dc) for dc in DISABLED_COMMANDS):
                self.add_message_to_queue(f"Command {input_text} is disabled from telegram")
            else:
                # Set display options to max, so that telegram does not display truncated data
                pd.set_option("display.max_rows", 500)
                pd.set_option("display.max_columns", 500)
                pd.set_option("display.width", 1000)

                # Execute the command
                await async_scheduler.call_async(self._hb._handle_command, input_text)

                # Reset to normal
                pd.set_option("display.max_rows", 0)
                pd.set_option("display.max_columns", 0)
                pd.set_option("display.width", 0)

        except Exception as e:
            self.logger().error(f"Error handling Telegram message: {e}", exc_info=True)
            self.add_message_to_queue(f"Error: {str(e)}")

    def stop(self) -> None:
        if self._started:
            self._started = False
            self.logger().info("Stopping Telegram notifier...")
        if self._polling_task:
            self._polling_task.cancel()
        if self._send_msg_task:
            self._send_msg_task.cancel()

    @staticmethod
    def _divide_chunks(arr: List[Any], n: int = 5):
        """Break a list into chunks of size N"""
        for i in range(0, len(arr), n):
            yield arr[i: i + n]

    def add_message_to_queue(self, msg: str):
        lines: List[str] = msg.split("\n")
        msg_chunks: List[List[str]] = list(self._divide_chunks(lines, 30))
        for chunk in msg_chunks:
            self._msg_queue.put_nowait("\n".join(chunk))

    async def _send_msg_from_queue(self):
        """Send messages from the queue."""
        while self._started:
            try:
                new_msg: str = await asyncio.wait_for(self._msg_queue.get(), timeout=1.0)
                if isinstance(new_msg, str) and len(new_msg) > 0:
                    await self._send_msg_async(new_msg)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                self.logger().error(f"Error sending message: {e}")
            await asyncio.sleep(0.1)

    async def _send_msg_async(self, msg: str) -> None:
        """Send a message to Telegram."""
        if self._bot is None:
            self.logger().warning("Bot not initialized, cannot send message")
            return

        # Command options that show up on user's screen
        approved_commands = ["start", "stop", "status", "history", "config"]
        keyboard = list(self._divide_chunks(approved_commands))
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        formatted_msg = f"\n{msg}\n"

        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=formatted_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except NetworkError as network_err:
            self.logger().warning(
                f"Telegram NetworkError: {network_err}! Trying without parse_mode..."
            )
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=msg,
                    reply_markup=reply_markup
                )
            except Exception as e:
                self.logger().error(f"Failed to send message: {e}")
        except TelegramError as telegram_err:
            self.logger().error(f"TelegramError: {telegram_err}! Giving up on that message.")
