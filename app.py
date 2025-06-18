from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from extensions import db
from flask_migrate import Migrate
from flask_caching import Cache
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import re
import logging
import redis
from flask_session import Session

# Load environment variables
load_dotenv()

# Initialize extensions
bcrypt = Bcrypt()
login_manager = LoginManager()
migrate = Migrate()
cache = Cache()

def create_app():
    app = Flask(__name__)

    # Get database URL and handle PostgreSQL compatibility
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Configure application
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'your-secret-key-here'),
        SQLALCHEMY_DATABASE_URI=database_url or 'sqlite:///site.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif', 'webp'},
        CACHE_TYPE='SimpleCache',
        CACHE_DEFAULT_TIMEOUT=300,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_TYPE='redis' if os.getenv('REDIS_URL') else 'filesystem',
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True
    )

    # Configure Redis if available
    redis_url = os.getenv('REDIS_URL')
    if redis_url:
        app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    else:
        # Fallback to filesystem sessions in development
        app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

    # Backblaze B2 configuration
    app.config['B2_KEY_ID'] = os.getenv('B2_KEY_ID')
    app.config['B2_APP_KEY'] = os.getenv('B2_APP_KEY')
    app.config['B2_BUCKET_NAME'] = os.getenv('B2_BUCKET_NAME')
    app.config['B2_BASE_URL'] = f"https://s3.us-east-005.backblazeb2.com/file/{app.config.get('B2_BUCKET_NAME', '')}/"

    # Initialize extensions with app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    
    # Initialize Flask-Session after setting config
    Session(app)
    
    login_manager.login_view = 'login'

    # Configure logging
    if app.config.get('ENV') == 'production':
        logging.basicConfig(level=logging.INFO)
        app.logger.addHandler(logging.StreamHandler())

    # Import models after app and db are initialized
    with app.app_context():
        from models import User, Shoe, Order, ShoeSize
        db.create_all()

    return app

app = create_app()
csrf = CSRFProtect(app)

# Import forms and routes after app creation
from forms import RegistrationForm, LoginForm, PaymentForm, ShoeForm, ShoeSizeForm, AddToCartForm
# Import models after app creation
from models import User, Shoe, Order, ShoeSize

from b2_helpers import upload_to_b2

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    if '.' not in filename:
        return False
        
    ext = filename.rsplit('.', 1)[1].lower()
    allowed = ext in app.config['ALLOWED_EXTENSIONS']
    
    if not allowed:
        app.logger.warning(f"Invalid file extension: {ext}. Allowed: {app.config['ALLOWED_EXTENSIONS']}")
        
    return allowed

def flash_errors(form):
    """Flash form validation errors to the user."""
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{field.replace('_', ' ').title()}: {error}", 'danger')
            app.logger.error(f"Form error in {field}: {error}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
@cache.cached(timeout=300)
def index():
    page = request.args.get('page', 1, type=int)
    # Eager load sizes to avoid N+1 query problem
    shoes = Shoe.query.options(db.joinedload(Shoe.sizes))\
                     .order_by(Shoe.id.desc())\
                     .paginate(page=page, per_page=9)
    
    # Create a form instance for each shoe
    for shoe in shoes.items:
        shoe.total_stock = sum(size.quantity for size in shoe.sizes)
        
        # Format price
        if isinstance(shoe.price, (float, int)):
            shoe.formatted_price = f"Ksh{shoe.price:.2f}"
        else:
            shoe.formatted_price = f"Ksh{shoe.price}"
            
        # Create a form instance for the shoe
        shoe.form = AddToCartForm()
        
        # Populate size choices
        available_sizes = [s for s in shoe.sizes if s.quantity > 0]
        shoe.form.size.choices = [(size.size, size.size) for size in available_sizes]
    
    return render_template('index.html', shoes=shoes)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            password=form.password.data,
            name=form.name.data,
            address=form.address.data
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.verify_password(form.password.data):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin'))
            return redirect(url_for('index'))
        flash('Invalid email or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET'])
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    form = ShoeForm()
    orders = Order.query.all()
    shoes = Shoe.query.all()
    size_form = ShoeSizeForm()
    return render_template('admin.html', orders=orders, shoes=shoes, form=form, size_form=size_form)

