import os
import logging

from app.HahOrNahBot import HahOrNahBot

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler()]
                        )
    try:
        token = os.environ['TELEGRAM_TOKEN']
    except KeyError:
        print('Missing token. You did not provide the TELEGRAM_TOKEN environment variable.')
        exit()

    try:
        database_url = os.environ['DATABASE_URL']
    except KeyError:
        print('Missing database url. You did not provide the DATABASE_URL environment variable.')
        exit()

    port = int(os.environ.get('PORT', 8443))

    bot = HahOrNahBot(token, database_url)
    bot.start_webhook("https://hah-or-nah-bot.herokuapp.com/", port)
