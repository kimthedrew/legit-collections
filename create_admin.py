from app import create_app
from models import User
from extensions import db

app = create_app()

with app.app_context():
    # Create super admin user
    admin = User(
        email='admin@example.com',
        password='adminpassword',
        name='Admin User',
        is_admin=True,
        admin_type='super_admin',
        product_limit=0  # 0 = unlimited
    )
    
    # Add to session and commit
    db.session.add(admin)
    db.session.commit()
    print(f"Admin user created with ID: {admin.id}")