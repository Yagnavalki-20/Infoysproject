from flask import Flask, jsonify, request, render_template, session
from flask_cors import CORS
import sqlite3
import logging
from functools import wraps

# Initialize the Flask app
app = Flask(__name__, template_folder="Frontend/templates", static_folder="Frontend/static")
CORS(app)  # Enable CORS for frontend-backend communication
app.secret_key = 'your_secret_key'  # Required for session management

# Database configuration
DATABASE = 'upskill_vision.db1.db'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to connect to the SQLite database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

# Helper function to execute a database query
def execute_query(query, args=(), fetch_all=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, args)
        if fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor.fetchone()
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

# Decorator for requiring authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Serve the frontend HTML pages
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/mycourses')
def mycourses():
    try:
        # Replace this with logic to retrieve the logged-in user's ID
        user_id = 1  # Example: Replace with session.get('user_id') or similar

        # Fetch enrolled courses using the existing API endpoint
        enrolled_courses_response = get_enrolled_courses(user_id)
        if enrolled_courses_response.status_code != 200:
            raise Exception("Failed to fetch enrolled courses")

        enrolled_courses = enrolled_courses_response.get_json()

        # Separate enrolled and completed courses
        enrolled = [course for course in enrolled_courses if course['status'] != 'completed']
        completed = [course for course in enrolled_courses if course['status'] == 'completed']

        # Render the mycourses.html template with the courses data
        return render_template("mycourses.html", enrolled_courses=enrolled, completed_courses=completed)

    except Exception as e:
        logger.error(f"Error fetching courses: {e}")
        return render_template("mycourses.html", error="An error occurred while fetching courses")

@app.route('/enroll')
def enroll():
    return render_template("enroll.html")
@app.route('/course/<int:course_id>')
def course(course_id):
    return render_template("course.html", course_id=course_id)

@app.route('/course/<int:course_id>')
def course_details(course_id):
    return render_template("course_detail.html", course_id=course_id)
@app.route('/quizzes')
def quizzes():
    return render_template("quizzes.html")

@app.route('/learning')
def learning():
    return render_template("learning.html")

# API Endpoints

# Get all courses with progress for a specific user
@app.route('/api/courses', methods=['GET'])
def get_all_courses():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        courses = execute_query("SELECT * FROM courses", fetch_all=True)

        if not courses:
            return jsonify([]), 200

        progress_data = execute_query("SELECT course_id, progress, status FROM enrollment WHERE user_id = ?", (user_id,), fetch_all=True)
        progress_map = {row['course_id']: row for row in progress_data} if progress_data else {}

        course_list = []
        for course in courses:
            progress = progress_map.get(course['id'], {"progress": 0, "status": None})
            course_list.append({
                "id": course['id'],
                "title": course['title'],
                "description": course['description'],
                "duration": course['duration'],
                "instructor_id": course['instructor_id'],
                "images": course['images'],
                "progress": progress['progress'],
                "status": progress['status']
            })

        return jsonify(course_list), 200

    except Exception as e:
        logger.error(f"Error fetching courses: {e}")
        return jsonify({"error": "An error occurred while fetching courses"}), 500

# Enroll a user in a course
@app.route('/api/enroll', methods=['POST'])
def enroll_course():
    try:
        data = request.json
        user_id = data.get('user_id')
        course_id = data.get('course_id')

        if not user_id or not course_id:
            return jsonify({"error": "Missing user_id or course_id"}), 400

        # Check if the user is already enrolled
        enrollment = execute_query("SELECT * FROM enrollment WHERE user_id = ? AND course_id = ?", (user_id, course_id))

        if enrollment:
            return jsonify({"message": "User is already enrolled in this course"}), 200

        # Enroll the user
        execute_query("""
            INSERT INTO enrollment (user_id, course_id, progress, status, enrollment_date)
            VALUES (?, ?, 0, 'enrolled', datetime('now'))
        """, (user_id, course_id))

        return jsonify({"message": "Enrollment successful"}), 200

    except Exception as e:
        logger.error(f"Error enrolling user: {e}")
        return jsonify({"error": "An error occurred while enrolling"}), 500

# Get a specific course by ID
@app.route('/api/courses/<int:course_id>', methods=['GET'])
def get_course(course_id):
    try:
        # Fetch the course by ID
        course = execute_query("SELECT * FROM courses WHERE id = ?", (course_id,))

        if not course:
            return jsonify({"error": "Course not found"}), 404

        return jsonify(dict(course)), 200
    except Exception as e:
        logger.error(f"Error fetching course: {e}")
        return jsonify({"error": "An error occurred while fetching course"}), 500

