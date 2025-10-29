from datetime import datetime, timedelta
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SoftDeleteMixin:
    is_deleted = db.Column(db.Boolean, default=False)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    level = db.Column(db.String(32), nullable=False, default="operator")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(SoftDeleteMixin, TimestampMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    sort = db.Column(db.Integer, default=0)

    parent = db.relationship("Category", remote_side=[id], backref="children")


class Grade(SoftDeleteMixin, TimestampMixin, db.Model):
    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)


class Class(SoftDeleteMixin, TimestampMixin, db.Model):
    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), nullable=False)

    grade = db.relationship("Grade", backref="classes")


class Book(SoftDeleteMixin, TimestampMixin, db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    isbn = db.Column(db.String(32), unique=True, nullable=False)
    position = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    category = db.relationship("Category", backref="books")
    amount = db.Column(db.Integer, default=1)
    lend_amount = db.Column(db.Integer, default=0)
    price = db.Column(db.Numeric(10, 2), default=0)
    publisher = db.Column(db.String(255))
    author = db.Column(db.String(255))
    version = db.Column(db.String(255))
    source = db.Column(db.String(255))
    index_id = db.Column(db.String(255))
    pages = db.Column(db.Integer)
    images = db.Column(db.String(500))
    summary = db.Column(db.String(500))
    input_num = db.Column(db.Integer)
    remark = db.Column(db.String(2000))

    def available_amount(self) -> int:
        return max(self.amount - self.lend_amount, 0)


class Reader(SoftDeleteMixin, TimestampMixin, db.Model):
    __tablename__ = "readers"

    id = db.Column(db.Integer, primary_key=True)
    card_no = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    sex = db.Column(db.String(16))
    phone = db.Column(db.String(32))
    cert_type = db.Column(db.String(255))
    cert_no = db.Column(db.String(255))
    expire_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=365))
    group = db.Column(db.String(255))
    status = db.Column(db.String(32), default="active")
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"))

    reader_class = db.relationship("Class", backref="readers")


class Lend(SoftDeleteMixin, TimestampMixin, db.Model):
    __tablename__ = "lends"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    reader_id = db.Column(db.Integer, db.ForeignKey("readers.id"), nullable=False)
    amount = db.Column(db.Integer, default=1)
    due_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(32), default="lent")
    comment = db.Column(db.Text)

    book = db.relationship("Book", backref="lends")
    reader = db.relationship("Reader", backref="lends")

    def mark_returned(self) -> None:
        self.status = "returned"
        self.updated_at = datetime.utcnow()


class ReturnRecord(SoftDeleteMixin, TimestampMixin, db.Model):
    __tablename__ = "returns"

    id = db.Column(db.Integer, primary_key=True)
    lend_id = db.Column(db.Integer, db.ForeignKey("lends.id"), nullable=False)
    amount = db.Column(db.Integer, default=1)
    comment = db.Column(db.Text)

    lend = db.relationship("Lend", backref="returns")


def ensure_seed_data(username: str = "admin", password: str = "admin123") -> None:
    if not User.query.filter_by(username=username).first():
        user = User(username=username, level="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def find_book_by_isbn(isbn: str) -> Optional[Book]:
    return Book.query.filter_by(isbn=isbn, is_deleted=False).first()


def find_reader_by_card(card_no: str) -> Optional[Reader]:
    return Reader.query.filter_by(card_no=card_no, is_deleted=False).first()
