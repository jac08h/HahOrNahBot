import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Joke, User
from app.exceptions import *

logger = logging.getLogger(__name__)

class TelegramBotHelperFunctions():
    """
    Class to provide helper functions to be used by Telegram bot.
    """

    def __init__(self, database_url, joke_limits, user_limits, user_allowed_characters):
        """
        Arguments:
            database_url: string
            joke_limits: dict, with `min` and `max` keys. Used to restrict length of new jokes
            user_limits: dict, with `min` and `max` keys. Used to restrict length of new usernames
            user_allowed_characters: string. Characters which can be used in a username
        """
        self.JOKE_LENGTH_MIN = joke_limits['min']
        self.JOKE_LENGTH_MAX = joke_limits['max']
        self.USERNAME_LENGTH_MIN = user_limits['min']
        self.USERNAME_LENGTH_MAX = user_limits['max']
        self.USERNAME_ALLOWED_CHARACTERS = user_allowed_characters

        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def get_user(self, message, user_data):
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

    def add_user(self, user_id, username):
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

        if self.USERNAME_LENGTH_MAX < len(username):
            raise TooLong

        user = self.session.query(User).filter(User.id == user_id).first()
        assert user is None  # should be called only for new users

        user = User(id=user_id, username=username, score=0)
        self.session.add(user)
        self.session.commit()
        return user

    def add_joke(self, joke_body, author):
        """
        Add new joke to database

        Arguments:
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

    def format_jokes(self, joke_list, start_index, end_index):
        """
        Return string from jokes

        Arguments:
              joke_list: list
              start_index: int
              end_index: int

        Returns:
              tuple:  string: reply message
                      bool: True if all jokes were shown
        """
        jokes_string = []
        all_jokes_shown = False
        for i in range(start_index, end_index):
            try:
                joke = joke_list[i]
            except IndexError:
                all_jokes_shown = True
                break

            joke_message = "{vote_count} votes(id={id})\n{joke_body}".format(
                vote_count=joke.get_vote_count(), id=joke.get_id(), joke_body=joke.get_body()
            )
            jokes_string.append(joke_message)

        reply_message = '\n\n'.join(jokes_string)
        return reply_message, all_jokes_shown

    def get_message(self, update):
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
