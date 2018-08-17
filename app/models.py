from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from app.exceptions import InvalidVote

import logging
from string import ascii_letters, digits
Base = declarative_base()


association_table = Table('association', Base.metadata,
                          Column('users_id', Integer, ForeignKey('users.id')),
                          Column('jokes_id', Integer, ForeignKey('jokes.id')),
                          )

logger = logging.getLogger(__name__)

class User(Base):
    __tablename__ = 'users'

    id = Column('id', Integer, primary_key=True, unique=True)
    username = Column('username', String)
    jokes_voted_for = relationship('Joke',
                                   secondary=association_table,
                                   back_populates='users_voted')
    jokes_voted_positive = relationship('Joke',
                                        secondary=association_table,
                                        back_populates='users_voted_positive',
                                        cascade='all, delete, delete-orphan',
                                        single_parent=True)
    jokes_submitted = relationship('Joke', backref='author',cascade='all, delete, delete-orphan', single_parent=True)
    score = Column('score', Integer, default=0)

    def get_id(self):
        return self.id

    def get_username(self):
        return self.username

    def get_jokes_voted_for(self):
        return self.jokes_voted_for

    def get_score(self):
        assert self.score is not None
        return self.score

    def get_jokes_submitted(self):
        return self.jokes_submitted

    def get_jokes_voted_positive(self):
        return self.jokes_voted_positive

    def get_average_score(self):
        jokes_submitted_count = len(self.get_jokes_submitted())
        score = self.get_score()

        try:
            average_score = jokes_submitted_count / score
            return average_score
        except ZeroDivisionError:
            return 0

    def is_author(self, joke):
        return joke in self.jokes_submitted

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
            InvalidVoteException: User has already voted for the joke.
            VoteForOwnJokeException: User is trying to vote for his own joke.
        """
        if joke.author.id == self.id:
            error_string = "Can't vote for your own joke. Joke ID={joke_id} User ID={user_id}".format(joke_id=joke.get_id(), user_id=self.get_id())
            logger.error(error_string)
            raise InvalidVote(error_string)

        if joke in self.jokes_voted_for:
            error_string = 'Duplicated vote. Joke ID={joke_id} User ID={user_id}'.format(joke_id=joke.get_id(), user_id=self.get_id())
            logger.error(error_string)
            raise InvalidVote(error_string)

        else:
            if positive:
                self.score += 1
                self.jokes_voted_positive.append(joke)
            else:
                self.score -= 1

            self.jokes_voted_for.append(joke)
            joke.register_vote(user=self, positive=positive)

    def __repr__(self):
        return 'username: {username} \nid: {id}\nscore: {score}\njokes submitted: {jokes_submitted}'.format(username=self.get_username(), id=self.get_id(), score=self.get_score(), jokes_submitted=len(self.jokes_submitted))


class Joke(Base):
    __tablename__ = 'jokes'

    id = Column('id', Integer, primary_key=True, unique=True)
    body = Column('body', String(1000))
    vote_count = Column(Integer)
    users_voted = relationship('User',
                               secondary=association_table,
                               back_populates='jokes_voted_for')
    users_voted_positive = relationship('User',
                                        secondary=association_table,
                                        back_populates='jokes_voted_positive')
    user_id = Column(Integer, ForeignKey('users.id'))

    def get_id(self):
        return self.id

    def get_body(self):
        return self.body

    def get_vote_count(self):
        return self.vote_count

    def get_users_voted(self):
        return self.users_voted

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
            self.vote_count += 1
            self.users_voted_positive.append(user)
        else:
            self.vote_count -= 1

        self.users_voted.append(user)

    def __repr__(self):
        joke_info =  """id: {id}\nbody: {body}\nvotes: {vote_count}\nauthor: {author}""".format(id=self.id, body=self.body, vote_count=self.vote_count, author=self.author.username)
        # For some reason the formatting is off when using multiline string
        return joke_info

if __name__ == '__main__':
    a = User(username='asdf', id=0)
    a.set_username('fasdljkfsadlfjda', 21039)