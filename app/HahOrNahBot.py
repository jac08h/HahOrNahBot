from telegram.ext import Updater, CommandHandler
import telegram

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy.orm.exc as sql_errors

import logging
from random import randint

from app.models import Joke, User, DuplicatedVoteException, VoteForOwnJokeException

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
        add_handler = CommandHandler('add', self.add, pass_args=True)
        self.dispatcher.add_handler(add_handler)
        me_handler = CommandHandler('me', self.me)
        self.dispatcher.add_handler(me_handler)
        top10_handler = CommandHandler('top10', self.top10)
        self.dispatcher.add_handler(top10_handler)

        engine = create_engine(database_url, echo=True)
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

    def start(self, bot, update):
        update.message.reply_text('Welcome to HahOrNah bot - bot that displays random jokes, allows you to vote for jokes or even add some yourself!')
        update.message.reply_markdown(self.help_text)
        return

    def help(self, bot, update):
        update.message.reply_markdown(self.help_text)

    def joke(self, bot, update, chat_data):
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

        while random_joke in user.jokes_voted_for or random_joke in user.jokes_submitted:
            try:
                random_joke_index = randint(0, len(all_jokes)-1)
            except ValueError:
                update.message.reply_text("You have seen all the jokes. Use /add command to add a new joke!")
                return

            random_joke = all_jokes.pop(random_joke_index)

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

            bot.send_message(chat_id=update.message.chat_id,
                             text='Vote submitted.')

            del chat_data['last_joke_displayed']
            return

        except DuplicatedVoteException:
            update.message.reply_text('You already voted for this joke.')

        except VoteForOwnJokeException:
            update.message.reply_text("You can't vote for your own joke.")

        finally:
            # Clear vote buttons
            remove_vote_options_markup = telegram.ReplyKeyboardRemove()
            bot.send_message(chat_id=update.message.chat_id,
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

    def me(self, bot, update):
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

    def top10(self, bot, update):
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