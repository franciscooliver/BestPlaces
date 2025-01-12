import os
import sys
import psycopg2
from psycopg2.extensions import AsIs
from sqlalchemy import create_engine
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy_utils import database_exists, create_database
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))
    checkpoints = relationship('Checkpoint')

    @property
    def serialize(self):

        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'picture': self.picture
        }


class Token(Base):
    __tablename__ = 'tokens'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    token = Column(String(250), nullable=False)

    @property
    def serialize(self):

        return {
            'id': self.id,
            'name': self.name,
            'token': self.token
        }


class Checkpoint(Base):
    __tablename__ = 'checkpoints'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String(250), nullable=False)
    coordinates = Column(String(250), nullable=False)
    address = Column(String(250))
    description = Column(String(250))

    @property
    def serialize(self):

        return {
            'id': self.id,
            'name': self.name,
            'coordinates': self.coordinates,
            'address': self.address,
            'description': self.description
        }

engine = create_engine('postgresql://'+os.getenv('user') +
                       ':'+os.getenv('password')+'@localhost:5432/bestplaces')

if not database_exists(engine.url):
    create_database(engine.url)

Base.metadata.create_all(engine)
