from flask_login import UserMixin
from extensions import db
from flask_bcrypt import Bcrypt
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import select, func
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
    admin_type = db.Column(db.String(20), default='user')  # 'user', 'limited_admin', 'super_admin'
    product_limit = db.Column(db.Integer, default=0)  # 0 = unlimited, 3 = limited
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
    
    def is_super_admin(self):
        """Check if user is a super admin"""
        try:
            return self.is_admin and getattr(self, 'admin_type', 'user') == 'super_admin'
        except:
            return self.is_admin  # Fallback for backward compatibility
    
    def is_limited_admin(self):
        """Check if user is a limited admin"""
        try:
            return self.is_admin and getattr(self, 'admin_type', 'user') == 'limited_admin'
        except:
            return False
    
    def can_add_product(self):
        """Check if user can add more products"""
        try:
            if self.is_super_admin():
                return True
            elif self.is_limited_admin():
                # Count products created by this user
                from sqlalchemy import func
                product_count = db.session.query(func.count(Shoe.id)).filter_by(created_by=self.id).scalar()
                limit = getattr(self, 'product_limit', 0)
                return product_count < limit
            return False
        except:
            return self.is_admin  # Fallback for backward compatibility
    
    def get_product_count(self):
        """Get the number of products created by this user"""
        try:
            from sqlalchemy import func
            return db.session.query(func.count(Shoe.id)).filter_by(created_by=self.id).scalar() or 0
        except:
            return 0

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
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Track who created the shoe
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to sizes
    sizes = db.relationship('ShoeSize', backref='shoe', cascade='all, delete-orphan', lazy=True)
    @hybrid_property
    def total_stock(self):
        """Calculate total stock by summing quantities of all sizes"""
        return sum(size.quantity for size in self.sizes)
    
    @total_stock.expression
    def total_stock(cls):
        """Database-level expression for efficient querying"""
        return (
            select(func.sum(ShoeSize.quantity))
            .where(ShoeSize.shoe_id == cls.id)
            .label('total_stock')
        )
    
class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shoe_id = db.Column(db.Integer, db.ForeignKey('shoes.id'), nullable=True)
    size = db.Column(db.String(10), nullable=False)
    
    # Payment fields
    payment_method = db.Column(db.String(20), default='Cash')  # M-Pesa, Card, Cash, Bank
    payment_status = db.Column(db.String(20), default='Pending')  # Pending, Completed, Failed, Cancelled
    payment_transaction_id = db.Column(db.String(200))  # Transaction ID from payment gateway
    payment_reference = db.Column(db.String(100))  # Our internal reference
    amount = db.Column(db.Float)  # Total amount paid
    
    # Legacy fields (keeping for backward compatibility)
    payment_code = db.Column(db.String(50))
    phone_number = db.Column(db.String(20))
    
    # Order status
    status = db.Column(db.String(20), default='Pending')  # Pending, Processing, Shipped, Delivered, Cancelled
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