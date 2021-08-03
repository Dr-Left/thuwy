from app import db
from flask_sqlalchemy import SQLAlchemy
import json as Json

from . import timetools as timestamp

# db: SQLAlchemy
# class Student(db.Model):
#     __tablename__ = 'students'
#     id = db.Column('id', db.Integer, primary_key = True)
#     name = db.Column(db.String(100))
#     city = db.Column(db.String(100))


class Admin(db.Model):
    __tablename__ = 'admins'
    openid        = db.Column(db.Text, primary_key = True)

class User(db.Model):
    __tablename__ = "users"
    openid        = db.Column(db.Text, primary_key = True)
    schoolId      = db.Column('school_id', db.Text, unique=True)
    name          = db.Column(db.Text)
    clazz         = db.Column(db.Text)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def __init__(self, openid, *args, **kwargs) -> None:
        self.openid = openid
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        return f'User({self.name}, {self.schoolId}, {self.clazz}, {self.openid})'

class Item(db.Model):
    __tablename__ = "items"
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.Text, nullable=False)
    available     = db.Column(db.Integer)
    delete        = db.Column(db.Integer)
    rsvMethod     = db.Column('rsv_method', db.Integer, nullable=False)
    briefIntro    = db.Column('brief_intro', db.Text)
    thumbnail     = db.Column(db.Text)
    mdIntro       = db.Column('md_intro', db.Text)

    def toDict(self):
        """
        json without md-intro
        """
        return {
            'name': self.name,
            'id': self.id,
            'available': bool(self.available),
            'brief-intro': self.briefIntro,
            'thumbnail': self.thumbnail,
            'rsv-method': self.rsvMethod
        }

    # no value check on dic
    def fromDict(self, dic):
        self.name = dic['name']
        self.id = dic['id']
        self.briefIntro = dic['brief-intro']
        self.thumbnail = dic['thumbnail']
        self.rsvMethod = dic['rsv-method']

    def __repr__(self) -> str:
        return f'Item({self.name}, {self.briefIntro}, {self.id}, {self.mdIntro if len(self.mdIntro) < 30 else (self.mdIntro[:27]+"...")})'

class Reservation(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    itemId   = db.Column('item_id', db.Integer)
    guest    = db.Column(db.Text, nullable=False)
    reason   = db.Column(db.Text, nullable=False)
    method   = db.Column(db.Integer, nullable=False)
    st       = db.Column(db.Integer, nullable=False)
    ed       = db.Column(db.Integer, nullable=False)
    state    = db.Column(db.Integer, nullable=False)
    approver = db.Column(db.Text)
    examRst  = db.Column('exam_rst', db.Text)
    chore    = db.Column(db.Text)


class LongTimeRsv:
    methodValue = 1
    methodMask = 1
    
    morningStartHour   = 8
    morningEndHour     = 12
    morningCode        = 1
    afternoonStartHour = 13
    afternoonEndHour   = 17
    afternoonCode      = 2
    nightStartHour     = 17
    nightEndHour       = 23
    nightCode          = 3

    weekendCode = 4

class FlexTimeRsv:
    methodValue = 2
    methodMask  = 2

# post-binding methods for Reservation
def _getIntervalStr(self: Reservation):
    """
    self中至少有Reservation中的如下属性：
        * method
        * st
        * ed
    return: 可读的时间段信息
    """
    if self.method == LongTimeRsv.methodValue:
        hour = timestamp.getHour(self.st)
        if hour == LongTimeRsv.morningStartHour:
            return f'{timestamp.date(self.st)()} {LongTimeRsv.morningCode}'
        elif hour == LongTimeRsv.afternoonStartHour:
            return f'{timestamp.date(self.st)()} {LongTimeRsv.afternoonCode}'
        elif hour == LongTimeRsv.nightStartHour:
            return f'{timestamp.date(self.st)()} {LongTimeRsv.nightCode}'
        else:
            return f'{timestamp.date(self.st)()} {LongTimeRsv.weekendCode}'

    elif self.method == FlexTimeRsv.methodValue:
        return f'{timestamp.date(self.st)} {timestamp.clock(self.st)}-{timestamp.clock(self.ed)}'
Reservation.getIntervalStr = _getIntervalStr

# TODO: 换个更恰当的名字
def mergeAndBeautify(qryRst: list):
    """
    qryRst中的rsv对象至少包含如下属性：
        * id
        * method
        * st
        * ed
        * chore
    """
    groups = {}
    rsvArr = []
    for e in qryRst:
        e: Reservation
        e.interval = None

        if e.method == FlexTimeRsv.methodValue:
            e.interval = _getIntervalStr(e)
            rsvArr.append(e)
        
        elif e.method == LongTimeRsv.methodValue:
            relation: dict = Json.loads(e.chore)['group-rsv']
            if 'sub-rsvs' in relation:
                e.interval = []
                e.interval.append(_getIntervalStr(e))

                for subRsvIds in relation['sub-rsvs']:
                    if subRsvIds in groups:
                        e.interval.append(_getIntervalStr(groups[subRsvIds]))
                
                groups[e.id] = e
                rsvArr.append(e)
            else:
                if relation['fth-rsv'] in groups:
                    groups[relation['fth-rsv']].interval.append(_getIntervalStr(e))
                else:
                    groups[e.id] = e
    return rsvArr