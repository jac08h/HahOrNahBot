from telegram.ext import Updater, CommandHandler
import os
from sys import exit


class HahOrNahBot:
    def __init__(self, token):
        self.token = token
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)

        return

    def start(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text='Hey.')
        return

    def start_webhook(self, url, port):
        self.updater.start_webhook(listen="0.0.0.0",
                                   port=port,
                                   url_path=self.token)
        self.updater.bot.set_webhook(url + self.token)
        self.updater.idle()
        return


if __name__=='__main__':
    try:
        token=os.environ['HAH_OR_NAH_TOKEN']
    except KeyError:
        print('Missing token. You did not provide the HAH_OR_NAH_TOKEN environment variable.')
        exit()

    port = int(os.environ.get('PORT', 8443))

    bot = HahOrNahBot(token)
    bot.start_webhook("hah-or-nah-bot.herokuapp.com/", port)