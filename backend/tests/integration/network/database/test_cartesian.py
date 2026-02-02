import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table
from sqlalchemy.ext.declarative import declarative_base

from src.network.database.session import ImplicitCartesianDetected

Base = declarative_base()
metadata = MetaData()

# Generic Tables
table1 = Table(
    'table1',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String),
    Column('table2_id', Integer, ForeignKey('table2.id')),
)

table2 = Table('table2', metadata, Column('id', Integer, primary_key=True), Column('name', String))


def test_cartesian_product_detection(db):
    # Create a query that would result in a cartesian product
    query = db.query(table1.c.id, table2.c.id)

    # Execute the query
    with pytest.raises(ImplicitCartesianDetected):
        query.all()
