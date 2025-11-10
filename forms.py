from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, FloatField, FileField, SelectField, DecimalField
from wtforms.validators import DataRequired, Length, ValidationError, Optional, NumberRange, Regexp, InputRequired
from models import User
from flask_wtf.file import FileAllowed
from flask import request

# Try to import Email validator, fallback to basic validation if not available
try:
    from wtforms.validators import Email
    EMAIL_VALIDATOR_AVAILABLE = True
except ImportError:
    EMAIL_VALIDATOR_AVAILABLE = False
    print("Warning: email-validator not available, using basic email validation")
    
    # Create a basic email validator as fallback
    class Email:
        def __init__(self, message=None):
            self.message = message or 'Invalid email address.'
        
        def __call__(self, form, field):
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, field.data):
                raise ValidationError(self.message)

class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    address = StringField('Address')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class PaymentForm(FlaskForm):
    phone_number = StringField('Phone Number', validators=[
        DataRequired(), 
        Length(min=10, max=13),
        Regexp(r'^\+?[0-9]+$', message="Invalid phone number format")
    ])
    payment_code = StringField('Payment Code', validators=[
        DataRequired(), 
        Length(min=6, max=12),
        Regexp(r'^[A-Z0-9]+$', message="Invalid payment code format")
    ])

class GuestCheckoutForm(FlaskForm):
    """Form for guest checkout with all required customer information"""
    # Customer Information
    guest_name = StringField('Full Name', validators=[
        DataRequired(), 
        Length(min=2, max=100, message="Name must be between 2 and 100 characters")
    ])
    guest_email = StringField('Email Address', validators=[
        DataRequired(), 
        Email(message="Please enter a valid email address")
    ])
    guest_phone = StringField('Phone Number', validators=[
        DataRequired(), 
        Length(min=10, max=15, message="Phone number must be between 10 and 15 digits"),
        Regexp(r'^\+?[0-9]+$', message="Invalid phone number format")
    ])
    
    # Delivery Information
    delivery_address = TextAreaField('Delivery Address', validators=[
        DataRequired(), 
        Length(min=10, max=500, message="Please provide a complete delivery address")
    ])
    delivery_city = StringField('City/Town', validators=[
        DataRequired(), 
        Length(min=2, max=100, message="Please enter your city or town")
    ])
    delivery_instructions = TextAreaField('Delivery Instructions (Optional)', validators=[
        Optional(), 
        Length(max=500)
    ])
    
    # Payment fields (for manual M-Pesa)
    payment_code = StringField('Payment Code', validators=[
        Optional(),  # Only required for manual M-Pesa
        Length(min=6, max=12),
        Regexp(r'^[A-Z0-9]+$', message="Invalid payment code format")
    ])

class ShoeForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired()])
    price = DecimalField('Price', validators=[InputRequired()])
    description = TextAreaField('Description', validators=[InputRequired()])
    category = StringField('Category', validators=[InputRequired()])
    image = FileField('Upload Image', validators=[Optional()])
    image_url = StringField('Or Image URL', validators=[Optional()])
    
    def validate(self, extra_validators=None, **kwargs):
        # Custom validation to ensure at least one image source
        if not super().validate(extra_validators=extra_validators, **kwargs):
            return False
            
        if not self.image.data and not self.image_url.data:
            self.image_url.errors.append('Either upload an image or provide an image URL')
            return False
            
        return True

class ShoeSizeForm(FlaskForm):
    size = StringField('Size', validators=[
        DataRequired(),
        Regexp(r'^\d+(\.\d{1,2})?$', message="Invalid size format (e.g., 9 or 9.5)")
    ])
    quantity = IntegerField('Quantity', validators=[
        DataRequired(),
        NumberRange(min=0, message="Quantity cannot be negative")
    ])

class AddToCartForm(FlaskForm):
    size = SelectField('Size', coerce=str, validators=[DataRequired()])