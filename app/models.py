from app import db
from datetime import datetime

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    bootcamp_id = db.Column(db.String(50), db.ForeignKey('bootcamps.id'))
    status = db.Column(db.String(20), default='지원완료')
    considering_reason = db.Column(db.Text, nullable=True)
    last_contact_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    batch_number = db.Column(db.Integer)

    __table_args__ = (
        db.Index('idx_student_phone_batch', 'phone', 'batch_number', unique=True,
                postgresql_where=db.text("phone != ''")),
    )

class Bootcamp(db.Model):
    __tablename__ = 'bootcamps'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    batch_number = db.Column(db.Integer)
    recruitment_start_date = db.Column(db.Date)
    recruitment_end_date = db.Column(db.Date)
    students = db.relationship('Student', backref='bootcamp', lazy=True) 