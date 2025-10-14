from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from extensions import db
from flask_migrate import Migrate
from flask_caching import Cache
from datetime import timedelta
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import re
import logging
# Import flask_session conditionally
try:
    from flask_session import Session
    SESSION_AVAILABLE = True
except ImportError:
    SESSION_AVAILABLE = False

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
        B2_ENDPOINT_URL=os.getenv('B2_ENDPOINT_URL', 'https://s3.us-east-005.backblazeb2.com'),
        B2_REGION_NAME=os.getenv('B2_REGION_NAME', 'us-east-005'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif', 'webp'},
        CACHE_TYPE='SimpleCache',
        CACHE_DEFAULT_TIMEOUT=300,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_TYPE='redis' if os.getenv('REDIS_URL') else 'filesystem',
        SESSION_PERMANENT=True,
        SESSION_USE_SIGNER=True,
        PERMANENT_SESSION_LIFETIME=timedelta(days=7)
    )

    # Configure Redis if available
    redis_url = os.getenv('REDIS_URL')
    if redis_url:
        try:
            import redis
            app.config['SESSION_REDIS'] = redis.from_url(redis_url)
        except ImportError:
            # Fallback to filesystem sessions if redis is not available
            app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
            os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    else:
        # Fallback to filesystem sessions in development
        app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

    # Backblaze B2 configuration
    app.config['B2_KEY_ID'] = os.getenv('B2_KEY_ID')
    app.config['B2_APP_KEY'] = os.getenv('B2_APP_KEY')
    app.config['B2_BUCKET_NAME'] = os.getenv('B2_BUCKET_NAME')
    app.config['B2_BASE_URL'] = f"https://s3.us-east-005.backblazeb2.com/{app.config.get('B2_BUCKET_NAME', '')}/"

    # Initialize extensions with app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    
    # Initialize Flask-Session after setting config (if available)
    if SESSION_AVAILABLE:
        Session(app)
    
    login_manager.login_view = 'login'

    # Configure logging
    if app.config.get('ENV') == 'production':
        logging.basicConfig(level=logging.INFO)
        app.logger.addHandler(logging.StreamHandler())

    # Import models after app and db are initialized
    with app.app_context():
        from models import User, Shoe, Order, ShoeSize, Wishlist, ProductImage
        db.create_all()

    return app

app = create_app()
csrf = CSRFProtect(app)

# Import forms and routes after app creation
from forms import RegistrationForm, LoginForm, PaymentForm, ShoeForm, ShoeSizeForm, AddToCartForm
# Import models after app creation
from models import User, Shoe, Order, ShoeSize

# Import b2_helpers conditionally
try:
    from b2_helpers import upload_to_b2
    B2_AVAILABLE = True
except ImportError:
    B2_AVAILABLE = False
    def upload_to_b2(file, filename):
        return None  # Fallback function

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

@app.route('/')
def index():
    from models import Wishlist
    from sqlalchemy import func
    
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'newest')
    
    # Get filter parameters
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    category = request.args.get('category', '')
    availability = request.args.get('availability', '')
    
    # Build query with filters
    query = Shoe.query.options(db.joinedload(Shoe.sizes))
    
    # Apply price filters
    if min_price is not None:
        query = query.filter(Shoe.price >= min_price)
    if max_price is not None:
        query = query.filter(Shoe.price <= max_price)
    
    # Apply category filter
    if category:
        query = query.filter(Shoe.category == category)
    
    # Apply availability filter
    if availability == 'in_stock':
        # Only show products with at least one size in stock
        query = query.join(ShoeSize).filter(ShoeSize.quantity > 0)
    elif availability == 'out_of_stock':
        # Products with no sizes or all sizes out of stock
        query = query.outerjoin(ShoeSize).group_by(Shoe.id).having(
            func.coalesce(func.sum(ShoeSize.quantity), 0) == 0
        )
    
    # Apply sorting
    if sort_by == 'price_low':
        query = query.order_by(Shoe.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Shoe.price.desc())
    elif sort_by == 'name_az':
        query = query.order_by(Shoe.name.asc())
    elif sort_by == 'name_za':
        query = query.order_by(Shoe.name.desc())
    else:  # newest (default)
        query = query.order_by(Shoe.id.desc())
    
    shoes = query.paginate(page=page, per_page=9)
    
    # Get user's wishlist if logged in
    wishlist_ids = []
    if current_user.is_authenticated:
        wishlist_items = Wishlist.query.filter_by(user_id=current_user.id).all()
        wishlist_ids = [item.shoe_id for item in wishlist_items]
    
    forms_dict = {}
    for shoe in shoes.items:  # Note: use shoes.items for paginated results
        form = AddToCartForm()
        form.size.choices = [(str(size.size), str(size.size)) for size in shoe.sizes]
        forms_dict[shoe.id] = form
    
    # Get related/recommended products (different from current page items)
    displayed_ids = [shoe.id for shoe in shoes.items]
    related_products = Shoe.query.options(db.joinedload(Shoe.sizes))\
                                 .filter(Shoe.id.notin_(displayed_ids) if displayed_ids else True)\
                                 .order_by(func.random())\
                                 .limit(3)\
                                 .all()
    
    return render_template('index.html', shoes=shoes, forms_dict=forms_dict, 
                         wishlist_ids=wishlist_ids, related_products=related_products)

# @app.route('/')
# def index():
#     page = request.args.get('page', 1, type=int)
#     cache_key = f"index_page_{page}"
    
#     if cache.get(cache_key):
#         return cache.get(cache_key)
    
#     shoes = Shoe.query.options(db.joinedload(Shoe.sizes))\
#                      .order_by(Shoe.id.desc())\
#                      .paginate(page=page, per_page=9)
    
#     # Create forms dictionary
#     forms_dict = {}
    
#     for shoe in shoes.items:
#         shoe.total_stock = sum(size.quantity for size in shoe.sizes)
        
#         # Format price
#         if isinstance(shoe.price, (float, int)):
#             shoe.formatted_price = f"Ksh{shoe.price:.2f}"
#         else:
#             shoe.formatted_price = f"Ksh{shoe.price}"
            
