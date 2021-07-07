import getpass
import os
from typing import Tuple

import helpers.dbg as dbg

NOTIFY_JUPYTER_TOKEN = os.environ["AM_TELEGRAM_TOKEN"]


def get_info() -> Tuple[str, str]:
    user = getpass.getuser()
    # telegram_token is the token of your bot
    # - You can use @NotifyJupyterBot, its token is
    #   '***REMOVED***'
    # chat_id: To get it, start messaging with the bot. Then go to
    # https://api.telegram.org/bot<telegram_token>/getUpdates and get your chat id.
    # (If you are using @NotifyJupyterBot, go to
    # https://api.telegram.org/bot***REMOVED***/getUpdates )
    if user in ("saggese", "root"):
        telegram_token = NOTIFY_JUPYTER_TOKEN
        chat_id = "967103049"
    else:
        dbg.dfatal("User `%s` is not in the config.py" % user)
    return telegram_token, chat_id