# Get enrolled courses for a user
@app.route('/api/enrolled-courses/<int:user_id>', methods=['GET'])
def get_enrolled_courses(user_id):
    try:
        # Fetch enrollments for the user
        enrollments = execute_query("SELECT * FROM enrollment WHERE user_id = ?", (user_id,), fetch_all=True)

        if not enrollments:
            return jsonify([]), 200

        # Fetch course details for each enrollment
        course_list = []
        for enrollment in enrollments:
            course = execute_query("SELECT * FROM courses WHERE id = ?", (enrollment['course_id'],))
            if course:
                course_list.append({
                    "id": course['id'],
                    "title": course['title'],
                    "description": course['description'],
                    "duration": course['duration'],
                    "instructor_id": course['instructor_id'],
                    "images": course['images'],
                    "progress": enrollment['progress'],
                    "status": enrollment['status'],
                    "enrollment_date": enrollment['enrollment_date']
                })

        return jsonify(course_list), 200

    except Exception as e:
        logger.error(f"Error fetching enrolled courses: {e}")
        return jsonify({"error": "An error occurred while fetching enrolled courses"}), 500

# Get user progress for a bar chart
@app.route('/api/user-progress/<int:user_id>', methods=['GET'])
def get_user_progress(user_id):
    try:
        # Fetch enrolled courses and progress for the user
        progress_data = execute_query('''
            SELECT c.title, e.progress
            FROM enrollment e
            JOIN courses c ON e.course_id = c.id
            WHERE e.user_id = ?
        ''', (user_id,), fetch_all=True)

        if not progress_data:
            return jsonify({"error": "No courses found for this user"}), 404

        # Prepare data for the bar chart
        courses = [row['title'] for row in progress_data]  # Course titles
        progress = [row['progress'] for row in progress_data]  # Progress percentages

        return jsonify({"labels": courses, "progress": progress}), 200

    except Exception as e:
        logger.error(f"Error fetching user progress: {e}")
        return jsonify({"error": "An error occurred while fetching user progress"}), 500

# Get progress data for a user
@app.route('/api/progress/<int:user_id>', methods=['GET'])
def get_progress(user_id):
    try:
        # Fetch enrollments for the user
        progress_data = execute_query("SELECT course_id, progress, status FROM enrollment WHERE user_id = ?", (user_id,), fetch_all=True)

        if not progress_data:
            return jsonify([]), 200

        # Convert rows to a list of dictionaries
        progress_list = [dict(row) for row in progress_data]

        return jsonify(progress_list), 200

    except Exception as e:
        logger.error(f"Error fetching progress data: {e}")
        return jsonify({"error": "An error occurred while fetching progress data"}), 500

