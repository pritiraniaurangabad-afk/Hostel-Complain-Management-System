"""
Hostel Complaint Management System
Run using: python app.py
"""

import os
from pathlib import Path
from functools import wraps

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort
)
from werkzeug.security import check_password_hash


# --------------------------------------------------
# 1. LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------
# 2. FLASK CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key-before-deployment"
)


# --------------------------------------------------
# 3. MYSQL CONFIGURATION
# --------------------------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USERNAME", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "hostel_complaints")
}


def get_db():
    """Create and return a MySQL database connection."""
    return mysql.connector.connect(**DB_CONFIG)


def query_db(sql, params=(), fetchone=False, commit=False):
    """
    Execute an SQL query.

    fetchone=True returns one record.
    Otherwise, SELECT queries return all records.
    commit=True saves INSERT, UPDATE, and DELETE changes.
    """

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(sql, params)

        if cursor.with_rows:
            result = cursor.fetchone() if fetchone else cursor.fetchall()
        else:
            result = None

        if commit:
            conn.commit()

        return result

    except Error:
        if conn.is_connected():
            conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


# --------------------------------------------------
# 4. LOGIN AND ROLE AUTHENTICATION
# --------------------------------------------------

def login_required(view):
    """Allow access only to logged-in users."""

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Allow access only to users with specified roles."""

    def decorator(view):

        @wraps(view)
        def wrapped(*args, **kwargs):

            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))

            if session.get("role") not in roles:
                abort(403)

            return view(*args, **kwargs)

        return wrapped

    return decorator


# --------------------------------------------------
# 5. COMPLAINT ACTIVITY HISTORY
# --------------------------------------------------

def add_activity(complaint_id, user_id, message):

    query_db(
        """
        INSERT INTO complaint_updates
            (complaint_id, user_id, message)
        VALUES (%s, %s, %s)
        """,
        (complaint_id, user_id, message),
        commit=True
    )


# --------------------------------------------------
# 6. HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# --------------------------------------------------
# 7. LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = query_db(
            """
            SELECT *
            FROM users
            WHERE username = %s AND is_active = 1
            """,
            (username,),
            fetchone=True
        )

        if user and check_password_hash(
            user["password_hash"], password
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["name"] = user["full_name"]
            session["role"] = user["role"]

            return redirect(url_for("dashboard"))

        flash(
            "Incorrect username or password, or the account is inactive.",
            "danger"
        )

    return render_template("login.html")


# --------------------------------------------------
# 8. LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


# --------------------------------------------------
# 9. ROLE-BASED DASHBOARD REDIRECTION
# --------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    role = session.get("role")

    if role == "student":
        return redirect(url_for("student_dashboard"))

    if role == "admin":
        return redirect(url_for("admin_dashboard"))

    if role == "staff":
        return redirect(url_for("staff_dashboard"))

    abort(403)


# --------------------------------------------------
# 10. STUDENT DASHBOARD
# --------------------------------------------------

@app.route("/student")
@role_required("student")
def student_dashboard():

    complaints = query_db(
        """
        SELECT
            c.*,
            s.full_name AS student_name,
            st.full_name AS staff_name
        FROM complaints c
        JOIN users s ON s.id = c.student_id
        LEFT JOIN users st ON st.id = c.assigned_staff_id
        WHERE c.student_id = %s
        ORDER BY c.created_at DESC
        """,
        (session["user_id"],)
    )

    return render_template(
        "student_dashboard.html",
        complaints=complaints
    )


# --------------------------------------------------
# 11. SUBMIT A NEW COMPLAINT
# --------------------------------------------------

@app.route("/complaints/new", methods=["GET", "POST"])
@role_required("student")
def new_complaint():

    categories = [
        "Electrical",
        "Plumbing",
        "Cleaning",
        "Furniture",
        "Internet",
        "Security",
        "Other"
    ]

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not all([title, category, location, description]):

            flash("Please fill in every field.", "danger")

            return render_template(
                "new_complaint.html",
                categories=categories
            )

        if category not in categories:

            flash("Please select a valid complaint category.", "danger")

            return render_template(
                "new_complaint.html",
                categories=categories
            )

        conn = None
        cursor = None

        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO complaints
                    (student_id, title, category, location,
                     description, status)
                VALUES (%s, %s, %s, %s, %s, 'Submitted')
                """,
                (
                    session["user_id"],
                    title,
                    category,
                    location,
                    description
                )
            )

            complaint_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO complaint_updates
                    (complaint_id, user_id, message)
                VALUES (%s, %s, %s)
                """,
                (
                    complaint_id,
                    session["user_id"],
                    "Complaint submitted."
                )
            )

            conn.commit()

            flash(
                f"Complaint #{complaint_id} submitted successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "complaint_detail",
                    complaint_id=complaint_id
                )
            )

        except Error as error:

            if conn is not None and conn.is_connected():
                conn.rollback()

            app.logger.error("Complaint submission failed: %s", error)

            flash(
                "Could not save the complaint. Please check the database.",
                "danger"
            )

        finally:

            if cursor is not None:
                cursor.close()

            if conn is not None and conn.is_connected():
                conn.close()

    return render_template(
        "new_complaint.html",
        categories=categories
    )


# --------------------------------------------------
# 12. VIEW COMPLAINT DETAILS
# --------------------------------------------------

@app.route("/complaints/<int:complaint_id>")
@login_required
def complaint_detail(complaint_id):

    complaint = query_db(
        """
        SELECT
            c.*,
            s.full_name AS student_name,
            st.full_name AS staff_name
        FROM complaints c
        JOIN users s ON s.id = c.student_id
        LEFT JOIN users st ON st.id = c.assigned_staff_id
        WHERE c.id = %s
        """,
        (complaint_id,),
        fetchone=True
    )

    if not complaint:
        abort(404)

    role = session.get("role")

    # Students can view only their own complaints.
    if (
        role == "student"
        and complaint["student_id"] != session["user_id"]
    ):
        abort(403)

    # Staff can view only complaints assigned to them.
    if (
        role == "staff"
        and complaint["assigned_staff_id"] != session["user_id"]
    ):
        abort(403)

    updates = query_db(
        """
        SELECT
            cu.*,
            u.full_name AS author_name,
            u.role AS author_role
        FROM complaint_updates cu
        JOIN users u ON u.id = cu.user_id
        WHERE cu.complaint_id = %s
        ORDER BY cu.created_at ASC, cu.id ASC
        """,
        (complaint_id,)
    )

    staff_members = query_db(
        """
        SELECT id, full_name
        FROM users
        WHERE role = 'staff' AND is_active = 1
        ORDER BY full_name
        """
    )

    return render_template(
        "complaint_detail.html",
        complaint=complaint,
        updates=updates,
        staff_members=staff_members
    )


# --------------------------------------------------
# 13. ADMIN DASHBOARD
# --------------------------------------------------

@app.route("/admin")
@role_required("admin")
def admin_dashboard():

    status_filter = request.args.get("status", "").strip()

    allowed_statuses = {
        "Submitted",
        "Assigned",
        "In Progress",
        "Completed"
    }

    if status_filter in allowed_statuses:

        complaints = query_db(
            """
            SELECT
                c.*,
                s.full_name AS student_name,
                st.full_name AS staff_name
            FROM complaints c
            JOIN users s ON s.id = c.student_id
            LEFT JOIN users st ON st.id = c.assigned_staff_id
            WHERE c.status = %s
            ORDER BY c.created_at DESC
            """,
            (status_filter,)
        )

    else:

        status_filter = ""

        complaints = query_db(
            """
            SELECT
                c.*,
                s.full_name AS student_name,
                st.full_name AS staff_name
            FROM complaints c
            JOIN users s ON s.id = c.student_id
            LEFT JOIN users st ON st.id = c.assigned_staff_id
            ORDER BY c.created_at DESC
            """
        )

    staff_members = query_db(
        """
        SELECT id, full_name
        FROM users
        WHERE role = 'staff' AND is_active = 1
        ORDER BY full_name
        """
    )

    stats = query_db(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(status = 'Submitted'), 0) AS submitted,
            COALESCE(
                SUM(status IN ('Assigned', 'In Progress')), 0
            ) AS active,
            COALESCE(SUM(status = 'Completed'), 0) AS completed
        FROM complaints
        """,
        fetchone=True
    )

    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        staff_members=staff_members,
        stats=stats,
        status_filter=status_filter
    )


