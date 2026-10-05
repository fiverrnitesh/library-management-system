# Library Management System

A small Flask and MySQL application for managing library books, students, issue and return records, and late fines. It runs on localhost and can be copied to another computer as one folder.

## Requirements

- Python 3.9 or newer
- MySQL 8 (or MariaDB with the same schema)
- The `mysql` client, so you can import `database/schema.sql`

## Setup

From this project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` if your MySQL username or password is not `root` with an empty password.

Create the database:

```bash
mysql -u root -p < database/schema.sql
```

If your local root account has no password:

```bash
mysql -u root < database/schema.sql
```

On Homebrew, the client is often `/opt/homebrew/bin/mysql`.

The first time the app starts, it creates the librarian account from `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` if that username is not already in the `admins` table. Passwords are stored as hashes.

## Run

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

Demo login (unless you changed `.env` before the first start):

- Username: `admin`
- Password: `admin123`

## Fine rate

Late returns use `FINE_PER_DAY` from `.env` (default `5`, currency rupees). That value is read in `config.py` and is the only fine rate the app uses. Restart the app after changing it. Fines already saved in the database stay as they were.

Default loan length for the issue form is `LOAN_DAYS` (14).

## Moving to another computer

Git stores the code only. Books, students, and issue records stay in MySQL on the machine that created them. The other computer starts empty, then creates the `admin` account on first launch.

Do not copy `.venv` or `.env`. On the new machine:

```bash
git clone <repo-url>
cd library-management-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows, activate with `.venv\Scripts\activate`.

Edit `.env` for that machine’s MySQL login, import the schema, then start the app:

```bash
mysql -u root -p < database/schema.sql
python app.py
```

## Pages

- `/login`
- `/dashboard`
- `/books`, `/books/add`, `/books/edit/<id>`
- `/students`, `/students/add`, `/students/edit/<id>`, `/students/<id>`
- `/issues`, `/issues/issue`, `/issues/return`
- `/fines`
- `/reports`
