"""
Database migration script

This script creates the new database schema with proper session and incident tracking.
Run this to initialize or upgrade the database.
"""

from flask import Flask
from models import db, Session, Incident, IncidentFrame, GeminiAnalysis, UserAlert
import os

def migrate_database():
    """Create or migrate database to new schema"""
    
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///security_monitor.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database with app
    db.init_app(app)
    
    with app.app_context():
        print("🗄️  Creating database tables...")
        
        # Check if old database exists
        old_db = 'theft_detection.db'
        if os.path.exists(old_db):
            print(f"⚠️  Found old database: {old_db}")
            print(f"   New database will be: security_monitor.db")
            backup_prompt = input("   Continue? (y/n): ")
            if backup_prompt.lower() != 'y':
                print("   Migration cancelled.")
                return
        
        # Drop all tables (clean slate)
        print("   Dropping existing tables...")
        db.drop_all()
        
        # Create all tables
        print("   Creating new tables...")
        db.create_all()
        
        # Verify tables were created
        tables = [Session, Incident, IncidentFrame, GeminiAnalysis, UserAlert]
        for table in tables:
            count = db.session.query(table).count()
            print(f"   ✅ {table.__tablename__}: {count} rows")
        
        print("✅ Database migration complete!")
        print(f"   Database file: security_monitor.db")
        print(f"   Tables created: {len(tables)}")
        
        # Print schema summary
        print("\n📋 Schema Summary:")
        print("   - sessions: Monitoring sessions (start/stop)")
        print("   - incidents: Hand detection incidents")
        print("   - incident_frames: Individual frames within incidents")
        print("   - gemini_analyses: Gemini API analysis results")
        print("   - user_alerts: Alerts sent to user")


if __name__ == '__main__':
    migrate_database()

