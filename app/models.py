from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


association_table = Table('association', Base.metadata,
                          Column('users_id', Integer, ForeignKey('users.id')),
                          Column('jokes_id', Integer, ForeignKey('jokes.id'))
                          )


class User(Base):
    __tablename__ = 'users'

    id = Column('id', Integer, primary_key=True, unique=True)
    username = Column('username', String)
    jokes_voted_for = relationship('Joke',
                                   secondary=association_table,
                                   back_populates='users_voted')

    def get_id(self):
        return self.id

    def get_username(self):
        return self.username

    def get_jokes_voted_for(self):
        return self.jokes_voted_for

    def vote_for_joke(self, joke):
        self.jokes_voted_for.append(joke)

    def __repr__(self):
        return '[{id}] User: {username}'.format(id=self.id, username=self.username)


class Joke(Base):
    __tablename__ = 'jokes'

    id = Column('id', Integer, primary_key=True, unique=True)
    body = Column('body', String(1000))
    vote_count = Column(Integer)
    users_voted = relationship('User',
                               secondary=association_table,
                               back_populates='jokes_voted_for')

    def get_id(self):
        return self.id

    def get_body(self):
        return self.body

    def get_vote_count(self):
        return self.vote_count

    def get_users_voted(self):
        return self.users_voted

    def register_vote(self, user):
        self.users_voted.append(user)


    def __repr__(self):
        return '[{id}] Joke: {body}'.format(id=self.id, body=self.body)