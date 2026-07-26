#!/usr/bin/env python3
"""Reset all assessments to start fresh for demo/recording"""
import sys
sys.path.insert(0, r'c:\Users\USER\Desktop\knowbe4\backend')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.assessment_item import AssessmentItem
from app.database import Base

# Connect to database
engine = create_engine("sqlite:///c:\\Users\\USER\\Desktop\\knowbe4\\backend\\data\\k12_assessment.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Delete all assessments
count = session.query(AssessmentItem).count()
session.query(AssessmentItem).delete()
session.commit()

print(f"✓ Reset complete! Deleted {count} assessments")
print("✓ All students now have score: 0%")
print("✓ Ready for fresh demo/recording")