#         # Create form instance for this shoe
#         forms_dict[shoe.id] = AddToCartForm()
    
#     rendered = render_template('index.html', shoes=shoes, forms_dict=forms_dict)
#     cache.set(cache_key, rendered, timeout=300)
    return rendered

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

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     form = LoginForm()
#     if form.validate_on_submit():
#         user = User.query.filter_by(email=form.email.data).first()
#         if user and user.verify_password(form.password.data):
#             login_user(user)
#             if user.is_admin:
#                 return redirect(url_for('admin'))
#             return redirect(url_for('index'))
#         flash('Invalid email or password', 'danger')
#     return render_template('login.html', form=form)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    form = LoginForm()
    next_url = request.args.get('next', url_for('index'))
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.verify_password(form.password.data):
            # Login user and commit session
            login_user(user, remember=True)
            session.modified = True
            
            # Handle pending cart items
            if 'pending_cart_item' in session:
                item = session.pop('pending_cart_item')
                try:
                    shoe = Shoe.query.get(item.get('shoe_id'))
                    if shoe:
                        size_inv = next((s for s in shoe.sizes 
                                       if s.size == item.get('size') and s.quantity > 0), None)
                        if size_inv:
                            cart = session.get('cart', [])
                            cart.append(item)
                            session['cart'] = cart
                            flash('Item added to cart!', 'success')
                        else:
                            flash('Selected size no longer available', 'warning')
                except Exception as e:
                    app.logger.error(f"Pending item error: {str(e)}")
            
            return redirect(next_url)
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html', form=form, next=next_url)

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
    
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from models import Wishlist
    
    form = ShoeForm()
    size_form = ShoeSizeForm()
    
    # Filter data based on admin type
    try:
        if current_user.is_super_admin():
            # Super admin sees all orders and shoes
            orders = Order.query.order_by(Order.created_at.desc()).all()
            shoes = Shoe.query.all()
            admin_type = 'super_admin'
        elif current_user.is_limited_admin():
            # Limited admin sees only their own products and related orders
            shoes = Shoe.query.filter_by(created_by=current_user.id).all()
            # Get orders for shoes created by this admin
            shoe_ids = [shoe.id for shoe in shoes]
            orders = Order.query.filter(Order.shoe_id.in_(shoe_ids)).order_by(Order.created_at.desc()).all() if shoe_ids else []
            admin_type = 'limited_admin'
        else:
            # Fallback for regular admin (backward compatibility)
            orders = Order.query.order_by(Order.created_at.desc()).all()
            shoes = Shoe.query.all()
            admin_type = 'admin'
    except Exception as e:
        # Fallback if there are any issues with the new fields
        app.logger.error(f"Admin type check failed: {str(e)}")
        orders = Order.query.order_by(Order.created_at.desc()).all()
        shoes = Shoe.query.all()
        admin_type = 'admin'
    
    # Calculate Analytics
    analytics = {}
    
    # Total Revenue (from completed payments)
    total_revenue = db.session.query(func.sum(Order.amount))\
                             .filter(Order.payment_status == 'Completed')\
                             .scalar() or 0
    
    # Total Orders
    total_orders = len(orders)
    
    # Pending Orders (need verification)
    pending_orders = len([o for o in orders if o.payment_status == 'Pending'])
    
    # Completed Orders
    completed_orders = len([o for o in orders if o.payment_status == 'Completed'])
    
    # Total Products
    total_products = len(shoes)
    
    # Low Stock Products (total stock < 5)
    low_stock_products = [shoe for shoe in shoes if shoe.total_stock < 5 and shoe.total_stock > 0]
    
    # Out of Stock Products
    out_of_stock_products = [shoe for shoe in shoes if shoe.total_stock == 0]
    
    # Total Customers (unique users who placed orders)
    total_customers = db.session.query(func.count(func.distinct(Order.user_id))).scalar() or 0
    
    # Revenue by payment method
    revenue_by_method = db.session.query(
        Order.payment_method,
        func.sum(Order.amount)
    ).filter(Order.payment_status == 'Completed')\
     .group_by(Order.payment_method)\
     .all()
    
    # Top selling products
    top_products = db.session.query(
        Shoe.name,
        func.count(Order.id).label('order_count'),
        func.sum(Order.amount).label('revenue')
    ).join(Order)\
     .filter(Order.payment_status == 'Completed')\
     .group_by(Shoe.id, Shoe.name)\
     .order_by(func.count(Order.id).desc())\
     .limit(5)\
     .all()
    
    # Recent 7 days sales
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_revenue = db.session.query(func.sum(Order.amount))\
                               .filter(Order.payment_status == 'Completed')\
                               .filter(Order.created_at >= seven_days_ago)\
                               .scalar() or 0
    
    recent_orders_count = Order.query.filter(Order.created_at >= seven_days_ago).count()
    
    # Products wishlisted
    most_wishlisted = db.session.query(
        Shoe.name,
        func.count(Wishlist.id).label('wishlist_count')
    ).join(Wishlist)\
     .group_by(Shoe.id, Shoe.name)\
     .order_by(func.count(Wishlist.id).desc())\
     .limit(5)\
     .all()
    
    analytics = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'total_products': total_products,
        'low_stock_count': len(low_stock_products),
        'out_of_stock_count': len(out_of_stock_products),
        'total_customers': total_customers,
        'revenue_by_method': revenue_by_method,
        'top_products': top_products,
        'recent_revenue': recent_revenue,
        'recent_orders': recent_orders_count,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'most_wishlisted': most_wishlisted
    }
    
    return render_template('admin.html', orders=orders, shoes=shoes, form=form, 
                         size_form=size_form, admin_type=admin_type, analytics=analytics)

