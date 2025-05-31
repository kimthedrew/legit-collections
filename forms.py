from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, FloatField, FileField, SelectField
from wtforms.validators import DataRequired, Email, Length, ValidationError, Optional, NumberRange, Regexp
from models import User
from flask_wtf.file import FileAllowed
from flask import request

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

class ShoeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    price = FloatField('Price', validators=[
        DataRequired(), 
        NumberRange(min=0.01, message="Price must be greater than 0")
    ])
    description = TextAreaField('Description')
    image = FileField('Product Image', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')
    ])
    image_url = StringField('Image URL', validators=[Optional()])
    category = StringField('Category', validators=[DataRequired()])

    # Add custom validation for new products
    def validate_image(self, field):
        # Only require image for new products
        if request.endpoint == 'add_shoe' and not field.data and not self.image_url.data:
            raise ValidationError('Either image file or URL is required')

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