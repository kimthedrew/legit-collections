from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, FloatField, FileField, SelectField, DecimalField
from wtforms.validators import DataRequired, Email, Length, ValidationError, Optional, NumberRange, Regexp, InputRequired
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