"""
Create the database, tables, and demo accounts.
Run using: python init_db.py
"""

import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from mysql.connector import Error


# Load .env from the same folder as this Python file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# Read database configuration
HOST = os.getenv("DB_HOST", "localhost")
USER = os.getenv("DB_USERNAME", "root")
PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE = os.getenv("DB_NAME", "hostel_complaints")


def initialize_database():
    conn = None
    cur = None

    try:
        # Connect to MySQL server
        conn = mysql.connector.connect(
            host=HOST,
            user=USER,
            password=PASSWORD
        )

        cur = conn.cursor()

        # Create database if it does not exist
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DATABASE}` "
            "CHARACTER SET utf8mb4 "
            "COLLATE utf8mb4_unicode_ci"
        )

        # Select database
        cur.execute(f"USE `{DATABASE}`")

        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                full_name VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('admin', 'student', 'staff') NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create complaints table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                assigned_staff_id INT NULL,
                title VARCHAR(150) NOT NULL,
                category ENUM(
                    'Electrical',
                    'Plumbing',
                    'Cleaning',
                    'Furniture',
                    'Internet',
                    'Security',
                    'Other'
                ) NOT NULL,
                location VARCHAR(120) NOT NULL,
                description TEXT NOT NULL,
                status ENUM(
                    'Submitted',
                    'Assigned',
                    'In Progress',
                    'Completed'
                ) NOT NULL DEFAULT 'Submitted',
                staff_response TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,

                CONSTRAINT fk_complaint_student
                    FOREIGN KEY (student_id) REFERENCES users(id),

                CONSTRAINT fk_complaint_staff
                    FOREIGN KEY (assigned_staff_id) REFERENCES users(id)
            )
        """)

        # Create complaint activity/history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS complaint_updates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                complaint_id INT NOT NULL,
                user_id INT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_update_complaint
                    FOREIGN KEY (complaint_id)
                    REFERENCES complaints(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_update_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Create demo accounts if they do not already exist
        accounts = [
            (
                "admin",
                "Hostel Administrator",
                "Admin@123",
                "admin"
            ),
            (
                "student1",
                "Demo Student",
                "Student@123",
                "student"
            ),
            (
                "staff1",
                "Maintenance Staff",
                "Staff@123",
                "staff"
            )
        ]

        for username, full_name, raw_password, role in accounts:

            cur.execute(
                "SELECT id FROM users WHERE username = %s",
                (username,)
            )

            existing_user = cur.fetchone()

            if existing_user is None:
                password_hash = generate_password_hash(raw_password)

                cur.execute("""
                    INSERT INTO users
                        (username, full_name, password_hash, role)
                    VALUES (%s, %s, %s, %s)
                """, (
                    username,
                    full_name,
                    password_hash,
                    role
                ))

        # Save database changes
        conn.commit()

        print("\nDatabase and demo accounts are ready!")
        print("--------------------------------------")
        print("Admin:   admin / Admin@123")
        print("Student: student1 / Student@123")
        print("Staff:   staff1 / Staff@123")
        print("--------------------------------------")
        print("You can now start the Flask application.")

    except Error as error:
        if conn is not None and conn.is_connected():
            conn.rollback()

        print("\nDatabase initialization failed.")
        print("MySQL error:", error)
        print("\nPlease check:")
        print("1. MySQL server is running.")
        print("2. Your .env file contains the correct credentials.")
        print("3. The MySQL user has permission to create a database.")

    finally:
        if cur is not None:
            cur.close()

        if conn is not None and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    initialize_database()