# Update progress for a course
@app.route('/api/progress', methods=['POST'])
def update_progress():
    try:
        data = request.json
        user_id = data.get('user_id')
        course_id = data.get('course_id')
        progress = data.get('progress')
        status = data.get('status', 'enrolled')  # Default status is 'enrolled'

        if not user_id or not course_id or progress is None:
            return jsonify({"error": "Missing required fields"}), 400

        # Check if the enrollment exists
        enrollment = execute_query("SELECT * FROM enrollment WHERE user_id = ? AND course_id = ?", (user_id, course_id))

        if enrollment:
            # Update the existing enrollment
            execute_query("""
                UPDATE enrollment
                SET progress = ?, status = ?
                WHERE user_id = ? AND course_id = ?
            """, (progress, status, user_id, course_id))
        else:
            # Create a new enrollment
            execute_query("""
                INSERT INTO enrollment (user_id, course_id, progress, status, enrollment_date)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (user_id, course_id, progress, status))

        return jsonify({"message": "Progress updated successfully"}), 200

    except Exception as e:
        logger.error(f"Error updating progress: {e}")
        return jsonify({"error": "An error occurred while updating progress"}), 500

# Get modules for a course
@app.route('/api/courses/<int:course_id>/modules', methods=['GET'])
def get_course_modules(course_id):
    try:
        # Fetch modules for the specified course_id
        modules = execute_query("SELECT * FROM module WHERE course_id = ?", (course_id,), fetch_all=True)
        
        if not modules:
            return jsonify({"error": "No modules found for this course"}), 404

        # Convert the result to a list of dictionaries
        module_list = [dict(module) for module in modules]
        return jsonify(module_list), 200
    except Exception as e:
        logger.error(f"Error fetching course modules: {e}")
        return jsonify({"error": "An error occurred while fetching course modules"}), 500

@app.route('/api/quizzes/<int:course_id>', methods=['GET'])
def get_quiz_questions(course_id):
    try:
        # Fetch quiz questions for the specified course_id
        quizzes = execute_query("SELECT * FROM quiz WHERE course_id = ?", (course_id,), fetch_all=True)
        
        if not quizzes:
            return jsonify({"error": "No quizzes found for this course"}), 404

        # Convert the result to a list of dictionaries
        quiz_list = [dict(quiz) for quiz in quizzes]
        return jsonify(quiz_list), 200
    except Exception as e:
        logger.error(f"Error fetching quiz questions: {e}")
        return jsonify({"error": "An error occurred while fetching quiz questions"}), 500

# Get details of a specific module
@app.route('/api/module/<int:module_id>', methods=['GET'])
def get_module(module_id):
    try:
        # Fetch the module by ID
        module = execute_query("SELECT * FROM module WHERE id = ?", (module_id,))

        if not module:
            return jsonify({"error": "Module not found"}), 404

        return jsonify(dict(module)), 200

    except Exception as e:
        logger.error(f"Error fetching module: {e}")
        return jsonify({"error": "An error occurred while fetching module"}), 500

# Mark a module as complete
@app.route('/api/mark-module-complete', methods=['POST'])
def mark_module_complete():
    try:
        data = request.json
        module_id = data.get('module_id')

        if not module_id:
            return jsonify({"error": "Missing module_id"}), 400

        # Mark the module as complete
        execute_query("""
            UPDATE module
            SET is_completed = 1
            WHERE id = ?
        """, (module_id,))

        return jsonify({"success": True}), 200

    except Exception as e:
        logger.error(f"Error marking module as complete: {e}")
        return jsonify({"error": "An error occurred while marking module as complete"}), 500

# Submit quiz
@app.route('/api/submit-quiz', methods=['POST'])
def submit_quiz():
    try:
        data = request.json
        user_id = data.get('user_id')
        course_id = data.get('course_id')
        user_answers = data.get('user_answers')  # List of user's answers

        if not user_id or not course_id or not user_answers:
            return jsonify({"error": "Missing required fields"}), 400

        # Fetch the correct answers for the quiz questions
        quizzes = execute_query("SELECT id, correct_answer FROM quiz WHERE course_id = ?", (course_id,), fetch_all=True)
        if not quizzes:
            return jsonify({"error": "No quizzes found for this course"}), 404

        # Calculate the score
        correct_answers = 0
        total_questions = len(quizzes)

        for i, quiz in enumerate(quizzes):
            if user_answers[i] == quiz['correct_answer']:
                correct_answers += 1

        # Calculate the score percentage
        score_percentage = (correct_answers / total_questions) * 100

        # Update the user's progress in the enrollment table
        execute_query("""
            UPDATE enrollment
            SET progress = ?
            WHERE user_id = ? AND course_id = ?
        """, (score_percentage, user_id, course_id))

        # Return the quiz results
        return jsonify({
            "message": "Quiz submitted successfully",
            "score": correct_answers,
            "total_questions": total_questions,
            "score_percentage": score_percentage
        }), 200

    except Exception as e:
        logger.error(f"Error submitting quiz: {e}")
        return jsonify({"error": "An error occurred while submitting quiz"}), 500

# Get quiz history for a user
@app.route('/api/quiz-history/<int:user_id>', methods=['GET'])
def get_quiz_history(user_id):
    try:
        # Fetch quiz history for the user
        quiz_history = execute_query('''
            SELECT q.course_id, c.title AS course_title, q.score, q.total_questions, q.date
            FROM quiz_results q
            JOIN courses c ON q.course_id = c.id
            WHERE q.user_id = ?
        ''', (user_id,), fetch_all=True)
        return jsonify(quiz_history), 200
    except Exception as e:
        logger.error(f"Error fetching quiz history: {e}")
        return jsonify({"error": "An error occurred while fetching quiz history"}), 500

# Submit course rating
@app.route('/api/submit-rating', methods=['POST'])
def submit_rating():
    try:
        data = request.json
        course_id = data.get('course_id')
        rating = data.get('rating')

        if not course_id or not rating:
            return jsonify({"error": "Missing course_id or rating"}), 400

        if not (1 <= rating <= 5):
            return jsonify({"error": "Rating must be between 1 and 5"}), 400

        # Insert the rating into the database
        execute_query("""
            INSERT INTO ratings (course_id, rating)
            VALUES (?, ?)
        """, (course_id, rating))

        return jsonify({"success": True}), 200

    except Exception as e:
        logger.error(f"Error submitting rating: {e}")
        return jsonify({"error": "An error occurred while submitting rating"}), 500

# Run the app
if __name__ == '__main__':
    app.run(debug=True)