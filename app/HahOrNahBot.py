from telegram.ext import (Updater,
                          CommandHandler, ConversationHandler, RegexHandler, MessageHandler, CallbackQueryHandler,
                          Filters)

from telegram import (KeyboardButton, ReplyKeyboardMarkup,
                      InlineKeyboardMarkup, InlineKeyboardButton,
                      ReplyKeyboardRemove)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import logging
from random import randint, choice
import json
from sys import exit
from string import ascii_letters, digits
from time import sleep

from app.models import Joke, User
from app.exceptions import *


logger = logging.getLogger(__name__)

USERNAME_RECEIVED = 0
JOKE_RECEIVED = 0

class HahOrNahBot:
    def __init__(self, token, database_url):
        self.JOKE_LENGTH_MIN = 10
        self.JOKE_LENGTH_MAX = 1000
        self.USERNAME_LENGTH_MIN = 5
        self.USERNAME_LENGTH_MAX = 20
        self.USERNAME_ALLOWED_CHARACTERS = set(ascii_letters + digits + '-_')

        self.WAIT_TIME = 2

        self.RESPONSES_FILE = 'bot_responses/bot_responses.json'
        self.responses = self.private_get_responses(self.RESPONSES_FILE)

        self.token = token
        self.database_url = database_url
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        new_user_keyboard_string = self.private_get_one_response('user_new_keyboard_button')
        new_user_handler = ConversationHandler(
            entry_points=[RegexHandler("{}".format(new_user_keyboard_string), self.new_user_prompt)],
            states={
                USERNAME_RECEIVED: [MessageHandler(Filters.text,
                                                     self.new_user_received_username,
                                                     pass_user_data=True)
                                    ],
            },
            fallbacks=[RegexHandler('Cancel', self.cancel)]
        )

        new_joke_keyboard_string = self.private_get_one_response('joke_new_keyboard_button')
        new_joke_handler = ConversationHandler(
            entry_points=[RegexHandler("/add_joke".format(new_joke_keyboard_string), self.new_joke_prompt)],
            states={
                JOKE_RECEIVED: [MessageHandler(Filters.text,
                                                  self.new_joke_received,
                                                  pass_user_data=True)
                    ]
            },
            fallbacks=[RegexHandler('Cancel', self.cancel)]
        )

        start_handler = CommandHandler('start', self.menu, pass_user_data=True)
        random_joke_handler = CommandHandler('random_joke', self.show_random_joke, pass_user_data=True)
        random_favorite_joke_handler = CommandHandler('random_favorite_joke', self.show_random_favorite_joke, pass_user_data=True)
        profile_handler = CommandHandler('profile', self.profile, pass_user_data=True)
        top10_handler = CommandHandler('top10', self.top10, pass_user_data=True)

        menu_handler = RegexHandler('menu', self.menu, pass_user_data=True)
        handlers = [start_handler,
                    new_user_handler,
                    new_joke_handler,

                    random_joke_handler,
                    random_favorite_joke_handler,
                    profile_handler,
                    top10_handler,

                    menu_handler]

        for handler in handlers:
            self.dispatcher.add_handler(handler)

        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    # PRIVATE METHODS

    def private_get_responses(self, responses_file):
        """
        Get bot responses defined in self.RESPONSES_FILE

        Returns:
            dict
        """
        try:
            with open(responses_file, 'r') as fp:
                responses = json.load(fp)
            return responses

        except FileNotFoundError:
            logger.info('Responses file {} not found. Exiting'.format(responses_file))
            exit()

    def private_get_random_response(self, state):
        """
        Return random response from config_file

        Returns:
            string
        """
        try:
            assert state in self.responses.keys()  # should be called only with states defined in self.RESPONSES_FILE
        except AssertionError:
            logger.info('No response found for ' + state)
            logger.info(self.responses.keys())
            exit()

        response = choice(self.responses[state])
        return response

    def private_get_one_response(self, state):
        """
        Return response from config_file when there is only one possible

        Returns:
            string

        """
        try:
            assert state in self.responses.keys()  # should be called only with states defined in self.RESPONSES_FILE
        except AssertionError:
            logger.info('No response found for ' + state)
            logger.info(self.responses.keys())
            exit()

        response = self.responses[state][0]
        return response

    def private_get_user(self, message, user_data):
        """
        Get user by id if the user is in database, raise exception if user is not found.

        Returns:
            instance of User class if user exists

        Raises:
            UserDoesNotExist
        """

        # Check user in cache
        try:
            user = user_data['current_user']
            return user
        except KeyError:
            pass

        # Check if user is in database
        user_id = message.chat.id
        user = self.session.query(User).filter(User.id == user_id).first()
        if user is None:
            raise UserDoesNotExist

        else:
            user_data['current_user'] = user
            return user

    def private_add_user(self, user_id, username):
        """
        Add new user to database

        Returns:
            User object

        Raises:
            InvalidCharacters
            TooShort
            TooLong
        """

        only_allowed_chars = set(username) <= self.USERNAME_ALLOWED_CHARACTERS
        if not only_allowed_chars:
            raise InvalidCharacters

        if len(username) < self.USERNAME_LENGTH_MIN:
            raise TooShort

        if  self.USERNAME_LENGTH_MAX < len(username):
            raise TooLong

        user = self.session.query(User).filter(User.id==user_id).first()
        assert user is None  # should be called only for new users

        user = User(id=user_id, username=username, score=0)
        self.session.add(user)
        self.session.commit()
        return user

    def private_add_joke(self, joke_body, author):
        """
        Add new joke to database

        Arguments:
            joke_id: int
            joke_body: str
            author: User

        Returns:
            None

        Raises:
            InvalidCharacters
            TooShort
            TooLong
        """
        if len(joke_body) < self.JOKE_LENGTH_MIN:
            raise TooShort

        if self.JOKE_LENGTH_MAX < len(joke_body):
            raise TooLong


        # Calculate id by adding one to last joke's id
        all_jokes = self.session.query(Joke).order_by(Joke.id).all()
        try:
            last_joke = all_jokes[-1]
            last_joke_id = last_joke.get_id()
            joke_id = last_joke_id + 1
        except IndexError:  # no jokes in database
            joke_id = 0

        new_joke = Joke(id=joke_id, body=joke_body, vote_count=0, author=author)
        self.session.add(new_joke)
        self.session.commit()
        return

    def private_get_message(self, update):
        """
        Depending on the type of response, message object can be located in update.message or update.message.callback_query.

        Returns:
            Message
        """
        try:
            message = update.callback_query.message
        except AttributeError:
            message = update.message  # this line returns None if a callback is used so it wouldn't work vice-versa

        return message

    def show_new_user_keyboard(self, bot, update):
        """
        Display keyboard prompt to register new user
        """
        keyboard_buttons = [[KeyboardButton(self.private_get_one_response('user_new_keyboard_button'))],
                            [KeyboardButton('Cancel')]]
        bot.send_message(chat_id=update.message.chat_id,
                         text=self.private_get_random_response('user_not_registered'),
                         reply_markup=ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True))
        return

    def show_new_joke_keyboard(self, bot, update):
        """
        Display keyboard prompot to add new joke
        """
        message = self.private_get_message(update)
        keyboard_buttons = [[KeyboardButton(self.private_get_one_response('joke_new_keyboard_button'))],
                            [KeyboardButton('Cancel')]]
        bot.send_message(chat_id=message.chat_id,
                         text=self.private_get_random_response('joke_new_ask'),
                         reply_markup=ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True))
        return

    def show_menu_keyboard(self, bot, update):
        """
        Display menu
        """
        menu_options = [
            [KeyboardButton('/random_joke')],
            [KeyboardButton('/random_favorite_joke')],
            [KeyboardButton('/add_joke')],
            [KeyboardButton('/profile')],
            [KeyboardButton('/top10')],
        ]

        keyboard = ReplyKeyboardMarkup(menu_options)
        bot.send_message(chat_id=update.message.chat_id,
                         text=self.private_get_random_response('menu'),
                         reply_markup=keyboard)
        return


    # COMMAND METHODS
    def cancel(self, bot, update):
        message = self.private_get_message(update)
        message.reply_text(self.private_get_random_response('cancel'))
        return

    def menu(self, bot, update, user_data):
        message = self.private_get_message(update)
        try:
            user = self.private_get_user(message, user_data)
        except UserDoesNotExist:
            self.show_new_user_keyboard(bot, update)
            return

        self.show_menu_keyboard(bot, update)

    def new_user_prompt(self, bot, update):
        message = self.private_get_message(update)
        message.reply_text(self.private_get_random_response('user_new_prompt'))
        return USERNAME_RECEIVED

    def new_user_received_username(self, bot, update, user_data):
        message = self.private_get_message(update)
        username = message.text
        user_id = message.chat.id

        try:
            user = self.private_add_user(user_id, username)
            user_data['user'] = user

            message.reply_text(self.private_get_random_response('user_register_success'))
            self.show_menu_keyboard(bot, update)

        except InvalidCharacters:
            error_message = self.private_get_random_response('username_invalid_characters')
            message.reply_text(error_message)
        except TooShort:
            error_message = self.private_get_random_response('username_too_short')
            message.reply_text(error_message)
        except TooLong:
            error_message = self.private_get_random_response('username_too_long')
            message.reply_text(error_message)
        finally:
            return

    def new_joke_prompt(self, bot, update):
        message = self.private_get_message(update)
        remove_keyboard = ReplyKeyboardRemove()
        reply_message = self.private_get_random_response('joke_new_prompt')
        bot.send_message(chat_id=message.chat.id,
                         text=reply_message,
                         reply_markup=remove_keyboard)

        return JOKE_RECEIVED

    def new_joke_received(self, bot, update, user_data):
        # Check if user is registered
        message = self.private_get_message(update)
        try:
            user = self.private_get_user(message, user_data)
        except UserDoesNotExist:
            self.show_new_user_keyboard(bot, update)
            return

        joke_body = message.text
        try:
            self.private_add_joke(joke_body, user)
            message.reply_text(self.private_get_random_response('joke_submitted'))
            self.show_menu_keyboard(bot, update)
        except TooShort:
            error_message = self.private_get_random_response('joke_too_short')
            message.reply_text(error_message)
        except TooLong:
            error_message = self.private_get_random_response('joke_too_long')
            message.reply_text(error_message)
        finally:
            return

    def show_random_joke(self, bot, update, user_data):
        """
        Return random joke
        """
        message = self.private_get_message(update)

        # Check if user is registered
        try:
            user = self.private_get_user(message, user_data)
        except UserDoesNotExist:
            self.show_new_user_keyboard(bot, update)
            return

        # Check if database is not empty
        all_jokes = self.session.query(Joke).all()
        try:
            random_joke_index = randint(0, len(all_jokes)-1)
        except ValueError:
            message.reply_text(self.private_get_random_response('no_new_jokes'))
            return


        # Find joke which user hasn't voted on and is not author of the joke
        random_joke = all_jokes.pop(random_joke_index)
        voted_already = random_joke in user.jokes_voted_for
        user_is_author = random_joke in user.jokes_submitted
        while voted_already or user_is_author:
            try:
                random_joke_index = randint(0, len(all_jokes)-1)
            except ValueError:
                message.reply_text(self.private_get_random_response('no_new_jokes'))
                return
            random_joke = all_jokes.pop(random_joke_index)

        vote_options = [
            [InlineKeyboardButton(text=self.private_get_random_response('positive_vote_keyboard_button'), callback_data='positive_vote')],
            [InlineKeyboardButton(text=self.private_get_random_response('negative_vote_keyboard_button'), callback_data='negative_vote')]
        ]
        vote_options_keyboard = InlineKeyboardMarkup(vote_options)

        # Remember last joke shown - used in self.vote_for_joke to vote for right joke
        user_data['last_joke'] = random_joke
        # Display joke
        message.reply_text(random_joke.get_body())

        # Display vote keyboard
        bot.send_message(chat_id=message.chat.id,
                         text=self.private_get_random_response('hah_or_nah'),
                         reply_markup=vote_options_keyboard)
        return

    def show_random_favorite_joke(self, bot, update, user_data):
        """
        Return random joke from jokes user voted for.
        """

        # Check if user is registered
        message = self.private_get_message(update)
        try:
            user = self.private_get_user(message, user_data)
        except UserDoesNotExist:
            self.show_new_user_keyboard(bot, update)
            return

        # Check if there are any jokes marked as favorite
        all_favorite_jokes = user.get_jokes_voted_positive()
        try:
            random_joke = choice(all_favorite_jokes)
        except IndexError:
            message.reply_text(self.private_get_random_response('joke_no_favorite'))
            return

        # Display joke
        message.reply_text(random_joke.get_body())
        return

    def vote_for_joke(self, update, bot, user_data, joke, positive_vote):
        """
        Register user's vote for joke.
        Remove

        Arguments:
            positive_vote: bool, True for positive vote
        """

        # Check if user is registered
        message = self.private_get_message(update)
        try:
            user = self.private_get_user(message, user_data)
        except UserDoesNotExist:
            self.show_new_user_keyboard(bot, update)
            return

        try:
            if positive_vote:
                user.vote_for_joke(joke, positive=True)
                message.edit_text(self.private_get_random_response('positive_vote'))
            else:
                user.vote_for_joke(joke, positive=False)
                message.edit_text(self.private_get_random_response('negative_vote'))

            self.session.add(user, joke)
            self.session.commit()

        except InvalidVote as e:
            logger.error(e)

        return

    def profile(self, bot, update, user_data):
        """
        Show information about user.
        """
        message = self.private_get_message(update)
        try:
            user = self.private_get_user(message, user_data)
        except UserDoesNotExist:
            self.show_new_user_keyboard(bot, update)
            return

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

    def top10(self, bot, update, user_data):
        """
        Show top 10 users by score.
        """
        message = self.private_get_message(update)
        try:
            user = self.private_get_user(message, user_data)
        except UserDoesNotExist:
            self.show_new_user_keyboard(bot, update)
            return

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