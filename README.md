# KnowBe4 - AI-Powered K-12 Student Assessment Platform

A modern, compliant platform for K-12 educators to assess students using AI-generated questions customized by topic and grade level, with actionable teaching insights and personalized student profiles.

## Overview

KnowBe4 simplifies student assessment through:
- **AI-Generated Assessments**: Google Gemini creates grade-appropriate questions on any topic
- **Topic-Based Testing**: Select subject + topic, assess entire class at once
- **Actionable Insights**: Dashboard shows student status, teaching guidance, and intervention priorities
- **Student Profiles**: Personalized learning insights based on assessment history
- **Full Compliance**: FERPA-compliant with documented parental consent

## Key Features

### Teacher Dashboard
- **Student Status Grid**: Color-coded performance indicators (green=on-track, yellow=needs attention, red=at-risk)
- **Today's Lesson Guidance**: AI-generated teaching strategies grouped by performance level
- **Student Profiles**: Searchable list with clickable profiles showing detailed learning insights
- **Needs Intervention**: Prioritized list of at-risk students scoring below 70%

### Topic-Based Assessments
- Select any K-12 subject (Math, Science, English, Social Studies, Arts, PE, Music, Computer Science)
- Enter specific topic (e.g., "Algebra", "Photosynthesis", "World War II")
- Assessments automatically sent to entire class
- AI generates grade-appropriate questions per student

### Student Profiles
- Individual assessment history
- Skill dimension performance tracking
- AI-synthesized learning summary
- Strengths and growth areas analysis

### Compliance & Privacy
- **Parental Consent Modal**: Required before dashboard access
- **FERPA Compliant**: Secure student data handling
- **COPPA Ready**: Parental/guardian consent requirement
- **Clear Data Disclosure**: Parents know how data is used by AI systems

## Tech Stack

### Frontend
- HTML5 / CSS3 / Vanilla JavaScript (no build step)
- Responsive design with CSS Grid & Flexbox
- Fetch API for backend communication

### Backend
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: JWT tokens with python-jose
- **AI**: Google Gemini 2.5 Flash

## Quick Start

### Prerequisites
- Python 3.10+
- Google Gemini API key
- pip package manager

### Setup

1. Navigate to backend
`ash
cd knowbe4/backend
`

2. Install dependencies
`ash
pip install -r requirements.txt
`

3. Set environment variables
`ash
export GEMINI_API_KEY="your-google-gemini-api-key"
`

4. Initialize database
`ash
python init_demo_data.py
`

5. Start the server
`ash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
`

6. Open in browser
- Teacher: http://127.0.0.1:8000/ui/teacher.html
- Student: http://127.0.0.1:8000/ui/student.html

### Demo Credentials

**Teacher:**
- Email: teacher@demo.com
- Password: password123

**Students:**
- ID: 1, PIN: 1234 (Alice Johnson)
- ID: 2, PIN: 5678 (Bob Smith)

## API Endpoints

### Authentication
- POST /auth/teacher/login - Teacher login
- POST /auth/student/login - Student login

### Classes
- GET /classes - List teacher's classes
- POST /classes - Create new class
- GET /classes/{class_id} - Get class roster
- POST /classes/{class_id}/students - Add student
- GET /classes/{class_id}/students/{student_id}/profile - Get student profile

### Assessments
- POST /classes/{class_id}/assess - Generate assessments for entire class
- POST /classes/{class_id}/students/{student_id}/assessments - Generate single assessment
- POST /assessments/{item_id}/answer - Submit student answer
- GET /auth/student/assessments/pending - Get pending assessments

## Compliance & Privacy

### FERPA (Family Educational Rights and Privacy Act)
- Student educational records are secured
- Only authorized teachers access class data

### COPPA (Children's Online Privacy Protection Act)
- Documented parental/guardian consent required
- Consent verified and stored

### Parental Consent Flow
1. Teacher logs in
2. Parental Consent Modal appears (if first time)
3. Modal explains data usage and AI processing
4. Parent/guardian checks box and clicks "I Consent"
5. Consent stored and dashboard loads
6. Option to decline (logs out immediately)

## Dashboard Features

### 1. Student Status Grid
- Color-coded performance: Green (80%+), Yellow (70-80%), Red (<70%)
- Clickable to view full student profile
- Scrollable for 30+ students

### 2. Today's Lesson Guidance
- AI-generated teaching strategies
- Grouped by performance level
- Actionable recommendations
- Updates with assessment results

### 3. Student Profiles
- Searchable list of students
- Shows latest score
- Click to view detailed profile
- Assessment history tracking

### 4. Needs Intervention
- Students scoring below 70%
- Prioritized for teacher attention
- Click to provide support

### 5. Assess Entire Class
- Select subject from dropdown
- Enter specific topic
- Sends assessment to all students
- AI customizes by grade level

## Project Structure

`
knowbe4/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── auth/
│   │   ├── llm/gemini.py
│   │   ├── models/
│   │   ├── routers/
│   │   └── schemas/
│   ├── static/
│   │   ├── index.html
│   │   └── student.html
│   ├── requirements.txt
│   └── init_demo_data.py
├── DEMO_GUIDE.txt
└── README.md
`

## Important Notes

### Before Production Deployment
1. Obtain documented parental consent
2. Establish data processing agreement with Google
3. Review state-specific K-12 data privacy laws
4. Get school district approval
5. Implement robust security measures
6. Follow all FERPA and COPPA requirements

### Development Status
- Demo-ready for hackathon
- Full feature set implemented
- All compliance requirements documented
- Production deployment requires security hardening

## Support

For questions or issues:
- Email: mannie.opoku@gmail.com
- GitHub: https://github.com/1dakdev/knowbe4

---

**Last Updated**: July 2026
