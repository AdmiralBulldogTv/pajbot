from typing import Optional, Tuple

import logging

from pajbot.bot import Bot
from pajbot.models.command import Command
from pajbot.modules import BaseModule, ModuleSetting

import schedule

log = logging.getLogger(__name__)


class AutoAdsModule(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "AutoAds"
    DESCRIPTION = "Automatically Run Ads"
    CATEGORY = "Feature"
    SETTINGS = [
        ModuleSetting(
            key="command_name",
            label="Command name (i.e. $ads)",
            type="text",
            required=True,
            placeholder="Command name (no !)",
            default="ads",
            constraints={"min_str_len": 2, "max_str_len": 15},
        ),
        ModuleSetting(
            key="command_level",
            label="Level required to issue the command",
            type="number",
            required=True,
            placeholder="",
            default=500,
            constraints={"min_value": 101, "max_value": 2000},
        ),
        ModuleSetting(
            key="ads_length",
            label="The length of the ads",
            type="options",
            required=True,
            default="60",
            options=["30", "60", "90", "120", "150", "180"],
        ),
    ]

    def run_ads(self, bot: Bot) -> Tuple[str, bool]:
        if not self.is_enabled():
            return "module is disabled", False

        if not bot.is_online:
            return "stream is offline", False

        message, success = bot.twitch_helix_api.start_commercial(
            bot.streamer.id, self.settings["ads_length"], bot.streamer_access_token_manager
        )

        if message:
            log.info(f"twitch responded with `{message}` for ads")

        return message, success

    def warn_chat(self, bot: Bot):
        if not self.is_enabled():
            return "module is disabled", False

        if not bot.is_online:
            return "stream is offline", False

        bot.say(
            "Hey we're about to run 3 minutes of ads at the top of the hour so that your experience as a viewer isn't interrupted when they would be run on you either way, if you'd like to avoid them please subscribe and support Lacari https://subs.twitch.tv/Lacari"
        )

    def run_ads_command(self, bot, source, message, *args, **kwargs):
        message, success = self.run_ads(bot)
        if message:
            bot.whisper(
                source, f"Ads run was {'successful' if success else 'unsuccessful'}. Twitch responded with `{message}`."
            )
        elif success:
            bot.whisper(
                source,
                f"Ads run was {'successful' if success else 'unsuccessful'}. Twitch didnt send back a bad response so we assume the ads ran.",
            )
        else:
            bot.whisper(
                source, f"Ads run was {'successful' if success else 'unsuccessful'}. Twitch didn't provide a response."
            )

    def load_commands(self, **options):
        self.commands[self.settings["command_name"].lower().replace("!", "").replace(" ", "")] = Command.raw_command(
            self.run_ads_command,
            level=self.settings["command_level"],
        )

    def on_loaded(self):
        if self.bot:
            if hasattr(self, "ads_job"):
                schedule.cancel_job(self.ads_job)
            if hasattr(self, "warning_job"):
                schedule.cancel_job(self.warning_job)

            self.ads_job = schedule.every().hour.do(self.run_ads, self.bot)
            self.warning_job = schedule.every().hour.at(":58").do(self.warn_chat, self.bot)

    def disable(self, bot: Optional[Bot]) -> None:
        if bot:
            if hasattr(self, "ads_job"):
                schedule.cancel_job(self.ads_job)
            if hasattr(self, "warning_job"):
                schedule.cancel_job(self.warning_job)
