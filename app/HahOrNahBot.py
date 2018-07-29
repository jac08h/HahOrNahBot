from telegram.ext import Updater, CommandHandler
import telegram
from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy.orm.exc as sql_errors

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
        add_handler = CommandHandler('add', self.add, pass_args=True)
        self.dispatcher.add_handler(add_handler)
        show_handler = CommandHandler('show', self.show, pass_args=True)
        self.dispatcher.add_handler(show_handler)
        vote_handler = CommandHandler(['hah', 'nah'], self.vote, pass_chat_data=True)
        self.dispatcher.add_handler(vote_handler)

        engine = create_engine(database_url, echo=True)
        Session = sessionmaker(bind=engine)
        self.session = Session()

        self.MIN_JOKE_LENGTH = 10

        self.help_text = """
        *Commands*
        /joke - return random joke
        /add JOKE TEXT - add joke
        /show JOKE ID - show joke informatin by id
        /help - show this message
        """

        return

    def start(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text='Hey.')
        return

    def help(self, bot, update):
        update.message.reply_markdown(self.help_text)

    def joke(self, bot, update, chat_data):
        """
        Return random joke
        """
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
        """
        Register user's vote for joke. Can't be called directly, only after `/joke` command.
        """
        try:
            joke = chat_data['last_joke_displayed']
        except KeyError:
            update.message.reply_markdown('No joke to vote for. Use `/joke` command to get random joke.')
            return

        telegram_id = update.message.chat_id
        telegram_username = update.message.from_user.username
        user = self.__get_user(telegram_id, telegram_username)

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
            return
        finally:
            del chat_data['last_joke_displayed']
            # Clear vote buttons
            remove_vote_options_markup = telegram.ReplyKeyboardRemove()
            bot.send_message(chat_id=update.message.chat_id,
                             text='Vote submitted.',
                             reply_markup=remove_vote_options_markup)
            return

    def add(self, bot, update, args):
        """
        Add joke to database.
        """
        telegram_id = update.message.chat_id
        telegram_username = update.message.from_user.username
        user = self.__get_user(telegram_id, telegram_username)

        new_joke_body = ' '.join(args)

        if len(new_joke_body) < self.MIN_JOKE_LENGTH:
            update.message.reply_text('Invalid joke text. Please use at least 10 characters.')
            return

        all_jokes = self.session.query(Joke).order_by(Joke.id).all()
        last_joke = all_jokes[-1]
        last_joke_id = last_joke.get_id()

        new_joke_id = last_joke_id + 1
        new_joke = Joke(id=new_joke_id, body=new_joke_body, vote_count=0, author=user)

        update.message.reply_text("Thanks for submitting your joke. Your joke's ID is {}.".format(new_joke_id))
        self.session.add(new_joke)
        self.session.commit()
        return

    def show(self, bot, update, args):
        """
        Show information about joke by id.
        """
        try:
            joke_id = args[0]
        except IndexError:
            update.message.reply_text('Please provide joke ID.')
            return

        try:
            joke_id = int(joke_id)
        except ValueError:
            update.message.reply_text('Invalid joke ID format ({})'.format(joke_id))
            return

        try:
            joke = self.session.query(Joke).filter(Joke.id == joke_id).one()
        except sql_errors.NoResultFound:
            update.message.reply_text('No joke with this ID ({})'.format(joke_id))
            return

        joke_info = str(joke)
        update.message.reply_text(joke_info)
        return

    def __get_user(self, id, username):
        """
        Get user by id if the user is in database, create new database record otherwise.

        Returns:
            instance of User class
        """

        # Check if user is in database
        user = self.session.query(User).filter(User.id==id).first()
        if user is None:
            # If not, create one
            telegram_username = username
            user = User(id=id, username=telegram_username)
            self.session.add(user)
            self.session.commit()

        return user

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