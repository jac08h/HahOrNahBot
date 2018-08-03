from telegram.ext import Updater, CommandHandler, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy.orm.exc as sql_errors

import logging
from random import randint, choice

from app.models import Joke, User, DuplicatedVoteException, VoteForOwnJokeException

logger = logging.getLogger(__name__)


class HahOrNahBot:
    def __init__(self, token, database_url):
        self.token = token
        self.database_url = database_url

        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        start_handler = CommandHandler('start', self.start_command)
        self.dispatcher.add_handler(start_handler)

        help_handler = CommandHandler('help', self.help_command)
        self.dispatcher.add_handler(help_handler)

        joke_handler = CommandHandler('joke', self.joke_command, pass_chat_data=True)
        self.dispatcher.add_handler(joke_handler)

        add_handler = CommandHandler('add', self.add, pass_args=True)
        self.dispatcher.add_handler(add_handler)

        me_handler = CommandHandler('me', self.me_command)
        self.dispatcher.add_handler(me_handler)

        top10_handler = CommandHandler('top10', self.top10_command)
        self.dispatcher.add_handler(top10_handler)

        callback_handler = CallbackQueryHandler(self.callback_eval, pass_chat_data=True)
        self.dispatcher.add_handler(callback_handler)

        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        self.session = Session()

        self.MIN_JOKE_LENGTH = 10

        self.help_text = """
        *Commands*
        /joke - show random joke
        /add JOKE TEXT - add joke
        /help - show this message
        /top10 - show top 10 users
        """

    # Commands
    def callback_eval(self, bot, update, chat_data):
        logger.info('entering callback eval')
        logger.info(update)
        query_data = update.callback_query.data

        if 'vote' in query_data:
            try:
                joke = chat_data['last_joke']
            except KeyError:
                update.callback_query.message.reply_text("Wait, what? I wasn't telling anything!")
                return

            del chat_data['last_joke']
            if 'positive' in query_data:
                self.vote(bot, update, joke, positive_vote=True)
            else:
                self.vote(bot, update, joke, positive_vote=False)

    def start_command(self, bot, update):
        update.message.reply_text('Welcome to HahOrNah bot - bot that displays random jokes, allows you to vote for jokes or even add some yourself!')
        update.message.reply_markdown(self.help_text)
        return

    def help_command(self, bot, update):
        update.message.reply_markdown(self.help_text)

    def joke_command(self, bot, update, chat_data):
        """
        Return random joke
        """
        all_jokes = self.session.query(Joke).all()

        telegram_id = update.message.chat_id
        telegram_username = update.message.from_user.username
        user = self.__get_user(telegram_id, telegram_username)

        try:
            random_joke_index = randint(0, len(all_jokes)-1)
        except ValueError:
            update.message.reply_text("There are currently no jokes in database. Use /add command to add your joke")
            return

        random_joke = all_jokes.pop(random_joke_index)
        voted_already = random_joke in user.jokes_voted_for
        user_is_author = random_joke in user.jokes_submitted

        while False:
            try:
                random_joke_index = randint(0, len(all_jokes)-1)
            except ValueError:
                update.message.reply_text("You have seen all the jokes. Use /add command to add a new joke!")
                return

            random_joke = all_jokes.pop(random_joke_index)

        vote_options = [
            [InlineKeyboardButton(text='Hah!', callback_data='positive_vote')],
            [InlineKeyboardButton(text='Nah.', callback_data='negative_vote')]
        ]

        vote_options_keyboard = InlineKeyboardMarkup(vote_options, one_time_keyboard=True)

        chat_data['last_joke'] = random_joke
        bot.send_message(chat_id=update.message.chat_id,
                         text=random_joke.get_body(),
                         reply_markup=vote_options_keyboard)

        return

    def vote(self, bot, update, joke, positive_vote):
        """
        Register user's vote for joke. Can't be called directly, only after `/joke` command.

        Arguments:
            positive_vote: bool, True for positive vote
        """
        telegram_id = update.callback_query.message.chat.id
        telegram_username = update.callback_query.message.chat.username
        chat_id = update.callback_query.message.chat.id
        user = self.__get_user(telegram_id, telegram_username)

        try:
            if positive_vote:
                user.vote_for_joke(joke, positive=True)
            else:
                user.vote_for_joke(joke, positive=False)

            self.session.add(user, joke)
            self.session.commit()

            remove_vote_options = ReplyKeyboardRemove()
            bot.send_message(chat_id=chat_id,
                             text='Vote submitted.',
                             reply_markup=remove_vote_options)

        except DuplicatedVoteException:
            remove_vote_options = ReplyKeyboardRemove()
            bot.send_message(chat_id=chat_id,
                             text='duplivated',
                             reply_markup=remove_vote_options)

        except VoteForOwnJokeException:
            remove_vote_options = ReplyKeyboardRemove()
            bot.send_message(chat_id=chat_id,
                             text='own',
                             reply_markup=remove_vote_options)
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
        try:
            last_joke = all_jokes[-1]
            last_joke_id = last_joke.get_id()
            new_joke_id = last_joke_id + 1
        except IndexError:  # no jokes in database
            new_joke_id = 0

        new_joke = Joke(id=new_joke_id, body=new_joke_body, vote_count=0, author=user)

        update.message.reply_text("Thanks for submitting your joke. Your joke's ID is {}.".format(new_joke_id))
        self.session.add(new_joke)
        self.session.commit()
        return

    def me_command(self, bot, update):
        """
        Show information about user.
        """
        telegram_id = update.message.chat_id
        telegram_username = update.message.from_user.username
        user = self.__get_user(telegram_id, telegram_username)

        all_users = self.session.query(User).order_by(User.score).all()
        user_rank = all_users.index(user) + 1

        user_info = str(user) + '\nrank: {}'.format(user_rank)
        update.message.reply_text(user_info)
        return

    def top10_command(self, bot, update):
        """
        Show top 10 users by score.
        """
        telegram_id = update.message.chat_id
        telegram_username = update.message.from_user.username
        user = self.__get_user(telegram_id, telegram_username)

        all_users = self.session.query(User).order_by(User.score).all()
        top_10_users = all_users[:10]
        telegram_message = ''
        for index, user in enumerate(top_10_users):
            rank = index + 1
            telegram_message += '{rank}. {username} - score: {score}\n'.format(rank=rank, username=user.get_username(), score=user.get_score())

        update.message.reply_text(telegram_message)
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
            user = User(id=id, username=telegram_username, score=0)
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