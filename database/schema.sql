-- Library Management System schema
-- Import: mysql -u root -p < database/schema.sql

CREATE DATABASE IF NOT EXISTS library_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE library_db;

CREATE TABLE IF NOT EXISTS admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    book_id INT AUTO_INCREMENT PRIMARY KEY,
    book_name VARCHAR(200) NOT NULL,
    author VARCHAR(150) NOT NULL,
    publisher VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    quantity INT NOT NULL,
    available_quantity INT NOT NULL,
    CONSTRAINT chk_book_qty CHECK (
        quantity >= 0
        AND available_quantity >= 0
        AND available_quantity <= quantity
    )
);

CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    student_name VARCHAR(150) NOT NULL,
    class_department VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,
    membership_type VARCHAR(50) NOT NULL,
    membership_start DATE NOT NULL,
    membership_end DATE NOT NULL,
    membership_status VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS issues (
    issue_id INT AUTO_INCREMENT PRIMARY KEY,
    book_id INT NOT NULL,
    student_id INT NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    return_date DATE NULL,
    fine DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_issue_book FOREIGN KEY (book_id) REFERENCES books (book_id),
    CONSTRAINT fk_issue_student FOREIGN KEY (student_id) REFERENCES students (student_id),
    CONSTRAINT chk_issue_dates CHECK (due_date >= issue_date),
    INDEX idx_issues_book (book_id),
    INDEX idx_issues_student (student_id),
    INDEX idx_issues_return (return_date)
);
