from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref

db = SQLAlchemy()


class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(255), nullable=True)
    model = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=True)