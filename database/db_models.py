from sqlalchemy import ForeignKey, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

Base = declarative_base()


class DbDrug(Base):
    __tablename__ = "drugs"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    descriptions = relationship("DbDescription")

    def __init__(self, name):
        self.name = name


class DbHit(Base):
    __tablename__ = "hits"
    id = Column(Integer, primary_key=True)
    drug_id = Column(Integer, ForeignKey('drugs.id'))
    drug = relationship("DbDrug", backref=backref("hits"))
    source = relationship("DbSource", backref=backref("hits"))
    source_id = Column(Integer, ForeignKey('sources.id'))
    hit_ts = Column(Integer)

    def __init__(self, drug_id, source_id, hit_ts):
        self.drug_id = drug_id
        self.source_id = source_id
        self.hit_ts = hit_ts


class DbDescription(Base):
    __tablename__ = "descr"
    id = Column(Integer, primary_key=True)
    drug_id = Column(Integer, ForeignKey('drugs.id'))
    text = Column(String)

    def __init__(self, text, drug_id):
        self.drug_id = drug_id
        self.text = text


class DbSource(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    created_ts = Column(Integer)
    updated_ts = Column(Integer)
    name = Column(String)
    display_name = Column(String)
    twitter_name = Column(String)
    address = Column(String)

    def __init__(self, name, address, display_name, twitter_name, created_ts, updated_ts):
        self.name = name
        self.address = address
        self.display_name = display_name
        self.twitter_name = twitter_name
        self.created_ts = created_ts
        self.updated_ts = updated_ts
