from telegram.ext import Updater, CommandHandler, ConversationHandler, CallbackQueryHandler, RegexHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy.orm.exc as sql_errors

import logging
from random import randint, choice
import json
from sys import exit
from string import ascii_letters, digits

from app.models import Joke, User, InvalidVoteException

logger = logging.getLogger(__name__)


class HahOrNahBot:
    def __init__(self, token, database_url):
        self.JOKE_LENGTH_MIN = 10
        self.JOKE_LENGTH_MAX = 1000
        self.USERNAME_LENGTH_MIN = 5
        self.USERNAME_LENGTH_MAX = 20
        self.USERNAME_ALLOWED_CHARACTERS = set(ascii_letters + digits + '-_')

        self.MESSAGES_FILE = 'messages.json'

        self.token = token
        self.database_url = database_url
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        start_handler = CommandHandler('start', self.command_menu)
        register_user_handler = CommandHandler('register', self.register_user)
        add_handler = RegexHandler('\+.+', self.add_joke, pass_chat_data=True)  # any text starting with + sign
        menu_handler = RegexHandler('.+', self.command_menu)
        callback_handler = CallbackQueryHandler(self.callback_eval, pass_chat_data=True)

        handlers = [start_handler,
                    register_user_handler,
                    add_handler,
                    menu_handler,
                    callback_handler]
        for handler in handlers:
            self.dispatcher.add_handler(handler)

        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        self.session = Session()

        self.messages = self.private_get_messages(self.MESSAGES_FILE)

    def private_get_messages(self, messages_file):
        """
        Get bot messages defined in config_file

        Returns:
            dict
        """

        try:
            with open(messages_file, 'r') as fp:
                messages = json.load(fp)
            return messages

        except FileNotFoundError:
            logger.info('Messages file {} not found. Exiting'.format(messages_file))
            exit()

    def private_get_random_message(self, state):
        """
        Return random message from to be replied

        Returns:
            string
        """
        try:
            assert state in self.messages.keys()  # should be called only with states defined in self.MESSAGES_FILE
        except AssertionError:
            logger.info(state)
            exit()

        message = choice(self.messages[state])
        return message

    def private_get_user(self, message):
        """
        Get user by id if the user is in database, create new database record otherwise.

        Returns:
            instance of User class if user exists, None otherwise

        """
        user_id = message.chat.id
        # Check if user is in database

        user = self.session.query(User).filter(User.id == user_id).first()
        if not user:
            reply_message = self.private_get_random_message('user_not_registered\n')
            reply_message += 'Use `/register YOUR_NAME` to introduce yourself!'
            message.reply_text(reply_message)
            return None

        return user

    def callback_eval(self, bot, update, chat_data):
        query_data = update.callback_query.data
        message = update.callback_query.message

        current_user = self.private_get_user(message)
        chat_data['current_user'] = current_user

        message = update.callback_query.message

        if 'joke_show' in query_data:
            self.show_random_joke(message, bot, chat_data)

        elif 'vote' in query_data:
            try:
                joke = chat_data['last_joke']
            except KeyError:
                message.reply_text(self.private_get_random_message('joke_no_current'))
                return

            del chat_data['last_joke']

            if 'positive' in query_data:
                self.vote_for_joke(message, chat_data, joke, positive_vote=True)
            else:
                self.vote_for_joke(message, chat_data, joke, positive_vote=False)

        elif 'joke_add' in query_data:
            message.reply_text(self.private_get_random_message('joke_add'))

        elif 'profile' in query_data:
            self.profile_command(message, chat_data)

        elif 'top10' in query_data:
            self.top10_command(message)

        return

    def command_menu(self, bot, update):
        menu_options = [
            [InlineKeyboardButton(text='Show random joke', callback_data='joke_show')],
            [InlineKeyboardButton(text='Add joke', callback_data='joke_add')],
            [InlineKeyboardButton(text='Profile', callback_data='profile')],
            [InlineKeyboardButton(text='Top 10', callback_data='top10')],
        ]

        vote_options_keyboard = InlineKeyboardMarkup(menu_options, one_time_keyboard=True)

        bot.send_message(chat_id=update.message.chat_id,
                         text=self.private_get_random_message('menu'),
                         reply_markup=vote_options_keyboard)
        return

    def register_user(self, bot, update):
        message = update.message
        user_id = message.chat_id

        user = self.session.query(User).filter(User.id==user_id).first()
        if user is not None:
            message.reply_text(self.private_get_random_message('user_registered_already'))
            return

        username = message.text.replace('/register ', '').strip()
        if len(username) < self.USERNAME_LENGTH_MIN:
            message.reply_text(self.private_get_random_message('username_too_short'))
            return

        if len(username) > self.USERNAME_LENGTH_MAX:
            message.reply_text(self.private_get_random_message('username_too_long'))
            return

        only_allowed_chars = set(username) <= self.USERNAME_ALLOWED_CHARACTERS
        if not only_allowed_chars:
            message.reply_text(self.private_get_random_message('username_forbidden_characters'))
            return



        user = User(id=user_id, username=username, score=0)
        message.reply_text(self.private_get_random_message('user_registered_success'))

        self.session.add(user)
        self.session.commit()
        return

    def show_random_joke(self, message, bot, chat_data):
        """
        Return random joke
        """
        user = self.private_get_user(message)
        chat_id = message.chat.id

        all_jokes = self.session.query(Joke).all()

        try:
            random_joke_index = randint(0, len(all_jokes)-1)
        except ValueError:
            message.reply_text(self.private_get_random_message('empty_database'))
            return

        random_joke = all_jokes.pop(random_joke_index)
        voted_already = random_joke in user.jokes_voted_for
        user_is_author = random_joke in user.jokes_submitted

        while False:
            try:
                random_joke_index = randint(0, len(all_jokes)-1)
            except ValueError:
                message.reply_text(self.private_get_random_message('no_new_jokes'))
                return

            random_joke = all_jokes.pop(random_joke_index)

        vote_options = [
            [InlineKeyboardButton(text='Hah!', callback_data='positive_vote')],
            [InlineKeyboardButton(text='Nah.', callback_data='negative_vote')]
        ]
        vote_options_keyboard = InlineKeyboardMarkup(vote_options)

        chat_data['last_joke'] = random_joke

        message.reply_text(random_joke.get_body())

        bot.send_message(chat_id=chat_id,
                         text=self.private_get_random_message('hah_or_nah'),
                         reply_markup=vote_options_keyboard)
        return

    def vote_for_joke(self, message, chat_data, joke, positive_vote):
        """
        Register user's vote for joke.
        Remove

        Arguments:
            positive_vote: bool, True for positive vote
        """
        user = chat_data['current_user']

        try:
            if positive_vote:
                user.vote_for_joke(joke, positive=True)
                message.edit_text(self.private_get_random_message('positive_vote'))
            else:
                user.vote_for_joke(joke, positive=False)
                message.edit_text(self.private_get_random_message('negative_vote'))

            self.session.add(user, joke)
            self.session.commit()

        except InvalidVoteException as e:
            logger.error(e)

        return

    def add_joke(self, bot, update, chat_data):
        """
        Add joke to database.
        """
        message = update.message
        try:
            user = chat_data['current_user']
        except KeyError:
            user = self.private_get_user(message)

        text = message.text
        joke_body = text.replace('+', '').strip()

        if len(joke_body) < self.JOKE_LENGTH_MIN:
            message.reply_text(self.private_get_random_message('joke_too_short'))
            return

        if len(joke_body) > self.JOKE_LENGTH_MAX:
            message.reply_text(self.private_get_random_message('joke_too_long'))
            return

        all_jokes = self.session.query(Joke).order_by(Joke.id).all()
        try:
            last_joke = all_jokes[-1]
            last_joke_id = last_joke.get_id()
            new_joke_id = last_joke_id + 1
        except IndexError:  # no jokes in database
            new_joke_id = 0

        new_joke = Joke(id=new_joke_id, body=joke_body, vote_count=0, author=user)

        message.reply_text(self.private_get_random_message('joke_submitted'))
        self.session.add(new_joke)
        self.session.commit()
        return

    def profile_command(self, message, chat_data):
        """
        Show information about user.
        """
        user = chat_data['current_user']

        all_users = self.session.query(User).order_by(User.score).all()
        user_rank = all_users.index(user) + 1
        jokes_submitted_count = len(user.get_jokes_submitted())
        average_score = user.get_average_score()

        width = 10
        username_line = '*{}*'.format(user.get_username())
        rank_line = 'rank: {rank}. ({score} points)'.format(rank=user_rank, width=width, score=user.get_score())
        jokes_submitted_line = "jokes submitted: {jokes_count} ({average_score} points/joke)".format(jokes_count=jokes_submitted_count, average_score=average_score)

        user_info = '\n'.join([username_line, rank_line, jokes_submitted_line])
        message.reply_markdown(user_info)
        return

    def top10_command(self, message):
        """
        Show top 10 users by score.
        """
        all_users = self.session.query(User).order_by(User.score).all()
        top_10_users = all_users[:10]
        reply_message = ''

        for index, user in enumerate(top_10_users):
            rank = index + 1
            reply_message += '{rank}. {username} - score: {score}\n'.format(rank=rank, username=user.get_username(), score=user.get_score())

        message.reply_text(reply_message)
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