# --------------------------------------------------
# 14. ASSIGN COMPLAINT TO STAFF
# --------------------------------------------------

@app.route(
    "/admin/complaints/<int:complaint_id>/assign",
    methods=["POST"]
)
@role_required("admin")
def assign_complaint(complaint_id):

    staff_id = request.form.get("staff_id", type=int)

    complaint = query_db(
        """
        SELECT id, status
        FROM complaints
        WHERE id = %s
        """,
        (complaint_id,),
        fetchone=True
    )

    staff = query_db(
        """
        SELECT id
        FROM users
        WHERE id = %s
          AND role = 'staff'
          AND is_active = 1
        """,
        (staff_id,),
        fetchone=True
    ) if staff_id is not None else None

    if not complaint or not staff:

        flash(
            "Complaint or staff member was not found.",
            "danger"
        )

        return redirect(url_for("admin_dashboard"))

    new_status = (
        "Completed"
        if complaint["status"] == "Completed"
        else "Assigned"
    )

    query_db(
        """
        UPDATE complaints
        SET assigned_staff_id = %s,
            status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (staff_id, new_status, complaint_id),
        commit=True
    )

    add_activity(
        complaint_id,
        session["user_id"],
        f"Complaint assigned to staff member #{staff_id}. "
        f"Status is now {new_status}."
    )

    flash("Complaint assigned successfully.", "success")

    return redirect(
        url_for(
            "complaint_detail",
            complaint_id=complaint_id
        )
    )


# --------------------------------------------------
# 15. STAFF DASHBOARD
# --------------------------------------------------

@app.route("/staff")
@role_required("staff")
def staff_dashboard():

    complaints = query_db(
        """
        SELECT
            c.*,
            s.full_name AS student_name,
            st.full_name AS staff_name
        FROM complaints c
        JOIN users s ON s.id = c.student_id
        LEFT JOIN users st ON st.id = c.assigned_staff_id
        WHERE c.assigned_staff_id = %s
        ORDER BY
            CASE c.status
                WHEN 'Assigned' THEN 1
                WHEN 'In Progress' THEN 2
                ELSE 3
            END,
            c.updated_at DESC
        """,
        (session["user_id"],)
    )

    return render_template(
        "staff_dashboard.html",
        complaints=complaints
    )


# --------------------------------------------------
# 16. UPDATE COMPLAINT STATUS AND STAFF RESPONSE
# --------------------------------------------------

@app.route(
    "/staff/complaints/<int:complaint_id>/status",
    methods=["POST"]
)
@role_required("staff")
def update_status(complaint_id):

    status = request.form.get("status", "").strip()
    note = request.form.get("response", "").strip()

    if status not in ("In Progress", "Completed"):

        flash("Invalid status.", "danger")

        return redirect(url_for("staff_dashboard"))

    complaint = query_db(
        """
        SELECT *
        FROM complaints
        WHERE id = %s AND assigned_staff_id = %s
        """,
        (complaint_id, session["user_id"]),
        fetchone=True
    )

    if not complaint:
        abort(403)

    if complaint["status"] == "Completed":

        flash(
            "A completed complaint cannot be changed.",
            "warning"
        )

        return redirect(
            url_for(
                "complaint_detail",
                complaint_id=complaint_id
            )
        )

    query_db(
        """
        UPDATE complaints
        SET status = %s,
            staff_response = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (status, note or None, complaint_id),
        commit=True
    )

    message = f"Status changed to {status}."

    if note:
        message += f" Staff response: {note}"

    add_activity(
        complaint_id,
        session["user_id"],
        message
    )

    flash(
        "Complaint updated. The student and admin can see "
        "the latest status and response.",
        "success"
    )

    return redirect(
        url_for(
            "complaint_detail",
            complaint_id=complaint_id
        )
    )


# --------------------------------------------------
# 17. ERROR PAGES
# --------------------------------------------------

@app.errorhandler(403)
def forbidden(_error):

    return render_template(
        "error.html",
        code=403,
        message="You do not have permission to view this page."
    ), 403


@app.errorhandler(404)
def not_found(_error):

    return render_template(
        "error.html",
        code=404,
        message="The requested page or complaint was not found."
    ), 404


# --------------------------------------------------
# 18. START THE FLASK SERVER
# --------------------------------------------------

if __name__ == "__main__":

    print("Starting Hostel Complaint Management System...")
    print("Open http://127.0.0.1:5000 in your browser.")

    app.run(debug=True)