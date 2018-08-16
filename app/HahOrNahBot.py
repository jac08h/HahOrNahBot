from telegram.ext import (Updater, Filters,
                          CommandHandler, ConversationHandler, RegexHandler, MessageHandler)
from telegram import (KeyboardButton, ReplyKeyboardMarkup,
                      ReplyKeyboardRemove)


import logging
from random import randint, choice, shuffle
from string import ascii_letters, digits

from app.TelegramBotHelperMethods import TelegramBotHelperFunctions
from app.TelegramBotResponses import TelegramBotResponses
from app.models import Joke, User
from app.exceptions import *

logger = logging.getLogger(__name__)

USERNAME_RECEIVED = 0
JOKE_RECEIVED, CANCEL = 0, 1
MJ_CHOOSING, MJ_NEXT, MJ_CANCEL = range(3)

class HahOrNahBot(TelegramBotHelperFunctions, TelegramBotResponses):
    def __init__(self, token, database_url):
        # Configuration variables
        BOT_RESPONSES_FILENAME = 'bot_responses/bot_responses.json'
        JOKE_LENGTH_MIN = 10
        JOKE_LENGTH_MAX = 1000
        USERNAME_LENGTH_MIN = 5
        USERNAME_LENGTH_MAX = 20
        USERNAME_ALLOWED_CHARACTERS = set(ascii_letters + digits + '-_')
        self.MY_JOKES_PER_MESSAGE = 5

        joke_limits = {'min':JOKE_LENGTH_MIN, 'max':JOKE_LENGTH_MAX}
        username_limits = {'min':USERNAME_LENGTH_MIN, 'max':USERNAME_LENGTH_MAX}

        TelegramBotResponses.__init__(self, BOT_RESPONSES_FILENAME)
        TelegramBotHelperFunctions.__init__(self, database_url, joke_limits, username_limits, USERNAME_ALLOWED_CHARACTERS)

        self.token = token
        self.database_url = database_url
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        start_handler = CommandHandler('start', self.menu, pass_user_data=True)
        help_handler = CommandHandler('help', self.help)
        cancel_handler = CommandHandler('cancel', self.cancel_conversation)
        random_joke_handler = CommandHandler('random_joke', self.display_random_joke, pass_user_data=True)
        random_favorite_joke_handler = CommandHandler('random_favorite_joke', self.display_random_favorite_joke, pass_user_data=True)
        best_joke_handler = CommandHandler('best_joke', self.display_best_joke, pass_user_data=True)
        vote_handler = RegexHandler('^(/hah|/nah)$', self.vote_for_joke, pass_user_data=True)
        profile_handler = CommandHandler('profile', self.profile, pass_user_data=True)

        # Whenever the method `self.private_get_user` raises an exception, keyboard with two options is displayed.
        # /whatever string is stored in 'user_new_keyboard_button' in bot_responses.json and /cancel
        # This ConversationHandler is entered when the first button is clicked.
        new_user_keyboard_string = self.get_one_response('user_new_keyboard_button')
        new_user_handler = ConversationHandler(
            entry_points=[RegexHandler("{}".format(new_user_keyboard_string), self.new_user_prompt)],
            states={
                USERNAME_RECEIVED: [MessageHandler(Filters.text,
                                                   self.new_user_received_username,
                                                   pass_user_data=True)
                                    ],
            },
            fallbacks=[cancel_handler]
        )

        new_joke_handler = ConversationHandler(
            entry_points=[RegexHandler("/add_joke", self.new_joke_prompt)],
            states={
                JOKE_RECEIVED: [MessageHandler(Filters.text, self.new_joke_received, pass_user_data=True)],
                CANCEL: [cancel_handler]
            },
            fallbacks=[cancel_handler])

        my_jokes_handler = ConversationHandler(
            entry_points=[RegexHandler('/my_jokes', self.my_jokes, pass_user_data=True)],
            states={
                MJ_CHOOSING: [RegexHandler('^(/next|/cancel)$', self.my_jokes_choosing, pass_user_data=True)],
                MJ_NEXT: [RegexHandler('.*', self.my_jokes, pass_user_data=True)],
            },
            fallbacks=[cancel_handler])

        menu_handler = RegexHandler('menu', self.menu, pass_user_data=True) # any message
        handlers = [start_handler,
                    help_handler,
                    new_user_handler,
                    new_joke_handler,

                    random_joke_handler,
                    random_favorite_joke_handler,
                    best_joke_handler,
                    vote_handler,

                    my_jokes_handler,
                    profile_handler,

                    menu_handler]

        for handler in handlers:
            self.dispatcher.add_handler(handler)

    def display_new_user_keyboard(self, bot, update):
        """
        Display keyboard prompt to register new user.

        text located in `user_new_keyboard_button` in responses file | /cancel
        """
        keyboard_buttons = [[KeyboardButton(self.get_one_response('user_new_keyboard_button'))],
                            [KeyboardButton('/cancel')]]
        bot.send_message(chat_id=update.message.chat_id,
                         text=self.get_random_response('user_not_registered'),
                         reply_markup=ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True))
        return

    def display_new_joke_keyboard(self, bot, update):
        """
        Display keyboard prompt to add new joke

        text located in `joke_new_keyboard_button` in responses file | /cancel
        """
        message = update.message
        keyboard_buttons = [[KeyboardButton(self.get_one_response('joke_new_keyboard_button'))],
                            [KeyboardButton('/cancel')]]
        bot.send_message(chat_id=message.chat_id,
                         text=self.get_random_response('joke_new_ask'),
                         reply_markup=ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True))
        return

    def display_menu_keyboard(self, bot, update):
        """
        Display menu
        """
        menu_options = [
            [KeyboardButton('/random_joke')],
            [KeyboardButton('/random_favorite_joke')],
            [KeyboardButton('/best_joke')],
            [KeyboardButton('/add_joke')],
            [KeyboardButton('/my_jokes')],
            [KeyboardButton('/profile')],
            [KeyboardButton('/help')],
        ]

        keyboard = ReplyKeyboardMarkup(menu_options)
        bot.send_message(chat_id=update.message.chat_id,
                         text=self.get_random_response('menu'),
                         reply_markup=keyboard)
        return

    def display_vote_keyboard(self, bot, update):
        """
        Display vote options.

        /hah | /nah
        """
        vote_options = [
            [KeyboardButton('/hah')],
            [KeyboardButton('/nah')],
        ]

        vote_options_keyboard = ReplyKeyboardMarkup(vote_options, one_time_keyboard=True)
        bot.send_message(chat_id=update.message.chat.id,
                         text=self.get_random_response('hah_or_nah'),
                         reply_markup=vote_options_keyboard)
        return

    def display_next_cancel_keyboard(self, bot, update):
        """
        /next | /cancel
        """
        vote_options = [
            [KeyboardButton('/next')],
            [KeyboardButton('/cancel')],
        ]

        vote_options_keyboard = ReplyKeyboardMarkup(vote_options, one_time_keyboard=True)
        bot.send_message(chat_id=update.message.chat.id,
                         text=self.get_random_response('my_jokes_show_next'),
                         reply_markup=vote_options_keyboard)
        return

    def remove_keyboard(self, bot, update, text):
        """
        Remove any keyboard

        Arguments:
            text: string to be displayed
        """
        remove_keyboard = ReplyKeyboardRemove()
        bot.send_message(chat_id=update.message.chat.id,
                         text=text,
                         reply_markup=remove_keyboard)

        return

    def help(self, bot, update):
        message = update.message
        help_message = '''
        *Commands*
        /help - Display this message
        /menu - Display commands keyboard
        /random\_joke - Display random joke
        /random\_favorite\_joke - Display random joke from favorites
        /best\_joke - Display joke with the most votes that you didn't see yet.
        /add\_joke - Proceed to add a joke
        /profile - Display user profile
        /top\_10 - Display top 10 users by score
        /cancel - Cancel current action (adding joke/registering user)
        '''
        message.reply_markdown(help_message)
        return

    def cancel_conversation(self, bot, update):
        reply = self.get_random_response('cancel')
        self.remove_keyboard(bot, update, reply)
        return ConversationHandler.END

    def menu(self, bot, update, user_data):
        """
        Display menu keyboard
        """
        message = update.message
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        self.display_menu_keyboard(bot, update)

    def new_user_prompt(self, bot, update):
        """
        Display prompt message like `How should I call you?`, after which user is expected to enter a new username.

        Method is an entry point in ConversationHandler, which is entered after user has was presented with a keyboard to
            -proceed with registration / -cancel
        and first option was selected

        Next method called is `self.new_user_received_username`
        """
        message = update.message
        message.reply_text(self.get_random_response('user_new_prompt'))
        return USERNAME_RECEIVED

    def new_user_received_username(self, bot, update, user_data):
        """
        Try to register user.
        If username doesn't meet restrictions, display error message and wait for another response.
        If it does, display menu keyboard and return from ConversationHandler

        Method is entered after `self.new_user_prompt` in ConversationHandler
        """
        message = update.message
        username = message.text
        user_id = message.chat.id

        try:
            user = self.add_user(user_id, username)
            user_data['user'] = user

            message.reply_text(self.get_random_response('user_register_success'))
            self.display_menu_keyboard(bot, update)
            return ConversationHandler.END
        except InvalidCharacters:
            error_message = self.get_random_response('username_invalid_characters')
            message.reply_text(error_message)
        except TooShort:
            error_message = self.get_random_response('username_too_short')
            message.reply_text(error_message)
        except TooLong:
            error_message = self.get_random_response('username_too_long')
            message.reply_text(error_message)

    def new_joke_prompt(self, bot, update):
        """
        Display prompt message like `I'm listening!`, after which user is expected to enter a new joke

        Method is an entry point in ConversationHandler, which is entered after `/add_joke` command.

        Next method called is `self.new_joke_received`
        """
        message = update.message
        remove_keyboard = ReplyKeyboardRemove()
        reply_message = self.get_random_response('joke_new_prompt')
        bot.send_message(chat_id=message.chat.id,
                         text=reply_message,
                         reply_markup=remove_keyboard)

        return JOKE_RECEIVED

    def new_joke_received(self, bot, update, user_data):
        """
        Try to add a joke.
        If the joke doesn't meet restrictions, display error message and wait for another response.
        If it does, display menu keyboard and return from ConversationHandler

        Method is entered after `self.new_joke_prompt` in ConversationHandler.
        """
        message = update.message
        # Check if user is registered
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        joke_body = message.text
        try:
            self.add_joke(joke_body, user)
            message.reply_text(self.get_random_response('joke_submitted'))
            self.display_menu_keyboard(bot, update)
            return ConversationHandler.END
        except TooShort:
            error_message = self.get_random_response('joke_too_short')
            message.reply_text(error_message)
        except TooLong:
            error_message = self.get_random_response('joke_too_long')
            message.reply_text(error_message)

    def display_random_joke(self, bot, update, user_data):
        """
        Display random joke
        """
        message = update.message

        # Check if user is registered
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        # Check if database is not empty
        all_jokes = self.session.query(Joke).all()
        try:
            joke = all_jokes[0]
        except IndexError:
            message.reply_text(self.get_random_response('no_new_jokes'))
            return

        shuffle(all_jokes)

        for random_joke in all_jokes:
            voted_already = random_joke in user.jokes_voted_for
            user_is_author = random_joke in user.jokes_submitted
            if not voted_already and not user_is_author:
                # Remember last joke displayn - used in self.vote_for_joke to vote for right joke
                user_data['last_joke'] = random_joke
                # Display joke
                message.reply_text(random_joke.get_body())
                self.display_vote_keyboard(bot, update)
                return

        message.reply_text(self.get_random_response('no_new_jokes'))
        return

    def display_random_favorite_joke(self, bot, update, user_data):
        """
        Display random joke from jokes user voted for.
        """

        # Check if user is registered
        message = update.message
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        # Check if there are any jokes marked as favorite
        all_favorite_jokes = user.get_jokes_voted_positive()
        try:
            random_joke = choice(all_favorite_jokes)
        except IndexError:
            message.reply_text(self.get_random_response('joke_no_favorite'))
            return

        # Display joke
        message.reply_text(random_joke.get_body())
        return

    def display_best_joke(self, bot, update, user_data):
        """
        Display joke with the highest number of votes the user hasn't seen yet.
        """
        # Check if user is registered
        message = update.message
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        jokes_by_score = self.session.query(Joke).order_by(Joke.vote_count).all()
        for joke in jokes_by_score:
            voted_already = joke in user.jokes_voted_for
            user_is_author = joke in user.jokes_submitted
            if not voted_already and not user_is_author:
                message.reply_text(joke.get_body())
                return


    def vote_for_joke(self, bot, update, user_data):
        """
        Register user's vote for joke.
        """
        message = update.message
        # Check if user is registered
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        # Check if is called after displaying a joke
        try:
            joke = user_data['last_joke']
        except KeyError:
            message.reply_text(self.get_random_response('joke_no_current'))
            return

        try:
            if 'hah' in message.text:
                user.vote_for_joke(joke, positive=True)
            else:
                user.vote_for_joke(joke, positive=False)

            self.session.add(user, joke)
            self.session.commit()

        except InvalidVote as e:
            logger.error(e)

        finally:
            self.remove_keyboard(update, bot, self.get_random_response('after_vote'))
            del user_data['last_joke']
            return


    def my_jokes(self, bot, update, user_data):
        """
        Display jokes submitted by user sorted by score.

        Afterwards displays a keyboard to show next jokes or cancel.
        Uses `self.MY_JOKES_PER_MESSAGE` variable to get the number of jokes to be displayed.
        Uses `my_jokes_index` key in `user_data` to keep track of index of jokes to be shown.
        """
        message = update.message
        # Check if user is registered
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        try:
            first_joke_index = user_data['my_jokes_index']
        except KeyError:
            first_joke_index = 0

        last_joke_index = first_joke_index + self.MY_JOKES_PER_MESSAGE
        all_jokes = self.session.query(Joke).order_by(Joke.vote_count).all()
        user_jokes = [joke for joke in all_jokes if user.is_author(joke)]
        user_data['user_jokes'] = user_jokes

        reply_message, all_jokes_shown = self.format_jokes(user_jokes, first_joke_index, last_joke_index)

        if len(reply_message) == 0:
            if first_joke_index == 0: # user didn't submit any joke
                message.reply_text(self.get_random_response('my_jokes_no_jokes'))
            else:
                # user has submitted jokes but on this iteration there are no jokes to be displayed
                # happens when number of jokes submitted is multiple of `self.MY_JOKES_PER_MESSAGE`
                # e.g. submitted 20 jokes and the bot displays 10 per message - after second try there
                # won't be any jokes to be displayed

                self.remove_keyboard(bot, update, self.get_random_response('my_jokes_all_jokes_shown'))

            return ConversationHandler.END

        message.reply_text(reply_message)
        if all_jokes_shown:
            self.remove_keyboard(bot, update, self.get_random_response('my_jokes_all_jokes_shown'))
            return ConversationHandler.END
        else:
            user_data['my_jokes_index'] = last_joke_index
            self.display_next_cancel_keyboard(bot, update)
            return MJ_CHOOSING

    def my_jokes_choosing(self, bot, update, user_data):
        message = update.message
        # Check if user is registered
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        user_choice = message.text
        if 'next' in user_choice:
            self.my_jokes(bot, update, user_data)
            return MJ_NEXT
        elif 'cancel' in user_choice:
            return ConversationHandler.END
        else:
            message.reply_text(self.get_random_response('my_jokes_invalid_choice'))
            return MJ_CHOOSING

    def profile(self, bot, update, user_data):
        """
        Display information about user.
        """
        message = update.message
        try:
            user = self.get_user(message, user_data)
        except UserDoesNotExist:
            self.display_new_user_keyboard(bot, update)
            return

        all_users = self.session.query(User).order_by(User.score).all()
        user_rank = all_users.index(user) + 1
        jokes_submitted_count = len(user.get_jokes_submitted())
        average_score = user.get_average_score()

        width = 10
        username_line = '*{}*'.format(user.get_username())
        rank_line = 'rank: {rank}. ({score} points)'.format(rank=user_rank, width=width, score=user.get_score())
        jokes_submitted_line = "jokes submitted: {jokes_count} ({average_score} points/joke)".format(
            jokes_count=jokes_submitted_count, average_score=average_score)

        user_info = '\n'.join([username_line, rank_line, jokes_submitted_line])
        message.reply_markdown(user_info)
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