@app.route('/admin/add_shoe', methods=['POST'])
@login_required
def add_shoe():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    # Check if user can add more products
    try:
        if not current_user.can_add_product():
            limit = getattr(current_user, 'product_limit', 0)
            flash(f'You have reached your product limit of {limit} products.', 'warning')
            return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Product limit check failed: {str(e)}")
        # Continue without limit check if there's an error
    
    form = ShoeForm()
    
    if form.validate_on_submit():
        try:
            image_url = None
            
            # Handle B2 upload if an image file was provided
            if form.image.data and form.image.data.filename != '':
                file = form.image.data
                
                if not allowed_file(file.filename):
                    flash(f'Invalid file type. Allowed types: {", ".join(app.config["ALLOWED_EXTENSIONS"])}', 'danger')
                    return redirect(url_for('admin'))
                
                filename = secure_filename(file.filename)
                if B2_AVAILABLE:
                    image_url = upload_to_b2(file, filename)
                    if not image_url:
                        flash('B2 upload failed', 'danger')
                        return redirect(url_for('admin'))
                else:
                    flash('File upload service not available. Please use image URL instead.', 'warning')
                    return redirect(url_for('admin'))
                    
            # If no file was uploaded but a URL was provided
            if not image_url and form.image_url.data:
                image_url = form.image_url.data
                
            # Ensure we have an image source
            if not image_url:
                flash('Either upload an image or provide an image URL', 'danger')
                return redirect(url_for('admin'))
            
            # Create shoe
            shoe_data = {
                'name': form.name.data,
                'price': form.price.data,
                'description': form.description.data,
                'image_url': image_url,
                'category': form.category.data
            }
            
            # Add created_by if the field exists
            try:
                shoe_data['created_by'] = current_user.id
            except:
                pass  # Field doesn't exist, skip it
            
            new_shoe = Shoe(**shoe_data)
            
            db.session.add(new_shoe)
            db.session.commit()
            cache.clear()
            flash('Shoe added successfully! Now add sizes', 'success')
            return redirect(url_for('manage_shoe_sizes', shoe_id=new_shoe.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving shoe: {str(e)}', 'danger')
            app.logger.error(f'Error in add_shoe: {str(e)}', exc_info=True)
    else:
        flash_errors(form)
    
    return redirect(url_for('admin'))



@app.route('/admin/shoe/<int:shoe_id>/sizes', methods=['GET', 'POST'])
@login_required
def manage_shoe_sizes(shoe_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    shoe = Shoe.query.get_or_404(shoe_id)
    
    # Check if limited admin can manage this shoe
    try:
        if current_user.is_limited_admin() and getattr(shoe, 'created_by', None) != current_user.id:
            flash('You can only manage your own products.', 'danger')
            return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Access control check failed: {str(e)}")
        # Continue without access control if there's an error
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
    
    # Check if limited admin can manage this shoe
    if current_user.is_limited_admin() and size.shoe.created_by != current_user.id:
        flash('You can only manage your own products.', 'danger')
        return redirect(url_for('admin'))
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
    
    # Check if limited admin can manage this shoe
    if current_user.is_limited_admin() and shoe.created_by != current_user.id:
        flash('You can only manage your own products.', 'danger')
        return redirect(url_for('admin'))
    form = ShoeForm(obj=shoe)
    
    if form.validate_on_submit():
        try:
            # Update fields
            shoe.name = form.name.data
            shoe.price = form.price.data
            shoe.description = form.description.data
            shoe.category = form.category.data
            
            # Handle image updates only if a new image is provided
            new_image_url = None
            
            if form.image.data and form.image.data.filename != '':
                file = form.image.data
                
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    if B2_AVAILABLE:
                        new_image_url = upload_to_b2(file, filename)
                    else:
                        flash('File upload service not available. Please use image URL instead.', 'warning')
                        return redirect(url_for('admin'))
                else:
                    flash('Invalid file type for uploaded image', 'danger')
                    return redirect(url_for('admin'))
                    
            # If no new file but a new URL was provided
            if not new_image_url and form.image_url.data:
                new_image_url = form.image_url.data
                
            # Update image URL only if we have a new one
            if new_image_url:
                shoe.image_url = new_image_url
            
            db.session.commit()
            cache.clear()
            flash('Shoe updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating shoe: {str(e)}', 'danger')
            app.logger.error(f'Error updating shoe: {str(e)}', exc_info=True)
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
    
    # Check if limited admin can manage this shoe
    if current_user.is_limited_admin() and shoe.created_by != current_user.id:
        flash('You can only manage your own products.', 'danger')
        return redirect(url_for('admin'))

    orders = Order.query.filter_by(shoe_id=shoe_id).all()
    for order in orders:
        order.shoe_id = None

    db.session.delete(shoe)
    db.session.commit()
    flash('Shoe deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/create_limited_admin', methods=['GET', 'POST'])
@login_required
def create_limited_admin():
    if not current_user.is_super_admin():
        flash('Only super admins can create limited admins.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        address = request.form.get('address', '')
        
        if not all([email, name, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('create_limited_admin'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('User with this email already exists.', 'danger')
            return redirect(url_for('create_limited_admin'))
        
        # Create limited admin
        limited_admin = User(
            email=email,
            password=password,
            name=name,
            address=address,
            is_admin=True,
            admin_type='limited_admin',
            product_limit=3
        )
        
        try:
            db.session.add(limited_admin)
            db.session.commit()
            flash(f'Limited admin {name} created successfully!', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating limited admin: {str(e)}', 'danger')
    
    return render_template('create_limited_admin.html')

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

# @app.route('/add_to_cart/<int:shoe_id>', methods=['POST'])
# @login_required
# def add_to_cart(shoe_id):
#     shoe = Shoe.query.get_or_404(shoe_id)
    
#     # Get size from form data
#     selected_size = request.form.get('size')
    
#     if not selected_size:
#         flash('Please select a size', 'danger')
#         return redirect(url_for('index'))
    
#     # Find the size inventory
#     size_inv = next((s for s in shoe.sizes if s.size == selected_size), None)
    
#     if not size_inv or size_inv.quantity < 1:
#         flash('This size is currently out of stock', 'danger')
#         return redirect(url_for('index'))
    
#     cart = session.get('cart', [])
    
#     # Add item with size
#     cart.append({
#         'shoe_id': shoe_id,
#         'size': selected_size
#     })
    
#     session['cart'] = cart
#     session.modified = True  # Explicitly mark session as modified
#     flash('Item added to cart', 'success')
#     return redirect(url_for('index'))

@app.route('/add_to_cart/<int:shoe_id>', methods=['POST'])
def add_to_cart(shoe_id):
    # Retrieve shoe FIRST to get available sizes
    shoe = Shoe.query.options(db.joinedload(Shoe.sizes)).get_or_404(shoe_id)
    
    # Create form and DYNAMICALLY SET CHOICES
    form = AddToCartForm(request.form)
    form.size.choices = [(str(size.size), str(size.size)) for size in shoe.sizes]
    
    # Validate after setting choices
    if not form.validate():
        flash('Invalid form submission. Please try again.', 'danger')
        return redirect(url_for('index'))
    
    # Get selected size and convert to int
    # try:
    #     selected_size = int(form.size.data)  # Convert string to int
    # except ValueError:
    #     flash('Invalid size selection', 'danger')
    #     return redirect(url_for('index'))
    # Convert selected size to int
    # Instead of converting to int, keep as string
    selected_size = form.size.data  # Keep as string
    size_inv = next((s for s in shoe.sizes if str(s.size) == selected_size), None)
    # Validate stock
    if not size_inv or size_inv.quantity < 1:
        flash(f"Size {selected_size} of {shoe.name} is out of stock", 'danger')
        return redirect(url_for('index'))


    
    # Step 6: Handle authentication
    if not current_user.is_authenticated:
        # Store in server session instead of sessionStorage
        session['pending_cart_item'] = {
            'shoe_id': shoe_id,
            'size': selected_size
        }
        flash('Please log in to complete adding to cart', 'info')
        return redirect(url_for('login', next=request.url))
    
    # Step 7: Add to cart (authenticated user)
    cart = session.get('cart', [])
    cart.append({
        'shoe_id': shoe_id,
        'size': selected_size
    })
    session['cart'] = cart
    flash(f"{shoe.name} (Size {selected_size}) added to cart!", 'success')
    return redirect(request.form.get('next', url_for('index')))

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

                    price = shoe.price if shoe.price else 0
                    cart_items.append({
                        'shoe': shoe,
                        'size': item.get('size', 'N/A'),
                        'price': shoe.price
                    })
                    total += shoe.price
            # Handle legacy format (shoe ID as integer)
            # elif isinstance(item, int):
            #     shoe = Shoe.query.get(item)
            #     if shoe:
            #         cart_items.append({
            #             'shoe': shoe,
            #             'size': 'Size not specified',
            #             'price': shoe.price
            #         })
            #         total += shoe.price
    
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
    
    if request.method == 'POST':
        try:
            payment_method = request.form.get('payment_method', 'cash')
            phone_number = request.form.get('phone_number', '')
            
            # Create orders first (with pending payment)
            order_ids = []
            for item in cart_items:
                shoe = item['shoe']
                size = item['size']
                
                # Create order
                order = Order(
                    user_id=current_user.id,
                    shoe_id=shoe.id,
                    size=size,
                    phone_number=phone_number,
                    payment_method=payment_method,
                    payment_status='Pending',
                    amount=shoe.price,
                    status='Pending'
                )
                db.session.add(order)
                db.session.flush()  # Get the order ID
                order_ids.append(order.id)
            
            db.session.commit()
            
            # Handle different payment methods
            if payment_method == 'mpesa_stk':
                # M-Pesa STK Push (Direct Daraja API)
                try:
                    from mpesa_helpers import initiate_stk_push, format_phone_number, validate_mpesa_credentials
                    
                    # Validate credentials
                    is_valid, error_msg = validate_mpesa_credentials()
                    if not is_valid:
                        flash(f'M-Pesa not configured: {error_msg}. Please use another payment method.', 'warning')
                        return redirect(url_for('view_cart'))
                    
                    # Get and format phone number
                    mpesa_phone = request.form.get('mpesa_phone', '')
                    formatted_phone = format_phone_number(mpesa_phone)
                    
                    # Use first order ID as primary reference
                    primary_order_id = order_ids[0]
                    
                    # Prepare callback URL
                    callback_url = url_for('mpesa_callback', _external=True)
                    
                    # Initiate STK Push
                    result = initiate_stk_push(
                        phone_number=formatted_phone,
                        amount=total,
                        account_reference=f"ORDER-{primary_order_id}",
                        transaction_desc=f"LegitCollections Order #{primary_order_id}",
                        callback_url=callback_url
                    )
                    
                    if result.get('success'):
                        # Update orders with checkout request ID
                        for order_id in order_ids:
                            order = Order.query.get(order_id)
                            order.payment_transaction_id = result.get('checkout_request_id')
                            order.payment_reference = result.get('merchant_request_id')
                            order.phone_number = formatted_phone
                        db.session.commit()
                        
                        # Show success message and redirect
                        flash('Payment request sent! Please check your phone and enter your M-Pesa PIN.', 'info')
                        return redirect(url_for('mpesa_payment_status', order_id=primary_order_id))
                    else:
                        flash(f"M-Pesa payment failed: {result.get('error')}", 'danger')
                        return redirect(url_for('view_cart'))
                        
                except Exception as e:
                    app.logger.error(f"M-Pesa STK Push error: {str(e)}")
                    flash('M-Pesa service temporarily unavailable. Please try another payment method.', 'warning')
                    return redirect(url_for('view_cart'))
            
            elif payment_method == 'pesapal':
                # Pesapal Payment
                try:
                    from pesapal_helpers import initiate_payment
                    
                    # Use first order ID as the primary reference
                    primary_order_id = order_ids[0]
                    
                    # Get or create IPN notification ID (should be done once during setup)
                    notification_id = os.getenv('PESAPAL_IPN_ID', '')
                    
                    # If no IPN ID, register one
                    if not notification_id:
                        from pesapal_helpers import register_ipn_url
                        ipn_url = url_for('pesapal_ipn', _external=True)
                        notification_id = register_ipn_url(ipn_url)
                        app.logger.warning(f"IPN ID created: {notification_id}. Add to .env file as PESAPAL_IPN_ID")
                    
                    # Prepare callback URL
                    callback_url = url_for('pesapal_callback', _external=True)
                    
                    # Initiate payment
                    result = initiate_payment(
                        order_id=primary_order_id,
                        amount=total,
                        description=f"Order #{primary_order_id} - LegitCollections",
                        callback_url=callback_url,
                        notification_id=notification_id,
                        customer_email=current_user.email,
                        customer_phone=phone_number
                    )
                    
                    if result.get('success'):
                        # Update orders with tracking ID
                        for order_id in order_ids:
                            order = Order.query.get(order_id)
                            order.payment_reference = result.get('merchant_reference')
                            order.payment_transaction_id = result.get('order_tracking_id')
                        db.session.commit()
                        
                        # Redirect to Pesapal payment page
                        return redirect(result.get('redirect_url'))
                    else:
                        flash(f"Payment initiation failed: {result.get('error')}", 'danger')
                        return redirect(url_for('view_cart'))
                        
                except Exception as e:
                    app.logger.error(f"Pesapal payment error: {str(e)}")
                    flash('Payment service temporarily unavailable. Please try another payment method.', 'warning')
                    return redirect(url_for('view_cart'))
            
            elif payment_method == 'manual_mpesa':
                # Manual M-Pesa payment
                payment_code = request.form.get('payment_code', '')
                
                if not payment_code:
                    flash('Please enter M-Pesa transaction code', 'danger')
                    return redirect(url_for('checkout'))
                
                # Update orders with payment code
                for order_id in order_ids:
                    order = Order.query.get(order_id)
                    order.payment_code = payment_code
                    
                    # Reduce stock
                    if order.size != 'Size not specified':
                        shoe = order.shoe
                        size_inv = next((s for s in shoe.sizes if s.size == order.size), None)
                        if size_inv and size_inv.quantity > 0:
                            size_inv.quantity -= 1
                
                db.session.commit()
                session.pop('cart', None)
                flash('Payment submitted! We will verify and process your order shortly.', 'success')
                return redirect(url_for('user_orders'))
            
            else:
                # Cash on delivery
                for order_id in order_ids:
                    order = Order.query.get(order_id)
                    order.payment_status = 'Cash on Delivery'
                
                db.session.commit()
                session.pop('cart', None)
                flash('Order placed successfully! Pay when you receive your items.', 'success')
                return redirect(url_for('user_orders'))
        
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Checkout error: {str(e)}")
            flash(f'Error processing order: {str(e)}', 'danger')
            return redirect(url_for('view_cart'))
    
    return render_template('checkout.html', form=form, cart=cart_items, total=total)

# Pesapal Payment Callbacks
@app.route('/pesapal/callback')
@login_required
def pesapal_callback():
    """Handle return from Pesapal payment page"""
    try:
        order_tracking_id = request.args.get('OrderTrackingId')
        merchant_reference = request.args.get('OrderMerchantReference')
        
        if not order_tracking_id:
            flash('Invalid payment response', 'danger')
            return redirect(url_for('user_orders'))
        
        # Check transaction status
        from pesapal_helpers import get_transaction_status, is_payment_successful
        
        status_result = get_transaction_status(order_tracking_id)
        
        if status_result.get('success'):
            payment_status_code = status_result.get('payment_status_code')
            
            # Find orders by transaction ID
            orders = Order.query.filter_by(payment_transaction_id=order_tracking_id).all()
            
            if is_payment_successful(payment_status_code):
                # Payment successful - update orders and reduce stock
                for order in orders:
                    order.payment_status = 'Completed'
                    order.status = 'Processing'
                    order.payment_transaction_id = status_result.get('confirmation_code', order_tracking_id)
                    
                    # Reduce stock
                    if order.size != 'Size not specified' and order.shoe:
                        size_inv = next((s for s in order.shoe.sizes if s.size == order.size), None)
                        if size_inv and size_inv.quantity > 0:
                            size_inv.quantity -= 1
                
                db.session.commit()
                
                # Clear cart
                session.pop('cart', None)
                
                flash('Payment successful! Your order is being processed.', 'success')
                return redirect(url_for('user_orders'))
            else:
                # Payment failed
                for order in orders:
                    order.payment_status = 'Failed'
                    order.status = 'Cancelled'
                
                db.session.commit()
                
                flash('Payment was not completed. Please try again.', 'warning')
                return redirect(url_for('view_cart'))
        else:
            flash('Unable to verify payment status. Please contact support.', 'warning')
            return redirect(url_for('user_orders'))
            
    except Exception as e:
        app.logger.error(f"Pesapal callback error: {str(e)}")
        flash('An error occurred while processing your payment', 'danger')
        return redirect(url_for('user_orders'))

# M-Pesa Payment Status Page
@app.route('/payment/mpesa/status/<int:order_id>')
@login_required
def mpesa_payment_status(order_id):
    """Show M-Pesa payment status page while waiting for confirmation"""
    order = Order.query.get_or_404(order_id)
    
    # Verify order belongs to current user
    if order.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_orders'))
    
    return render_template('mpesa_status.html', order=order)

# M-Pesa Callback Endpoint
@app.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa STK Push callback"""
    try:
        data = request.json
        app.logger.info(f"M-Pesa callback received: {data}")
        
        # Extract callback data
        callback_data = data.get('Body', {}).get('stkCallback', {})
        result_code = callback_data.get('ResultCode')
        result_desc = callback_data.get('ResultDesc')
        checkout_request_id = callback_data.get('CheckoutRequestID')
        
        # Find order by checkout request ID
        orders = Order.query.filter_by(payment_transaction_id=checkout_request_id).all()
        
        if not orders:
            app.logger.error(f"No orders found for CheckoutRequestID: {checkout_request_id}")
            return jsonify({'ResultCode': 1, 'ResultDesc': 'Order not found'}), 200
        
        # Check if payment was successful
        from mpesa_helpers import is_mpesa_payment_successful
        
        if is_mpesa_payment_successful(result_code):
            # Payment successful - extract transaction details
            callback_metadata = callback_data.get('CallbackMetadata', {}).get('Item', [])
            
            # Extract amount and receipt number
            mpesa_receipt = None
            amount_paid = None
            phone_number = None
            
            for item in callback_metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                elif item.get('Name') == 'Amount':
                    amount_paid = item.get('Value')
                elif item.get('Name') == 'PhoneNumber':
                    phone_number = item.get('Value')
            
            # Update all orders
            for order in orders:
                order.payment_status = 'Completed'
                order.status = 'Processing'
                order.payment_reference = mpesa_receipt
                if amount_paid:
                    order.amount = amount_paid
                if phone_number:
                    order.phone_number = str(phone_number)
                
                # Reduce stock
                if order.size != 'Size not specified' and order.shoe:
                    size_inv = next((s for s in order.shoe.sizes if s.size == order.size), None)
                    if size_inv and size_inv.quantity > 0:
                        size_inv.quantity -= 1
            
            db.session.commit()
            app.logger.info(f"M-Pesa payment completed: Receipt {mpesa_receipt}")
            
        else:
            # Payment failed or cancelled
            for order in orders:
                order.payment_status = 'Failed'
                order.status = 'Cancelled'
            
            db.session.commit()
            app.logger.info(f"M-Pesa payment failed: {result_desc}")
        
        # Always return success to M-Pesa
        return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'}), 200
        
    except Exception as e:
        app.logger.error(f"M-Pesa callback error: {str(e)}")
        return jsonify({'ResultCode': 1, 'ResultDesc': 'Failed'}), 200

# AJAX endpoint to check M-Pesa payment status
@app.route('/payment/mpesa/check/<int:order_id>')
@login_required
def check_mpesa_status(order_id):
    """AJAX endpoint to check if M-Pesa payment has been completed"""
    order = Order.query.get_or_404(order_id)
    
    # Verify order belongs to current user
    if order.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'payment_status': order.payment_status,
        'order_status': order.status,
        'payment_reference': order.payment_reference,
        'completed': order.payment_status == 'Completed'
    })

@app.route('/pesapal/ipn', methods=['GET', 'POST'])
def pesapal_ipn():
    """Handle Pesapal IPN (Instant Payment Notification)"""
    try:
        # Pesapal sends IPN with these parameters
        order_tracking_id = request.args.get('OrderTrackingId') or request.form.get('OrderTrackingId')
        merchant_reference = request.args.get('OrderMerchantReference') or request.form.get('OrderMerchantReference')
        order_notification_type = request.args.get('OrderNotificationType') or request.form.get('OrderNotificationType')
        
        if not order_tracking_id:
            return jsonify({'status': 'error', 'message': 'Missing tracking ID'}), 400
        
        # Get transaction status
        from pesapal_helpers import get_transaction_status, is_payment_successful
        
        status_result = get_transaction_status(order_tracking_id)
        
        if status_result.get('success'):
            payment_status_code = status_result.get('payment_status_code')
            
            # Find orders
            orders = Order.query.filter_by(payment_transaction_id=order_tracking_id).all()
            
            if orders:
                if is_payment_successful(payment_status_code):
                    # Update orders
                    for order in orders:
                        if order.payment_status != 'Completed':
                            order.payment_status = 'Completed'
                            order.status = 'Processing'
                            order.payment_transaction_id = status_result.get('confirmation_code', order_tracking_id)
                            
                            # Reduce stock if not already reduced
                            if order.size != 'Size not specified' and order.shoe:
                                size_inv = next((s for s in order.shoe.sizes if s.size == order.size), None)
                                if size_inv and size_inv.quantity > 0:
                                    size_inv.quantity -= 1
                    
                    db.session.commit()
                    app.logger.info(f"IPN: Payment completed for tracking ID {order_tracking_id}")
                else:
                    # Payment failed
                    for order in orders:
                        order.payment_status = 'Failed'
                        if order.status == 'Pending':
                            order.status = 'Cancelled'
                    
                    db.session.commit()
                    app.logger.info(f"IPN: Payment failed for tracking ID {order_tracking_id}")
        
        # Always return success to acknowledge IPN
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        app.logger.error(f"IPN error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/orders')
@login_required
def user_orders():
    orders = Order.query.filter_by(user_id=current_user.id) \
                       .order_by(Order.created_at.desc()) \
                       .all()
    
    for order in orders:
        if order.shoe:
            order.total_price = order.shoe.price
        else:
            order.total_price = 0

    return render_template('orders.html', orders=orders)

@app.route('/admin/export/orders')
@login_required
def export_orders():
    """Export orders to CSV"""
    if not current_user.is_admin:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    import csv
    from io import StringIO
    from flask import make_response
    
    # Get all orders
    orders = Order.query.order_by(Order.created_at.desc()).all()
    
    # Create CSV
    si = StringIO()
    writer = csv.writer(si)
    
    # Headers
    writer.writerow([
        'Order ID', 'Customer Name', 'Customer Email', 'Phone', 'Product', 'Size',
        'Amount', 'Payment Method', 'Payment Status', 'Payment Reference',
        'Order Status', 'Created At', 'Updated At'
    ])
    
    # Data
    for order in orders:
        writer.writerow([
            order.id,
            order.user.name if order.user else 'N/A',
            order.user.email if order.user else 'N/A',
            order.phone_number or 'N/A',
            order.shoe.name if order.shoe else 'N/A',
            order.size,
            order.amount or (order.shoe.price if order.shoe else 0),
            order.payment_method or 'Cash',
            order.payment_status or 'Pending',
            order.payment_reference or order.payment_code or 'N/A',
            order.status,
            order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            order.updated_at.strftime('%Y-%m-%d %H:%M:%S') if order.updated_at else 'N/A'
        ])
    
    # Create response
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=orders_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

@app.route('/admin/export/products')
@login_required
def export_products():
    """Export products inventory to CSV"""
    if not current_user.is_admin:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    import csv
    from io import StringIO
    from flask import make_response
    
    # Get all products
    shoes = Shoe.query.all()
    
    # Create CSV
    si = StringIO()
    writer = csv.writer(si)
    
    # Headers
    writer.writerow([
        'Product ID', 'Name', 'Category', 'Price', 'Total Stock',
        'Sizes Available', 'Description', 'Image URL', 'Created By', 'Created At'
    ])
    
    # Data
    for shoe in shoes:
        sizes_info = ', '.join([f"{s.size}({s.quantity})" for s in shoe.sizes])
        
        writer.writerow([
            shoe.id,
            shoe.name,
            shoe.category,
            shoe.price,
            shoe.total_stock,
            sizes_info or 'No sizes',
            shoe.description or '',
            shoe.image_url or '',
            shoe.created_by or 'N/A',
            shoe.created_at.strftime('%Y-%m-%d %H:%M:%S') if shoe.created_at else 'N/A'
        ])
    
    # Create response
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=products_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

@app.route('/search')
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    results = Shoe.query.options(db.joinedload(Shoe.sizes))\
                        .filter(
                            db.or_(
                                Shoe.name.ilike(f'%{query}%'),
                                Shoe.description.ilike(f'%{query}%'),
                                Shoe.category.ilike(f'%{query}%')
                            )
                        ).paginate(page=page, per_page=9)
    
    return render_template('search.html', results=results, query=query)

# Wishlist Routes
@app.route('/wishlist')
@login_required
def wishlist():
    """Display user's wishlist"""
    from models import Wishlist
    
    wishlist_items = Wishlist.query.filter_by(user_id=current_user.id)\
                                   .join(Shoe)\
                                   .options(db.joinedload(Wishlist.shoe).joinedload(Shoe.sizes))\
                                   .all()
    
    return render_template('wishlist.html', wishlist_items=wishlist_items)

@app.route('/wishlist/add/<int:shoe_id>', methods=['POST'])
@login_required
def add_to_wishlist(shoe_id):
    """Add item to wishlist"""
    from models import Wishlist
    
    try:
        shoe = Shoe.query.get_or_404(shoe_id)
        
        # Check if already in wishlist
        existing = Wishlist.query.filter_by(user_id=current_user.id, shoe_id=shoe_id).first()
        
        if existing:
            flash(f'{shoe.name} is already in your wishlist!', 'info')
        else:
            wishlist_item = Wishlist(user_id=current_user.id, shoe_id=shoe_id)
            db.session.add(wishlist_item)
            db.session.commit()
            flash(f'{shoe.name} added to wishlist!', 'success')
        
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Added to wishlist'})
        
        return redirect(request.referrer or url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding to wishlist: {str(e)}")
        flash('Error adding to wishlist', 'danger')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': str(e)}), 400
        
        return redirect(request.referrer or url_for('index'))

@app.route('/wishlist/remove/<int:wishlist_id>', methods=['POST'])
@login_required
def remove_from_wishlist(wishlist_id):
    """Remove item from wishlist"""
    from models import Wishlist
    
    try:
        wishlist_item = Wishlist.query.get_or_404(wishlist_id)
        
        # Verify ownership
        if wishlist_item.user_id != current_user.id:
            flash('Unauthorized action', 'danger')
            return redirect(url_for('wishlist'))
        
        shoe_name = wishlist_item.shoe.name
        db.session.delete(wishlist_item)
        db.session.commit()
        
        flash(f'{shoe_name} removed from wishlist', 'success')
        
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True})
        
        return redirect(url_for('wishlist'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error removing from wishlist: {str(e)}")
        flash('Error removing from wishlist', 'danger')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': str(e)}), 400
        
        return redirect(url_for('wishlist'))

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

# @app.route('/test_boto3')
# def test_boto3():
#     try:
#         import boto3
#         from botocore.client import Config
        
#         # Get configuration
#         key_id = os.getenv('B2_KEY_ID')
#         app_key = os.getenv('B2_APP_KEY')
#         bucket_name = os.getenv('B2_BUCKET_NAME')
#         endpoint_url = os.getenv('B2_ENDPOINT_URL')
        
#         # Create client
#         s3 = boto3.client(
#             's3',
#             aws_access_key_id=key_id,
#             aws_secret_access_key=app_key,
#             endpoint_url=endpoint_url,
#             config=Config(
#                 signature_version='s3v4',
#                 s3={'addressing_style': 'virtual'},
#                 region_name='us-east-005'
#             )
#         )
        
#         # Test connection
#         response = s3.list_buckets()
#         buckets = [b['Name'] for b in response['Buckets']]
        
#         return jsonify({
#             "status": "success",
#             "buckets": buckets,
#             "message": f"Connected to {endpoint_url}"
#         })
        
#     except Exception as e:
#         return jsonify({
#             "status": "error",
#             "message": str(e)
#         }), 500
    
# @app.route('/test_connection')
# def test_connection():
#     try:
#         import boto3
#         from botocore.client import Config
#         import re
        
#         # Get configuration
#         key_id = os.getenv('B2_KEY_ID')
#         app_key = os.getenv('B2_APP_KEY')
#         endpoint_url = os.getenv('B2_ENDPOINT_URL')
        
#         # Clean credentials
#         key_id = re.sub(r'[^\x20-\x7E]', '', key_id).strip()
#         app_key = re.sub(r'[^\x20-\x7E]', '', app_key).strip()
        
#         # Extract region
#         region_match = re.search(r'https://s3\.([\w\-]+)\.backblazeb2\.com', endpoint_url)
#         if not region_match:
#             return jsonify({"error": "Invalid endpoint format"}), 400
            
#         region = region_match.group(1)
        
#         # Create client
#         s3 = boto3.client(
#             's3',
#             aws_access_key_id=key_id,
#             aws_secret_access_key=app_key,
#             endpoint_url=endpoint_url,
#             config=Config(
#                 signature_version='s3v4',
#                 s3={'addressing_style': 'virtual'},
#                 region_name=region
#             )
#         )
        
#         # Test connection
#         response = s3.list_buckets()
#         bucket_names = [b['Name'] for b in response['Buckets']]
        
#         return jsonify({
#             "status": "success",
#             "buckets": bucket_names,
#             "region": region,
#             "endpoint": endpoint_url
#         })
        
#     except Exception as e:
#         return jsonify({
#             "status": "error",
#             "message": str(e),
#             "key_id": key_id,
#             "app_key": bool(app_key),  # Don't expose full key
#             "endpoint": endpoint_url,
#             "region": region
#         }), 500

@app.route('/b2_diag')
def b2_diag():
    try:
        from b2sdk.v2 import B2Api, InMemoryAccountInfo
        
        key_id = os.getenv('B2_KEY_ID')
        app_key = os.getenv('B2_APP_KEY')
        bucket_name = os.getenv('B2_BUCKET_NAME')
        
        # Mask credentials for logging
        key_id_mask = f"{key_id[:5]}...{key_id[-3:]}" if key_id else "Not set"
        app_key_mask = f"{app_key[:5]}...{app_key[-3:]}" if app_key else "Not set"
        
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        
        try:
            # Try US authorization
            b2_api.authorize_account("production", key_id, app_key)
            auth_success = True
            auth_server = "US"
        except Exception as us_e:
            try:
                # Try EU authorization
                b2_api.authorize_account("production", key_id, app_key, realm="eu-central-001")
                auth_success = True
                auth_server = "EU"
            except Exception as eu_e:
                return jsonify({
                    "status": "error",
                    "message": f"Authorization failed: US: {str(us_e)}, EU: {str(eu_e)}",
                    "key_id": key_id_mask,
                    "app_key": app_key_mask,
                    "bucket": bucket_name
                }), 500
        
        if auth_success:
            try:
                bucket = b2_api.get_bucket_by_name(bucket_name)
                return jsonify({
                    "status": "success",
                    "message": f"Authenticated with {auth_server} server",
                    "bucket": bucket_name,
                    "key_id": key_id_mask
                })
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": f"Bucket access failed: {str(e)}",
                    "bucket": bucket_name
                }), 500
                
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Diagnostic failed: {str(e)}"
        }), 500
    
@app.route('/test_b2_sdk')
def test_b2_sdk():
    try:
        from b2sdk.v2 import B2Api, InMemoryAccountInfo, UploadSourceBytes
        
        key_id = os.getenv('B2_KEY_ID')
        app_key = os.getenv('B2_APP_KEY')
        bucket_name = os.getenv('B2_BUCKET_NAME')
        
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", key_id, app_key)
        bucket = b2_api.get_bucket_by_name(bucket_name)
        
        # Upload a test file
        content = b"Test content from B2 SDK"
        uploaded_file = bucket.upload(
            upload_source=UploadSourceBytes(content),
            file_name="test_sdk.txt",
            content_type="text/plain"
        )
        
        # Get download URL
        public_url = b2_api.get_download_url_for_file_name(bucket_name, "test_sdk.txt")
        
        return jsonify({
            "status": "success",
            "url": public_url
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/b2_config')
def b2_config():
    return jsonify({
        "B2_KEY_ID": os.getenv('B2_KEY_ID', 'Not set'),
        "B2_APP_KEY": bool(os.getenv('B2_APP_KEY')),  # Show only if set
        "B2_BUCKET_NAME": os.getenv('B2_BUCKET_NAME', 'Not set'),
        "B2_ENDPOINT_URL": os.getenv('B2_ENDPOINT_URL', 'Not set')
    })

@app.route('/create_admin')
def create_admin():
    # Predefined admin credentials
    admin_email = "admin2@example.com"
    admin_password = "securepassword123"
    admin_name = "Admin User"
    admin_address = "Admin Address"
    
    # Check if admin already exists
    if User.query.filter_by(email=admin_email).first():
        return "Admin user already exists", 400
    
    # Create admin user
    admin = User(
        email=admin_email,
        password=bcrypt.generate_password_hash(admin_password).decode('utf-8'),
        name=admin_name,
        address=admin_address,
        is_admin=True
    )
    
    # Add to database
    try:
        db.session.add(admin)
        db.session.commit()
        return "Admin created successfully!<br>" \
               f"Email: {admin_email}<br>" \
               f"Password: {admin_password}<br>" \
               "<strong>IMPORTANT: Remove this route after use!</strong>"
    except Exception as e:
        db.session.rollback()
        return f"Error creating admin: {str(e)}", 500
    
@app.route('/test_b2')
def test_b2():
    try:
        # Create a test file
        from io import BytesIO
        test_file = BytesIO(b"This is a Backblaze test file")
        test_file.filename = "test_file.txt"
        test_file.content_type = "text/plain"
        
        # Attempt upload
        url = upload_to_b3(test_file, "test_file.txt")
        
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

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    # with app.app_context():
    #     # Create database tables if they don't exist
    #     db.create_all()
    
    # Determine if we're in production
    is_production = os.getenv('ENV') == 'production'
    
    # Force production mode if running on Koyeb (has PORT environment variable)
    if os.getenv('PORT') and not is_production:
        print("Detected Koyeb deployment, forcing production mode")
        is_production = True
    
    # Debug logging
    print(f"ENV variable: {os.getenv('ENV')}")
    print(f"Is production: {is_production}")
    print(f"PORT variable: {os.getenv('PORT')}")
    
    # Run the app
    if is_production:
        # Get port from environment variable or default to 8000
        port = int(os.getenv('PORT', 8000))
        # For production, try waitress first, fallback to Flask server
        try:
            from waitress import serve
            serve(app, host="0.0.0.0", port=port)
        except ImportError:
            # Fallback to Flask's built-in server if waitress is not available
            app.run(host="0.0.0.0", port=port, debug=False)
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