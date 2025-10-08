from app import create_app
from models import User
from extensions import db

app = create_app()

with app.app_context():
    # Check if limited admin already exists
    existing = User.query.filter_by(email='limitedadmin@example.com').first()
    if existing:
        print("Limited admin user already exists!")
        print(f"Email: limitedadmin@example.com")
        print(f"Name: {existing.name}")
        print(f"Admin Type: {existing.admin_type}")
        print(f"Product Limit: {existing.product_limit}")
        print(f"Current Products: {existing.get_product_count()}")
    else:
        # Create limited admin user
        limited_admin = User(
            email='limitedadmin@example.com',
            password='limitedpass',
            name='Limited Admin',
            address='123 Limited St',
            is_admin=True,
            admin_type='limited_admin',
            product_limit=3
        )
        
        # Add to session and commit
        db.session.add(limited_admin)
        db.session.commit()
        
        print("✅ Limited admin user created successfully!")
        print(f"ID: {limited_admin.id}")
        print(f"Email: limitedadmin@example.com")
        print(f"Password: limitedpass")
        print(f"Name: {limited_admin.name}")
        print(f"Admin Type: {limited_admin.admin_type}")
        print(f"Product Limit: {limited_admin.product_limit}")
        print("\n🔐 You can now login with:")
        print("   Email: limitedadmin@example.com")
        print("   Password: limitedpass")
        print("\n📝 Limited admins can:")
        print("   - Add up to 3 products")
        print("   - Edit/delete only their own products")
        print("   - View all orders but cannot verify payments")
        print("   - Cannot create other admin accounts")


