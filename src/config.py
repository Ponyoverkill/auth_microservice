import datetime
import uuid

import pydantic
from phonenumbers import PhoneNumber
from pydantic import EmailStr, Json
from sqlalchemy import Integer, Boolean, String, UUID, BigInteger, Float, DateTime, Time, \
    Date, JSON, MetaData
from sqlalchemy.ext.declarative import declarative_base

type_dict = {
    int: BigInteger,
    bool: Boolean,
    str: String,
    uuid.UUID: UUID(as_uuid=True),
    float: Float,
    datetime.datetime: DateTime,
    datetime.time: Time,
    datetime.date: Date,
    EmailStr: String,
    Json: JSON,
    PhoneNumber: String,
}


