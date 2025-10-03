#!/usr/bin/env python3
"""
Database initialization script for production deployment.
This script ensures the database is properly set up with all required fields.
"""

import os
import sys
from app import create_app, db
from models import User

def init_database():
    """Initialize the database with proper schema and default admin."""
    app = create_app()
    
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Check if admin exists
            admin = User.query.filter_by(is_admin=True).first()
            if admin:
                # Update existing admin to super admin if needed
                if not hasattr(admin, 'admin_type') or admin.admin_type is None:
                    try:
                        admin.admin_type = 'super_admin'
                        admin.product_limit = 0
                        db.session.commit()
                        print("✅ Updated existing admin to super admin")
                    except Exception as e:
                        print(f"⚠️  Could not update admin type: {e}")
                else:
                    print("✅ Admin already configured")
            else:
                print("⚠️  No admin user found. Please create one manually.")
            
            print("✅ Database initialization completed successfully")
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    init_database()
