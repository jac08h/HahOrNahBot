from telegram.ext import Updater, CommandHandler
import telegram

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import logging
from random import choice

from app.models import Joke, User, InvalidVoteException

logger = logging.getLogger(__name__)


class HahOrNahBot:
    def __init__(self, token, database_url):
        self.token = token
        self.database_url = database_url

        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)
        help_handler = CommandHandler('help', self.help)
        self.dispatcher.add_handler(help_handler)
        joke_handler = CommandHandler('joke', self.joke, pass_chat_data=True)
        self.dispatcher.add_handler(joke_handler)
        vote_handler = CommandHandler(['hah', 'nah'], self.vote, pass_chat_data=True)
        self.dispatcher.add_handler(vote_handler)

        engine = create_engine(database_url, echo=True)
        Session = sessionmaker(bind=engine)
        self.session = Session()

        self.help_text = """
        *Commands*
        /joke - return random joke
        """

        return

    def start(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text='Hey.')
        return

    def help(self, bot, update):
        update.message.reply_markdown(self.help_text)

    def joke(self, bot, update, chat_data):
        all_jokes = self.session.query(Joke).all()
        random_joke = choice(all_jokes)

        vote_options = [['/hah', '/nah']]
        show_vote_options_markup = telegram.ReplyKeyboardMarkup(vote_options)
        bot.send_message(chat_id=update.message.chat_id,
                         text=random_joke.get_body(),
                         reply_markup=show_vote_options_markup)

        chat_data['last_joke_displayed'] = random_joke
        return

    def vote(self, bot, update, chat_data):
        try:
            joke = chat_data['last_joke_displayed']
        except KeyError:
            update.message.reply_markdown('No joke to vote for. Use `/joke` command to get random joke.')
            return

        # Check if user is in database
        telegram_id = update.message.chat_id
        user = self.session.query(User).filter(User.id==telegram_id).first()
        if user is None:
            # If not, create one
            telegram_username = update.message.from_user.username
            user = User(id=telegram_id, username=telegram_username)
            self.session.add(user)

        try:
            # Register vote
            if 'hah' in update.message.text:
                user.vote_for_joke(joke, positive=True)
            else:
                user.vote_for_joke(joke, positive=False)
            self.session.add(user, joke)
            self.session.commit()
        except InvalidVoteException:
            update.message.reply_text('You already voted for this joke.')
        finally:
            del chat_data['last_joke_displayed']
            # Clear vote buttons
            remove_vote_options_markup = telegram.ReplyKeyboardRemove()
            bot.send_message(chat_id=update.message.chat_id,
                             text='Vote submitted.',
                             reply_markup=remove_vote_options_markup)
            return

    def start_webhook(self, url, port):
        self.updater.start_webhook(listen="0.0.0.0",
                                   port=port,
                                   url_path=self.token)
        self.updater.bot.set_webhook(url + self.token)
        self.updater.idle()
        return

    def start_local(self):
        self.updater.start_polling()
        self.updater.idle()