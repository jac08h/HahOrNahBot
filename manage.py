#!/usr/bin/env python
from migrate.versioning.shell import main

if __name__ == '__main__':
    main(repository='db', url='postgresql+psycopg2://postgres@localhost/hahornahbot', debug='False')
