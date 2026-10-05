"""Library Management System.

Run: python app.py
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from pymysql.err import DatabaseError, IntegrityError, OperationalError
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from db import close_db, execute, get_db, query_all, query_one

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s]{7,20}$")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.teardown_appcontext(close_db)

    @app.template_filter("money")
    def money_filter(value):
        return f"{as_money(value):.2f}"

    @app.context_processor
    def inject_globals():
        return {
            "fine_per_day": Config.FINE_PER_DAY,
            "today": date.today(),
        }

    register_routes(app)
    return app


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def as_money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_fine(due_date, return_date):
    """Charge FINE_PER_DAY for each day after the due date."""
    if return_date <= due_date:
        return Decimal("0.00")
    days = (return_date - due_date).days
    return as_money(Decimal(days) * Decimal(str(Config.FINE_PER_DAY)))


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def clean(value):
    return (value or "").strip()


def like_pattern(value):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def ensure_admin():
    existing = query_one("SELECT admin_id FROM admins WHERE username = %s", (Config.ADMIN_USERNAME,))
    if existing:
        return
    try:
        execute(
            "INSERT INTO admins (username, password) VALUES (%s, %s)",
            (
                Config.ADMIN_USERNAME,
                generate_password_hash(Config.ADMIN_PASSWORD, method="pbkdf2:sha256"),
            ),
        )
    except IntegrityError:
        return


def issued_copies(book):
    return int(book["quantity"]) - int(book["available_quantity"])


def book_form_data(source):
    return {
        "book_name": clean(source.get("book_name")),
        "author": clean(source.get("author")),
        "publisher": clean(source.get("publisher")),
        "category": clean(source.get("category")),
        "quantity": clean(source.get("quantity")),
    }


def validate_book(form, issued=0):
    errors = []
    for field, label in (
        ("book_name", "Book name"),
        ("author", "Author"),
        ("publisher", "Publisher"),
        ("category", "Category"),
        ("quantity", "Quantity"),
    ):
        if not form[field]:
            errors.append(f"{label} is required.")
    quantity = None
    if form["quantity"]:
        if not form["quantity"].isdigit():
            errors.append("Quantity must be a whole number.")
        else:
            quantity = int(form["quantity"])
            if quantity < issued:
                errors.append(
                    f"Quantity cannot be less than {issued}, the number of copies currently issued."
                )
            if quantity > 100000:
                errors.append("Quantity is too large.")
    return errors, quantity


def student_form_data(source):
    return {
        "student_name": clean(source.get("student_name")),
        "class_department": clean(source.get("class_department")),
        "phone": clean(source.get("phone")),
        "email": clean(source.get("email")),
        "address": clean(source.get("address")),
        "membership_type": clean(source.get("membership_type")),
        "membership_start": clean(source.get("membership_start")),
        "membership_end": clean(source.get("membership_end")),
        "membership_status": clean(source.get("membership_status")),
    }


def validate_student(form):
    errors = []
    required = (
        ("student_name", "Student name"),
        ("class_department", "Class / department"),
        ("phone", "Phone"),
        ("email", "Email"),
        ("address", "Address"),
        ("membership_type", "Membership type"),
        ("membership_start", "Membership start"),
        ("membership_end", "Membership end"),
        ("membership_status", "Membership status"),
    )
    for field, label in required:
        if not form[field]:
            errors.append(f"{label} is required.")
    if form["phone"] and not PHONE_RE.match(form["phone"]):
        errors.append("Enter a valid phone number.")
    if form["email"] and not EMAIL_RE.match(form["email"]):
        errors.append("Enter a valid email address.")
    if form["membership_type"] not in ("Regular", "Student", "Faculty"):
        errors.append("Select a membership type.")
    if form["membership_status"] not in ("Active", "Inactive"):
        errors.append("Select a membership status.")
    start = parse_date(form["membership_start"])
    end = parse_date(form["membership_end"])
    if form["membership_start"] and not start:
        errors.append("Membership start date is invalid.")
    if form["membership_end"] and not end:
        errors.append("Membership end date is invalid.")
    if start and end and end < start:
        errors.append("Membership end date cannot be before the start date.")
    return errors, start, end


def register_routes(app):
    @app.before_request
    def prepare_admin():
        if request.endpoint in (None, "static"):
            return None
        try:
            ensure_admin()
        except (OperationalError, DatabaseError):
            return render_template("db_error.html"), 500
        return None

    @app.route("/")
    def home():
        if session.get("admin_id"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("admin_id"):
            return redirect(url_for("dashboard"))
        error = None
        if request.method == "POST":
            username = clean(request.form.get("username"))
            password = request.form.get("password") or ""
            admin = query_one("SELECT * FROM admins WHERE username = %s", (username,))
            if admin and check_password_hash(admin["password"], password):
                session.clear()
                session["admin_id"] = admin["admin_id"]
                session["username"] = admin["username"]
                nxt = request.args.get("next") or ""
                if not nxt.startswith("/") or nxt.startswith("//"):
                    nxt = url_for("dashboard")
                return redirect(nxt)
            error = "Invalid username or password."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        books = query_one(
            """
            SELECT COUNT(*) AS titles,
                   COALESCE(SUM(quantity), 0) AS total_books,
                   COALESCE(SUM(available_quantity), 0) AS available_books
            FROM books
            """
        )
        students = query_one("SELECT COUNT(*) AS total_students FROM students")
        issues = query_one(
            """
            SELECT
                COALESCE(SUM(return_date IS NULL), 0) AS active_issues,
                COALESCE(SUM(return_date IS NULL AND due_date < CURDATE()), 0) AS overdue_issues,
                COALESCE(SUM(fine), 0) AS total_fines
            FROM issues
            """
        )
        activity = query_all(
            """
            SELECT i.issue_id, i.issue_date, i.due_date, i.return_date, i.fine,
                   b.book_name, s.student_name
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            ORDER BY COALESCE(i.return_date, i.issue_date) DESC, i.issue_id DESC
            LIMIT 8
            """
        )
        stats = {
            "total_books": int(books["total_books"]),
            "available_books": int(books["available_books"]),
            "issued_books": int(books["total_books"]) - int(books["available_books"]),
            "titles": int(books["titles"]),
            "total_students": int(students["total_students"]),
            "active_issues": int(issues["active_issues"]),
            "overdue_issues": int(issues["overdue_issues"]),
            "total_fines": issues["total_fines"],
        }
        return render_template("dashboard.html", stats=stats, activity=activity)

    @app.route("/books")
    @login_required
    def books():
        q = clean(request.args.get("q"))
        if q:
            like = like_pattern(q)
            rows = query_all(
                """
                SELECT * FROM books
                WHERE book_name LIKE %s OR author LIKE %s OR publisher LIKE %s
                   OR category LIKE %s OR CAST(book_id AS CHAR) LIKE %s
                ORDER BY book_id DESC
                """,
                (like, like, like, like, like),
            )
        else:
            rows = query_all("SELECT * FROM books ORDER BY book_id DESC")
        return render_template("books.html", books=rows, q=q)

    @app.route("/books/add", methods=["GET", "POST"])
    @login_required
    def add_book():
        form = book_form_data(request.form if request.method == "POST" else {})
        errors = []
        if request.method == "POST":
            errors, quantity = validate_book(form)
            if not errors:
                execute(
                    """
                    INSERT INTO books
                        (book_name, author, publisher, category, quantity, available_quantity)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (form["book_name"], form["author"], form["publisher"], form["category"], quantity, quantity),
                )
                flash("Book added.", "success")
                return redirect(url_for("books"))
        return render_template("book_form.html", form=form, errors=errors, mode="add")

    @app.route("/books/edit/<int:book_id>", methods=["GET", "POST"])
    @login_required
    def edit_book(book_id):
        book = query_one("SELECT * FROM books WHERE book_id = %s", (book_id,))
        if not book:
            flash("Book not found.", "error")
            return redirect(url_for("books"))
        issued = issued_copies(book)
        if request.method == "POST":
            form = book_form_data(request.form)
        else:
            form = {
                "book_name": book["book_name"],
                "author": book["author"],
                "publisher": book["publisher"],
                "category": book["category"],
                "quantity": str(book["quantity"]),
            }
        errors = []
        if request.method == "POST":
            errors, quantity = validate_book(form, issued=issued)
            if not errors:
                available = quantity - issued
                execute(
                    """
                    UPDATE books
                    SET book_name = %s, author = %s, publisher = %s, category = %s,
                        quantity = %s, available_quantity = %s
                    WHERE book_id = %s
                    """,
                    (
                        form["book_name"],
                        form["author"],
                        form["publisher"],
                        form["category"],
                        quantity,
                        available,
                        book_id,
                    ),
                )
                flash("Book updated.", "success")
                return redirect(url_for("books"))
        return render_template(
            "book_form.html",
            form=form,
            errors=errors,
            mode="edit",
            book=book,
            issued=issued,
        )

    @app.route("/books/delete/<int:book_id>", methods=["POST"])
    @login_required
    def delete_book(book_id):
        try:
            execute("DELETE FROM books WHERE book_id = %s", (book_id,))
            flash("Book deleted.", "success")
        except IntegrityError:
            flash("Cannot delete this book because issue records exist for it.", "error")
        return redirect(url_for("books"))

    @app.route("/students")
    @login_required
    def students():
        q = clean(request.args.get("q"))
        if q:
            like = like_pattern(q)
            rows = query_all(
                """
                SELECT * FROM students
                WHERE student_name LIKE %s OR class_department LIKE %s OR phone LIKE %s
                   OR email LIKE %s OR CAST(student_id AS CHAR) LIKE %s
                ORDER BY student_id DESC
                """,
                (like, like, like, like, like),
            )
        else:
            rows = query_all("SELECT * FROM students ORDER BY student_id DESC")
        return render_template("students.html", students=rows, q=q)

    @app.route("/students/add", methods=["GET", "POST"])
    @login_required
    def add_student():
        if request.method == "POST":
            form = student_form_data(request.form)
        else:
            today = date.today()
            form = student_form_data({})
            form["membership_type"] = "Student"
            form["membership_status"] = "Active"
            form["membership_start"] = today.isoformat()
            form["membership_end"] = (today + timedelta(days=365)).isoformat()
        errors = []
        if request.method == "POST":
            errors, start, end = validate_student(form)
            if not errors:
                execute(
                    """
                    INSERT INTO students (
                        student_name, class_department, phone, email, address,
                        membership_type, membership_start, membership_end, membership_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        form["student_name"],
                        form["class_department"],
                        form["phone"],
                        form["email"],
                        form["address"],
                        form["membership_type"],
                        start,
                        end,
                        form["membership_status"],
                    ),
                )
                flash("Student added.", "success")
                return redirect(url_for("students"))
        return render_template("student_form.html", form=form, errors=errors, mode="add")

    @app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
    @login_required
    def edit_student(student_id):
        student = query_one("SELECT * FROM students WHERE student_id = %s", (student_id,))
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("students"))
        if request.method == "POST":
            form = student_form_data(request.form)
        else:
            form = {
                "student_name": student["student_name"],
                "class_department": student["class_department"],
                "phone": student["phone"],
                "email": student["email"],
                "address": student["address"],
                "membership_type": student["membership_type"],
                "membership_start": student["membership_start"].isoformat(),
                "membership_end": student["membership_end"].isoformat(),
                "membership_status": student["membership_status"],
            }
        errors = []
        if request.method == "POST":
            errors, start, end = validate_student(form)
            if not errors:
                execute(
                    """
                    UPDATE students
                    SET student_name = %s, class_department = %s, phone = %s, email = %s,
                        address = %s, membership_type = %s, membership_start = %s,
                        membership_end = %s, membership_status = %s
                    WHERE student_id = %s
                    """,
                    (
                        form["student_name"],
                        form["class_department"],
                        form["phone"],
                        form["email"],
                        form["address"],
                        form["membership_type"],
                        start,
                        end,
                        form["membership_status"],
                        student_id,
                    ),
                )
                flash("Student updated.", "success")
                return redirect(url_for("students"))
        return render_template(
            "student_form.html", form=form, errors=errors, mode="edit", student=student
        )

    @app.route("/students/<int:student_id>")
    @login_required
    def student_detail(student_id):
        student = query_one("SELECT * FROM students WHERE student_id = %s", (student_id,))
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("students"))
        history = query_all(
            """
            SELECT i.*, b.book_name
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            WHERE i.student_id = %s
            ORDER BY i.issue_id DESC
            """,
            (student_id,),
        )
        return render_template("student_detail.html", student=student, history=history)

    @app.route("/students/delete/<int:student_id>", methods=["POST"])
    @login_required
    def delete_student(student_id):
        try:
            execute("DELETE FROM students WHERE student_id = %s", (student_id,))
            flash("Student deleted.", "success")
        except IntegrityError:
            flash("Cannot delete this student because issue records exist for them.", "error")
        return redirect(url_for("students"))

    @app.route("/issues")
    @login_required
    def issues():
        q = clean(request.args.get("q"))
        sql = """
            SELECT i.*, b.book_name, s.student_name
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
        """
        params = ()
        if q:
            like = like_pattern(q)
            sql += """
                WHERE b.book_name LIKE %s OR s.student_name LIKE %s
                   OR CAST(i.issue_id AS CHAR) LIKE %s
            """
            params = (like, like, like)
        sql += " ORDER BY i.issue_id DESC"
        rows = query_all(sql, params)
        return render_template("issues.html", issues=rows, q=q)

    @app.route("/issues/issue", methods=["GET", "POST"])
    @login_required
    def issue_book():
        students_list = query_all(
            "SELECT student_id, student_name, class_department FROM students ORDER BY student_name"
        )
        book_list = query_all(
            """
            SELECT book_id, book_name, author, available_quantity
            FROM books
            WHERE available_quantity > 0
            ORDER BY book_name
            """
        )
        today = date.today()
        form = {
            "student_id": clean(request.form.get("student_id")) if request.method == "POST" else "",
            "book_id": clean(request.form.get("book_id")) if request.method == "POST" else "",
            "issue_date": clean(request.form.get("issue_date")) if request.method == "POST" else today.isoformat(),
            "due_date": clean(request.form.get("due_date"))
            if request.method == "POST"
            else (today + timedelta(days=Config.LOAN_DAYS)).isoformat(),
        }
        errors = []
        if request.method == "POST":
            issue_date = parse_date(form["issue_date"])
            due_date = parse_date(form["due_date"])
            if not form["student_id"].isdigit():
                errors.append("Select a student.")
            if not form["book_id"].isdigit():
                errors.append("Select a book.")
            if not issue_date:
                errors.append("Issue date is required.")
            if not due_date:
                errors.append("Due date is required.")
            if issue_date and due_date and due_date < issue_date:
                errors.append("Due date cannot be before the issue date.")
            if not errors:
                student = query_one(
                    "SELECT student_id FROM students WHERE student_id = %s", (int(form["student_id"]),)
                )
                if not student:
                    errors.append("Selected student is not registered.")
            if not errors:
                db = get_db()
                try:
                    with db.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE books
                            SET available_quantity = available_quantity - 1
                            WHERE book_id = %s AND available_quantity > 0
                            """,
                            (int(form["book_id"]),),
                        )
                        if cur.rowcount != 1:
                            db.rollback()
                            errors.append("This book has no copies available.")
                        else:
                            cur.execute(
                                """
                                INSERT INTO issues (book_id, student_id, issue_date, due_date, fine)
                                VALUES (%s, %s, %s, %s, 0)
                                """,
                                (int(form["book_id"]), int(form["student_id"]), issue_date, due_date),
                            )
                            db.commit()
                            flash("Book issued.", "success")
                            return redirect(url_for("issues"))
                except Exception:
                    db.rollback()
                    raise
        return render_template(
            "issue_form.html",
            form=form,
            errors=errors,
            students=students_list,
            books=book_list,
        )

    @app.route("/issues/return", methods=["GET"])
    @login_required
    def return_books():
        rows = query_all(
            """
            SELECT i.*, b.book_name, s.student_name
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            WHERE i.return_date IS NULL
            ORDER BY i.due_date ASC, i.issue_id ASC
            """
        )
        for row in rows:
            row["estimated_fine"] = calculate_fine(row["due_date"], date.today())
        return render_template("return_book.html", issues=rows)

    @app.route("/issues/return/<int:issue_id>", methods=["POST"])
    @login_required
    def return_book(issue_id):
        return_date = parse_date(request.form.get("return_date"))
        if not return_date:
            flash("Return date is required.", "error")
            return redirect(url_for("return_books"))
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM issues WHERE issue_id = %s FOR UPDATE", (issue_id,))
                issue = cur.fetchone()
                if not issue:
                    db.rollback()
                    flash("Issue record not found.", "error")
                    return redirect(url_for("return_books"))
                if issue["return_date"] is not None:
                    db.rollback()
                    flash("This book is already returned.", "error")
                    return redirect(url_for("return_books"))
                if return_date < issue["issue_date"]:
                    db.rollback()
                    flash("Return date cannot be before the issue date.", "error")
                    return redirect(url_for("return_books"))
                fine = calculate_fine(issue["due_date"], return_date)
                cur.execute(
                    """
                    UPDATE issues
                    SET return_date = %s, fine = %s
                    WHERE issue_id = %s AND return_date IS NULL
                    """,
                    (return_date, fine, issue_id),
                )
                cur.execute(
                    """
                    UPDATE books
                    SET available_quantity = LEAST(quantity, available_quantity + 1)
                    WHERE book_id = %s
                    """,
                    (issue["book_id"],),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        if fine > 0:
            flash(f"Book returned. Late fine: ₹{fine:.2f}.", "success")
        else:
            flash("Book returned. No fine.", "success")
        return redirect(url_for("issues"))

    @app.route("/fines")
    @login_required
    def fines():
        collected = query_all(
            """
            SELECT i.*, b.book_name, s.student_name
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            WHERE i.fine > 0
            ORDER BY i.return_date DESC, i.issue_id DESC
            """
        )
        overdue = query_all(
            """
            SELECT i.*, b.book_name, s.student_name
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            WHERE i.return_date IS NULL AND i.due_date < CURDATE()
            ORDER BY i.due_date ASC
            """
        )
        for row in overdue:
            row["estimated_fine"] = calculate_fine(row["due_date"], date.today())
        total = query_one("SELECT COALESCE(SUM(fine), 0) AS total FROM issues")
        return render_template(
            "fines.html",
            collected=collected,
            overdue=overdue,
            total_fines=total["total"],
        )

    @app.route("/reports")
    @login_required
    def reports():
        report = request.args.get("type") or "all_books"
        titles = {
            "all_books": "All Books",
            "available_books": "Available Books",
            "issued_books": "Issued Books",
            "returned_books": "Returned Books",
            "overdue_books": "Overdue Books",
            "students": "Student / Member Records",
            "fines": "Fine Records",
        }
        if report not in titles:
            report = "all_books"
        rows = report_rows(report)
        return render_template(
            "reports.html",
            report=report,
            report_title=titles[report],
            titles=titles,
            rows=rows,
        )


def report_rows(report):
    if report == "all_books":
        return query_all("SELECT * FROM books ORDER BY book_name")
    if report == "available_books":
        return query_all(
            "SELECT * FROM books WHERE available_quantity > 0 ORDER BY book_name"
        )
    if report == "issued_books":
        return query_all(
            """
            SELECT i.issue_id, b.book_id, b.book_name, b.author, s.student_name,
                   i.issue_date, i.due_date, i.fine
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            WHERE i.return_date IS NULL
            ORDER BY i.due_date
            """
        )
    if report == "returned_books":
        return query_all(
            """
            SELECT i.issue_id, b.book_name, s.student_name, i.issue_date,
                   i.due_date, i.return_date, i.fine
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            WHERE i.return_date IS NOT NULL
            ORDER BY i.return_date DESC
            """
        )
    if report == "overdue_books":
        return query_all(
            """
            SELECT i.issue_id, b.book_name, s.student_name, s.phone,
                   i.issue_date, i.due_date
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            WHERE i.return_date IS NULL AND i.due_date < CURDATE()
            ORDER BY i.due_date
            """
        )
    if report == "students":
        return query_all("SELECT * FROM students ORDER BY student_name")
    if report == "fines":
        return query_all(
            """
            SELECT i.issue_id, b.book_name, s.student_name, i.issue_date,
                   i.due_date, i.return_date, i.fine
            FROM issues i
            JOIN books b ON b.book_id = i.book_id
            JOIN students s ON s.student_id = i.student_id
            WHERE i.fine > 0
            ORDER BY i.fine DESC, i.issue_id DESC
            """
        )
    return []


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=Config.PORT, debug=True)
