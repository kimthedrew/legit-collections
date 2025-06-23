from flask_login import UserMixin
from extensions import db
from flask_bcrypt import Bcrypt
from datetime import datetime
# from flask_session import SqlAlchemySessionInterface

bcrypt = Bcrypt()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    # orders = db.relationship('Order', backref='user', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def verify_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class Shoe(db.Model):
    __tablename__ = 'shoes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(300))
    # @property
    # def formatted_price(self):
    #     return f"${self.price:.2f}" if self.price else "N/A"
    # Remove stock field since we're tracking by size now
    category = db.Column(db.String(50), default='Shoes')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to sizes
    sizes = db.relationship('ShoeSize', backref='shoe', cascade='all, delete-orphan', lazy=True)
    # @hybrid_property
    # def total_stock(self):
    #     return sum(size.quantity for size in self.sizes)

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shoe_id = db.Column(db.Integer, db.ForeignKey('shoes.id'), nullable=True)
    size = db.Column(db.String(10), nullable=False)  # Add this
    payment_code = db.Column(db.String(50))
    phone_number = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='orders')
    shoe = db.relationship('Shoe', backref='orders')


class ShoeSize(db.Model):
    __tablename__ = 'shoe_sizes'
    
    id = db.Column(db.Integer, primary_key=True)
    shoe_id = db.Column(db.Integer, db.ForeignKey('shoes.id'), nullable=False)
    size = db.Column(db.String(10), nullable=False)  # e.g., "9", "10", "10.5"
    quantity = db.Column(db.Integer, default=0)
    
    # shoe = db.relationship('Shoe', backref='sizes')

class Session(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.String(255), primary_key=True)
    data = db.Column(db.LargeBinary)
    expiry = db.Column(db.DateTime)