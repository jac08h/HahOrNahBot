from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import logging

Base = declarative_base()


association_table = Table('association', Base.metadata,
                          Column('users_id', Integer, ForeignKey('users.id')),
                          Column('jokes_id', Integer, ForeignKey('jokes.id'))
                          )

logger = logging.getLogger(__name__)


class InvalidVoteException(Exception):
    pass


class User(Base):
    __tablename__ = 'users'

    id = Column('id', Integer, primary_key=True, unique=True)
    username = Column('username', String)
    jokes_voted_for = relationship('Joke',
                                   secondary=association_table,
                                   back_populates='users_voted')
    jokes_submitted = relationship('Joke', backref='author')

    def get_id(self):
        return self.id

    def get_username(self):
        return self.username

    def get_jokes_voted_for(self):
        return self.jokes_voted_for

    def vote_for_joke(self, joke, positive):
        """
        Registers user's vote.

        Adds joke to jokes_voted_for attribute of self and calls vote method of joke object.

        Args:
            joke: Joke instance
            positive: bool which is True for positive vote, False for negative vote

        Returns:
            None

        Raises:
            InvalidVoteException: User has already voted.
        """
        if joke not in self.jokes_voted_for:
            self.jokes_voted_for.append(joke)
            joke.register_vote(user=self, positive=positive)
        else:
            error_string = 'Duplicated vote. Joke ID={joke_id} User ID={user_id}'.format(joke_id=joke.get_id(), user_id=self.get_id())
            logger.error(error_string)
            raise InvalidVoteException(error_string)

    def __repr__(self):
        return 'USER:\n id: {id}   username: {username}\njokes voted for: {jokes}'.format(id=self.id, username=self.username, jokes=[joke.id for joke in self.jokes_voted_for])


class Joke(Base):
    __tablename__ = 'jokes'

    id = Column('id', Integer, primary_key=True, unique=True)
    body = Column('body', String(1000))
    vote_count = Column(Integer)
    users_voted = relationship('User',
                               secondary=association_table,
                               back_populates='jokes_voted_for')
    user_id = Column(Integer, ForeignKey('users.id'))

    def get_id(self):
        return self.id

    def get_body(self):
        return self.body

    def get_vote_count(self):
        return self.vote_count

    def get_users_voted(self):
        return self.users_voted

    def increment_vote_count(self):
        try:
            self.vote_count += 1
        except TypeError:
            self.vote_count = 1

    def decrement_vote_count(self):
        try:
            self.vote_count -= 1
        except TypeError:
            self.vote_count = -1

    def add_user(self, user):
        if user not in self.users_voted:
            self.users_voted.append(user)

    def register_vote(self, user, positive):
        """
        Register vote for joke.

        Increments/decrements vote_count, adds user to user_voted.

        Args:
            user: instance of User class who voted for the joke
            positive: bool which is True for positive vote, False for negative vote

        Returns:
            None
        """
        if positive:
            self.increment_vote_count()
        else:
            self.decrement_vote_count()

        self.add_user(user)

    def __repr__(self):
        joke_info =  """id: {id}\nbody: {body}\nvotes: {vote_count}\nauthor: {author}""".format(id=self.id, body=self.body, vote_count=self.vote_count, author=self.author.username)
        # For some reason the formatting is off when using multiline string
        return joke_info