@app.route('/admin/add_shoe', methods=['POST'])
@login_required
def add_shoe():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    form = ShoeForm()
    
    if form.validate_on_submit():
        try:
            image_url = None
            
            # Handle B2 upload
            if form.image.data:
                file = form.image.data
                if file.filename == '':
                    flash('No selected file', 'danger')
                    return redirect(url_for('admin'))
                
                if not allowed_file(file.filename):
                    flash(f'Invalid file type. Allowed types: {", ".join(app.config["ALLOWED_EXTENSIONS"])}', 'danger')
                    return redirect(url_for('admin'))
                
                filename = secure_filename(file.filename)
                image_url = upload_to_b2(file, filename)
                
                if not image_url:
                    flash('B2 upload failed', 'danger')
                    return redirect(url_for('admin'))
                    
            elif form.image_url.data:
                image_url = form.image_url.data
                
            if not image_url:
                flash('Image source required', 'danger')
                return redirect(url_for('admin'))
            
            # Create shoe
            new_shoe = Shoe(
                name=form.name.data,
                price=form.price.data,
                description=form.description.data,
                image_url=image_url,
                category=form.category.data
            )
            
            db.session.add(new_shoe)
            db.session.commit()
            cache.clear()
            flash('Shoe added successfully! Now add sizes', 'success')
            return redirect(url_for('manage_shoe_sizes', shoe_id=new_shoe.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving shoe: {str(e)}', 'danger')
            app.logger.error(f'Error in add_shoe: {str(e)}')
    else:
        flash_errors(form)
    
    return redirect(url_for('admin'))


@app.route('/admin/shoe/<int:shoe_id>/sizes', methods=['GET', 'POST'])
@login_required
def manage_shoe_sizes(shoe_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    shoe = Shoe.query.get_or_404(shoe_id)
    form = ShoeSizeForm()
    
    if form.validate_on_submit():
        size = ShoeSize(
            shoe_id=shoe_id,
            size=form.size.data,
            quantity=form.quantity.data
        )
        db.session.add(size)
        db.session.commit()
        flash('Size added successfully!', 'success')
        return redirect(url_for('manage_shoe_sizes', shoe_id=shoe_id))
    
    return render_template('manage_sizes.html', shoe=shoe, form=form)

@app.route('/admin/delete_size/<int:size_id>', methods=['POST'])
@login_required
def delete_size(size_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    size = ShoeSize.query.get_or_404(size_id)
    shoe_id = size.shoe_id
    db.session.delete(size)
    db.session.commit()
    flash('Size deleted successfully!', 'success')
    return redirect(url_for('manage_shoe_sizes', shoe_id=shoe_id))

@app.route('/admin/update_shoe/<int:shoe_id>', methods=['POST'])
@login_required
def update_shoe(shoe_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    shoe = Shoe.query.get_or_404(shoe_id)
    form = ShoeForm(obj=shoe)  # Pre-populate form with existing data
    
    if form.validate_on_submit():
        try:
            # Update fields
            shoe.name = form.name.data
            shoe.price = form.price.data
            shoe.description = form.description.data
            shoe.category = form.category.data
            
            # Handle image updates
            new_image_url = None
            
            if form.image.data:
                file = form.image.data
                if file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    new_image_url = upload_to_b2(file, filename)
                    
            if not new_image_url and form.image_url.data:
                new_image_url = form.image_url.data
                
            if new_image_url:
                shoe.image_url = new_image_url
            
            db.session.commit()
            cache.clear()
            flash('Shoe updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating shoe: {str(e)}', 'danger')
    else:
        flash_errors(form)
    
    return redirect(url_for('admin'))


# Add delete shoe route
@app.route('/admin/delete_shoe/<int:shoe_id>', methods=['POST'])
@login_required
def delete_shoe(shoe_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    shoe = Shoe.query.get_or_404(shoe_id)
    db.session.delete(shoe)
    db.session.commit()
    flash('Shoe deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/verify_payment/<int:order_id>', methods=['POST'])
@login_required
def verify_payment(order_id):
    if current_user.is_admin:
        order = Order.query.get(order_id)
        admin_code = request.form.get('admin_code')
        
        if order.payment_code == admin_code:
            order.status = 'Verified'
            db.session.commit()
            flash('Payment verified! Order can be shipped', 'success')
        else:
            flash('Payment codes do not match', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/add_to_cart/<int:shoe_id>', methods=['POST'])
@login_required
def add_to_cart(shoe_id):
    shoe = Shoe.query.get_or_404(shoe_id)
    
    # Get size from form data
    selected_size = request.form.get('size')
    
    if not selected_size:
        flash('Please select a size', 'danger')
        return redirect(url_for('index'))
    
    # Find the size inventory
    size_inv = next((s for s in shoe.sizes if s.size == selected_size), None)
    
    if not size_inv or size_inv.quantity < 1:
        flash('This size is currently out of stock', 'danger')
        return redirect(url_for('index'))
    
    cart = session.get('cart', [])
    
    # Add item with size
    cart.append({
        'shoe_id': shoe_id,
        'size': selected_size
    })
    
    session['cart'] = cart
    session.modified = True  # Explicitly mark session as modified
    flash('Item added to cart', 'success')
    return redirect(url_for('index'))


@app.route('/remove_from_cart/<int:index>', methods=['POST'])
@login_required
def remove_from_cart(index):
    cart = session.get('cart', [])
    
    if 0 <= index < len(cart):
        item = cart.pop(index)
        session['cart'] = cart
        session.modified = True
        
        # Restore stock if needed (only if item is a dictionary)
        if isinstance(item, dict):
            size_inv = ShoeSize.query.filter_by(
                shoe_id=item.get('shoe_id'),
                size=item.get('size')
            ).first()
            
            if size_inv:
                size_inv.quantity += 1
                db.session.commit()
            
        flash('Item removed from cart', 'success')
    return redirect(url_for('view_cart'))

@app.route('/cart')
@login_required
def view_cart():
    cart_items = []
    total = 0
    
    if 'cart' in session:
        for item in session['cart']:
            # Ensure item is a dictionary
            if isinstance(item, dict):
                shoe = Shoe.query.get(item.get('shoe_id'))
                if shoe:
                    cart_items.append({
                        'shoe': shoe,
                        'size': item.get('size', 'N/A'),
                        'price': shoe.price
                    })
                    total += shoe.price
            # Handle legacy format (shoe ID as integer)
            elif isinstance(item, int):
                shoe = Shoe.query.get(item)
                if shoe:
                    cart_items.append({
                        'shoe': shoe,
                        'size': 'Size not specified',
                        'price': shoe.price
                    })
                    total += shoe.price
    
    form = PaymentForm()
    return render_template('cart.html', cart=cart_items, total=total, form=form)

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    form = PaymentForm()
    cart = session.get('cart', [])
    cart_items = []
    total = 0
    
    # First pass: validate stock
    for item in cart:
        shoe_id = item['shoe_id'] if isinstance(item, dict) else item
        shoe = Shoe.query.get(shoe_id)
        
        if not shoe:
            continue
            
        # Get size if available
        size = item['size'] if isinstance(item, dict) and 'size' in item else 'Size not specified'
        
        # For dictionary items, validate size stock
        if isinstance(item, dict):
            size_inv = next((s for s in shoe.sizes if s.size == item.get('size')), None)
            
            if not size_inv or size_inv.quantity < 1:
                flash(f"Size {item.get('size', 'unknown')} of {shoe.name} is no longer available", 'danger')
                return redirect(url_for('view_cart'))
        
        cart_items.append({
            'shoe': shoe,
            'size': size,
            'price': shoe.price
        })
        total += shoe.price
    
    if form.validate_on_submit():
        try:
            for item in cart_items:
                shoe = item['shoe']
                size = item['size']
                
                # Only reduce stock if we have a specific size
                if size != 'Size not specified':
                    # Find the size inventory
                    size_inv = next((s for s in shoe.sizes if s.size == size), None)
                    
                    if not size_inv or size_inv.quantity < 1:
                        raise ValueError(f"Size {size} of {shoe.name} is out of stock")
                    
                    # Reduce stock
                    size_inv.quantity -= 1
                
                # Create order
                order = Order(
                    user_id=current_user.id,
                    shoe_id=shoe.id,
                    size=size,
                    payment_code=form.payment_code.data,
                    phone_number=form.phone_number.data,
                    status='Pending'
                )
                db.session.add(order)
            
            db.session.commit()
            session.pop('cart', None)
            flash('Payment successful! Your order is being processed', 'success')
            return redirect(url_for('index'))
        
        except Exception as e:
            db.session.rollback()
            flash(str(e), 'danger')
    
    return render_template('checkout.html', form=form, cart=cart_items, total=total)

@app.route('/orders')
@login_required
def user_orders():
    orders = Order.query.filter_by(user_id=current_user.id) \
                       .order_by(Order.created_at.desc()) \
                       .all()
    return render_template('orders.html', orders=orders)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    results = Shoe.query.filter(
        db.or_(
            Shoe.name.ilike(f'%{query}%'),
            Shoe.description.ilike(f'%{query}%')
        )
    ).paginate(page=page, per_page=9)
    
    return render_template('search.html', results=results, query=query)

@app.route('/migrate_cart')
@login_required
def migrate_cart():
    if 'cart' in session:
        new_cart = []
        for item in session['cart']:
            if isinstance(item, int):
                new_cart.append({
                    'shoe_id': item,
                    'size': 'Size not specified'
                })
            else:
                new_cart.append(item)
        session['cart'] = new_cart
        flash('Cart migrated to new format', 'success')
    return redirect(url_for('view_cart'))

@app.route('/test_b2')
def test_b2():
    try:
        # Create a test file
        from io import BytesIO
        test_file = BytesIO(b"This is a Backblaze test file")
        test_file.filename = "test_file.txt"
        test_file.content_type = "text/plain"
        
        # Attempt upload
        url = upload_to_b2(test_file, "test_file.txt")
        
        if url:
            # Verify URL accessibility
            try:
                response = requests.head(url)
                if response.status_code == 200:
                    return jsonify({
                        "status": "success",
                        "url": url,
                        "message": "Backblaze upload and URL verification successful"
                    })
                else:
                    return jsonify({
                        "status": "warning",
                        "url": url,
                        "message": f"Upload succeeded but URL returned status {response.status_code}"
                    })
            except Exception as e:
                return jsonify({
                    "status": "warning",
                    "url": url,
                    "message": f"Upload succeeded but URL verification failed: {str(e)}"
                })
        else:
            return jsonify({
                "status": "error",
                "message": "Upload function returned None. Check server logs for details."
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Test failed: {str(e)}"
        }), 500
# Add this to app.py
@app.template_filter('float')
def format_float(value, decimals=2):
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return value

if __name__ == '__main__':
    # with app.app_context():
    #     # Create database tables if they don't exist
    #     db.create_all()
    
    # Determine if we're in production
    is_production = os.getenv('ENV') == 'production'
    
    # Run the app
    if is_production:
        # For production, use a production WSGI server
        from waitress import serve
        serve(app, host="0.0.0.0", port=8080)
    else:
        # For development, use Flask's built-in server
        app.config['GUNICORN_TIMEOUT'] = 120
        app.run(debug=True)

# Temporary admin creation routes (comment out after use)
# @app.route('/create_admin')
# def create_admin():
#     if User.query.filter_by(is_admin=True).count() == 0:
#         admin = User(
#             email="kimutai3002@gmail.com",
#             password=bcrypt.generate_password_hash("123498").decode('utf-8'),
#             name="Legit collections",
#             address="mine",
#             is_admin=True
#         )
#         db.session.add(admin)
#         db.session.commit()
#         return "Admin created!"
#     return "Admin already exists"

# # @app.route('/reset_admin_password')
# def reset_admin_password():
#     admin = User.query.filter_by(is_admin=True).first()
#     if admin:
#         new_password = "your_new_secure_password"
#         admin.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
#         db.session.commit()
#         return f"Admin password reset for {admin.email}"
#     return "No admin user found"