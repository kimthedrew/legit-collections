from app import create_app
from models import User
from extensions import db

app = create_app()

with app.app_context():
    # Create admin user
    admin = User(
        email='admin@example.com',
        password='adminpassword',
        name='Admin User',
        is_admin=True
    )
    
    # Add to session and commit
    db.session.add(admin)
    db.session.commit()
    print(f"Admin user created with ID: {admin.id}")