from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Status(Base):
    __tablename__ = "statuses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


class Type(Base):
    __tablename__ = "types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type_id = Column(Integer, ForeignKey("types.id"))

    type = relationship("Type")


class Subcategory(Base):
    __tablename__ = "subcategories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))

    category = relationship("Category")


class DDSEntry(Base):
    __tablename__ = "dds_entries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date)
    status_id = Column(Integer, ForeignKey("statuses.id"))
    type_id = Column(Integer, ForeignKey("types.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    subcategory_id = Column(Integer, ForeignKey("subcategories.id"))
    amount = Column(Float)
    comment = Column(String, nullable=True)

    status = relationship("Status")
    type = relationship("Type")
    category = relationship("Category")
    subcategory = relationship("Subcategory")
