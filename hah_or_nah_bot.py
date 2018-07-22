from telegram.ext import Updater, CommandHandler
import os
from sys import exit
import psycopg2
from random import choice


class HahOrNahBot:
    def __init__(self, token, database_url):
        self.token = token
        self.database_url = database_url

        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)
        joke_handler = CommandHandler('joke', self.joke)
        self.dispatcher.add_handler(joke_handler)

        self.db_connection = psycopg2.connect(self.database_url, ssl_mode='require')
        self.cursor = self.db_connection.cursor()

        return

    def start(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text='Hey.')
        return

    def joke(self, bot, update):
        command = "SELECT * FROM joke"
        self.cursor.execute(command)

        random_joke = choice(self.cursor.fetchall())
        random_joke_string = random_joke[1]

        bot.send_message(chat_id=update.message.chat_id, text = random_joke_string)

    def start_webhook(self, url, port):
        self.updater.start_webhook(listen="0.0.0.0",
                                   port=port,
                                   url_path=self.token)
        self.updater.bot.set_webhook(url + self.token)
        self.updater.idle()
        return


if __name__=='__main__':
    try:
        token = os.environ['HAH_OR_NAH_TOKEN']
    except KeyError:
        print('Missing token. You did not provide the HAH_OR_NAH_TOKEN environment variable.')
        exit()

    try:
        database_url = os.environ['DATABASE_URL']
    except KeyError:
        print('Missing database url. You did not provide the DATABASE_URL environment variable.')
        exit()

    port = int(os.environ.get('PORT', 8443))

    bot = HahOrNahBot(token, database_url)
    bot.start_webhook("https://hah-or-nah-bot.herokuapp.com/", port)