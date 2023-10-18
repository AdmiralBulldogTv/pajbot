from __future__ import annotations

from typing import TYPE_CHECKING

import logging
from datetime import datetime, timedelta, timezone

from pajbot import utils
from pajbot.exc import InvalidPointAmount
from pajbot.managers.db import DBManager
from pajbot.models.command import Command, CommandExample
from pajbot.models.user import User
from pajbot.modules import BaseModule, ModuleSetting

if TYPE_CHECKING:
    from pajbot.bot import Bot

log = logging.getLogger(__name__)


class MassPointsModule(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "Mass Points"
    DESCRIPTION = "Allows staff to give points to everyone"
    CATEGORY = "Feature"
    SETTINGS = [
        ModuleSetting(
            key="command_name",
            label="Command name (i.e. masspoints)",
            type="text",
            required=True,
            placeholder="Command name (no !)",
            default="masspoints",
            constraints={"min_str_len": 2, "max_str_len": 25},
        ),
        ModuleSetting(
            key="last_active_minutes",
            label="Minutes since last active",
            type="number",
            required=True,
            placeholder="Minutes since last active",
            default=10,
            constraints={"min_value": 0, "max_value": 1440},
        ),
    ]

    def mass_points(self, bot: Bot, source: User, message: str, **rest) -> bool:
        if message is None or len(message) == 0:
            # The user did not supply any arguments
            return False

        msg_split = message.split(" ")
        if len(msg_split) < 1:
            # The user did not supply enough arguments
            bot.whisper(source, f"Usage: !{self.command_name} POINTS")
            return False

        try:
            num_points = utils.parse_points_amount(source, msg_split[0])
        except InvalidPointAmount as e:
            bot.whisper(source, f"{e}. Usage: !{self.command_name} POINTS")
            return False

        with DBManager.create_session_scope() as db_session:
            # We want to know how many users we are giving points to

            threshold = datetime.now(timezone.utc) - timedelta(minutes=self.settings["last_active_minutes"])

            num_users = (
                db_session.query(User)
                .filter(User.last_active >= threshold)
                .update({User.points: User.points + num_points})
            )

            bot.say(f"Successfully gave away {num_points} points to {num_users} users FeelsGoodMan")

        return True

    def load_commands(self, **options) -> None:
        self.command_name = self.settings["command_name"].lower().replace("!", "").replace(" ", "")
        self.commands[self.command_name] = Command.raw_command(
            self.mass_points,
            level=1000,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            examples=[
                CommandExample(
                    None,
                    "Give points to everyone.",
                    chat=f"user:!{self.command_name} 4444\n"
                    "bot: Successfully gave away 4444 points to 2 users FeelsGoodMan",
                    description="",
                ).parse()
            ],
        )
