from sqlalchemy import *
from migrate import *

meta = MetaData()

joke = Table(
    'joke', meta,
    Column('id', SmallInteger, primary_key=True),
    Column('body', String(500)),
    Column('vote_count', SmallInteger)
)


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    joke.create()


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    joke.drop()