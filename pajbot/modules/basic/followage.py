from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

import logging

from pajbot import utils
from pajbot.managers.db import DBManager
from pajbot.models.command import Command, CommandExample
from pajbot.models.user import User
from pajbot.modules import BaseModule, ModuleSetting
from pajbot.modules.basic import BasicCommandsModule
from pajbot.utils import time_since

from requests import HTTPError

if TYPE_CHECKING:
    from datetime import datetime

    from pajbot.bot import Bot

log = logging.getLogger(__name__)


class FollowAgeModule(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "Followage"
    DESCRIPTION = "Enables the usage of the !followage and !followsince commands"
    CATEGORY = "Feature"
    PARENT_MODULE = BasicCommandsModule
    SETTINGS = [
        ModuleSetting(
            key="action_followage",
            label="MessageAction for !followage",
            type="options",
            required=True,
            default="say",
            options=["say", "whisper", "reply"],
        ),
        ModuleSetting(
            key="action_followsince",
            label="MessageAction for !followsince",
            type="options",
            required=True,
            default="say",
            options=["say", "whisper", "reply"],
        ),
        ModuleSetting(
            key="global_cd",
            label="Global cooldown (seconds)",
            type="number",
            required=True,
            placeholder="",
            default=4,
            constraints={"min_value": 0, "max_value": 120},
        ),
        ModuleSetting(
            key="user_cd",
            label="Per-user cooldown (seconds)",
            type="number",
            required=True,
            placeholder="",
            default=8,
            constraints={"min_value": 0, "max_value": 240},
        ),
    ]

    def load_commands(self, **options: Any) -> None:
        self.commands["followage"] = Command.raw_command(
            self.follow_age,
            delay_all=self.settings["global_cd"],
            delay_user=self.settings["user_cd"],
            description="Check your or someone elses followage for a channel",
            can_execute_with_whisper=True,
            examples=[
                CommandExample(
                    None,
                    "Check your own followage",
                    chat="user:!followage\nbot:pajlada, you have been following Karl_Kons for 4 months and 24 days",
                    description="Check how long you have been following the current streamer (Karl_Kons in this case)",
                ).parse(),
                CommandExample(
                    None,
                    "Check someone elses followage",
                    chat="user:!followage NightNacht\n"
                    "bot:pajlada, NightNacht has been following Karl_Kons for 5 months and 4 days",
                    description="Check how long any user has been following the current streamer (Karl_Kons in this case)",
                ).parse(),
                CommandExample(
                    None,
                    "Check someones followage for a certain streamer",
                    chat="user:!followage NightNacht forsen\n"
                    "bot:pajlada, NightNacht has been following forsen for 1 year and 4 months",
                    description="Check how long NightNacht has been following forsen",
                ).parse(),
                CommandExample(
                    None,
                    "Check your own followage for a certain streamer",
                    chat="user:!followage pajlada forsen\n"
                    "bot:pajlada, you have been following forsen for 1 year and 3 months",
                    description="Check how long you have been following forsen",
                ).parse(),
            ],
        )

        self.commands["followsince"] = Command.raw_command(
            self.follow_since,
            delay_all=self.settings["global_cd"],
            delay_user=self.settings["user_cd"],
            description="Check from when you or someone else first followed a channel",
            can_execute_with_whisper=True,
            examples=[
                CommandExample(
                    None,
                    "Check your own follow since",
                    chat="user:!followsince\n"
                    "bot:pajlada, you have been following Karl_Kons since 04 March 2015, 07:02:01 UTC",
                    description="Check when you first followed the current streamer (Karl_Kons in this case)",
                ).parse(),
                CommandExample(
                    None,
                    "Check someone elses follow since",
                    chat="user:!followsince NightNacht\n"
                    "bot:pajlada, NightNacht has been following Karl_Kons since 03 July 2014, 04:12:42 UTC",
                    description="Check when NightNacht first followed the current streamer (Karl_Kons in this case)",
                ).parse(),
                CommandExample(
                    None,
                    "Check someone elses follow since for another streamer",
                    chat="user:!followsince NightNacht forsen\n"
                    "bot:pajlada, NightNacht has been following forsen since 13 June 2013, 13:10:51 UTC",
                    description="Check when NightNacht first followed the given streamer (forsen)",
                ).parse(),
                CommandExample(
                    None,
                    "Check your follow since for another streamer",
                    chat="user:!followsince pajlada forsen\n"
                    "bot:pajlada, you have been following forsen since 16 December 1990, 03:06:51 UTC",
                    description="Check when you first followed the given streamer (forsen)",
                ).parse(),
            ],
        )

    @staticmethod
    def _format_for_follow_age(follow_since: datetime) -> str:
        human_age = time_since(utils.now().timestamp() - follow_since.timestamp(), 0)
        return f"for {human_age}"

    @staticmethod
    def _format_for_follow_since(follow_since: datetime) -> str:
        human_age = follow_since.strftime("%d %B %Y, %X %Z")
        return f"since {human_age}"

    @staticmethod
    def _parse_message(message: str) -> tuple[Optional[str], Optional[str]]:
        from_input = None
        to_input = None
        if message is not None and len(message) > 0:
            message_split = message.split(" ")
            if len(message_split) >= 1:
                from_input = message_split[0]
            if len(message_split) >= 2:
                to_input = message_split[1]

        return from_input, to_input

    def _handle_command(
        self,
        bot: Bot,
        source: User,
        message: str,
        event: Any,
        format_cb: Callable[[datetime], str],
        message_method: str,
    ) -> None:
        # user is the user we check the followage for
        # broadcaster is the broadcaster we check the followage against
        user_input, broadcaster_input = self._parse_message(message)

        with DBManager.create_session_scope(expire_on_commit=False) as db_session:
            if user_input is not None:
                user = User.find_or_create_from_user_input(db_session, bot.twitch_helix_api, user_input)

                if user is None:
                    bot.execute_now(
                        bot.send_message_to_user,
                        source,
                        f'User "{user_input}" could not be found',
                        event,
                        method=self.settings["action_followage"],
                    )
                    return
            else:
                user = source

            if broadcaster_input is None:
                broadcaster_input = bot.streamer.login

            broadcaster = User.find_or_create_from_user_input(db_session, bot.twitch_helix_api, broadcaster_input)
            if broadcaster is None:
                bot.execute_now(
                    bot.send_message_to_user,
                    source,
                    f'User "{broadcaster_input}" could not be found',
                    event,
                    method=message_method,
                )
                return

        try:
            follow_since = bot.twitch_helix_api.get_follow_since(broadcaster.id, user.id, bot.bot_token_manager)
        except HTTPError as e:
            if e.response is None:
                raise e

            if e.response.status_code == 401:
                log.info(f"Failed to fetch follow since, error 401: {e.response.text}")
                bot.execute_now(
                    bot.send_message_to_user,
                    source,
                    f"Bot does not have permission to check follow age for streamer {broadcaster_input}",
                    event,
                    method=message_method,
                )
                return
            raise e
        is_self = source == user

        if follow_since is not None:
            # Following
            suffix = f"been following {broadcaster} {format_cb(follow_since)}"
            if is_self:
                message = f"You have {suffix}"
            else:
                message = f"{user.name} has {suffix}"
        else:
            # Not following
            suffix = f"not following {broadcaster}"
            if is_self:
                message = f"You are {suffix}"
            else:
                message = f"{user.name} is {suffix}"

        bot.execute_now(bot.send_message_to_user, source, message, event, method=message_method)

    def follow_age(self, bot: Bot, source: User, message: str, event: Any, **rest: Any) -> None:
        bot.action_queue.submit(
            self._handle_command,
            bot,
            source,
            message,
            event,
            self._format_for_follow_age,
            self.settings["action_followage"],
        )

    def follow_since(self, bot: Bot, source: User, message: str, event: Any, **rest: Any) -> None:
        bot.action_queue.submit(
            self._handle_command,
            bot,
            source,
            message,
            event,
            self._format_for_follow_since,
            self.settings["action_followsince"],
        )
