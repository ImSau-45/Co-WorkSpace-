import os
import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "cowork.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"  # for demo only
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Create tables
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price_per_hour REAL NOT NULL,
            rating REAL,
            image_path TEXT,
            currency TEXT DEFAULT 'USD',
            owner_id INTEGER,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT,
            hours INTEGER NOT NULL,
            total_price REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
        );
        """
    )

    # Reviews table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
        );
        """
    )

    conn.commit()
    # Ensure `currency` column exists (older DBs may lack it)
    cur.execute("PRAGMA table_info(workspaces)")
    existing_cols = [c[1] for c in cur.fetchall()]
    if "currency" not in existing_cols:
        cur.execute("ALTER TABLE workspaces ADD COLUMN currency TEXT DEFAULT 'USD'")
        conn.commit()

    # Ensure bookings table has booking_date column for older DBs
    cur.execute("PRAGMA table_info(bookings)")
    booking_cols = [c[1] for c in cur.fetchall()]
    if "booking_date" not in booking_cols:
        try:
            cur.execute("ALTER TABLE bookings ADD COLUMN booking_date TEXT")
            conn.commit()
        except Exception:
            # If bookings table doesn't exist yet or another issue, ignore and continue
            pass
    # Ensure bookings table has start_time column for older DBs
    if "start_time" not in booking_cols:
        try:
            cur.execute("ALTER TABLE bookings ADD COLUMN start_time TEXT")
            conn.commit()
        except Exception:
            pass

    # Seed example workspaces if none exist
    cur.execute("SELECT COUNT(*) as cnt FROM workspaces")
    count = cur.fetchone()["cnt"]
    if count == 0:
        example_workspaces = [
            # US examples (USD)
            ("Downtown Loft Desk", "Modern desk space with fast Wi-Fi and great city view.", 12.5, 4.7, None, 'INR', None),
            ("Creative Hub Meeting Room", "Bright meeting room ideal for workshops and client calls.", 25.0, 4.5, None, 'USD', None),
            ("Quiet Focus Pod", "Soundproof pod for deep work and focus.", 15.0, 4.9, None, 'USD', None),
            # Indian examples (INR) with placeholder SVGs in static/uploads
            ("Bengaluru Startup Loft", "Cozy loft in Koramangala with reliable internet and vibrant community.",None, 350.0, 4.8, 'INR', None),
            ("Delhi Meeting Suite", "Professional meeting suite in Connaught Place with presentation setup.", 1200.0, 4.6,  'INR', None),
            ("Mumbai Focus Pod", "Private focus pod near Bandra with ergonomic chair and quiet ambiance.", 450.0, 4.7,  'INR', None),
            ("Hyderabad Creative Hub", "Spacious creative workspace with whiteboards and natural light.", 800.0, 4.5, 'INR', None),
        ]
        cur.executemany(
            """
            INSERT INTO workspaces (name, description, price_per_hour, rating, image_path, currency, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            example_workspaces,
        )
        conn.commit()

    # Ensure Indian example entries exist (insert if missing)
    cur.execute("SELECT COUNT(*) as has_b FROM workspaces WHERE name = ?", ("Bengaluru Startup Loft",))
    if cur.fetchone()["has_b"] == 0:
        indian_examples = [
            ("Bengaluru Startup Loft", "Cozy loft in Koramangala with reliable internet and vibrant community.", 350.0, 4.8, 'uploads/bengaluru_loft.svg', 'INR', None),
            ("Delhi Meeting Suite", "Professional meeting suite in Connaught Place with presentation setup.", 1200.0, 4.6, 'uploads/delhi_meeting.svg', 'INR', None),
            ("Mumbai Focus Pod", "Private focus pod near Bandra with ergonomic chair and quiet ambiance.", 450.0, 4.7, 'uploads/mumbai_pod.svg', 'INR', None),
            ("Hyderabad Creative Hub", "Spacious creative workspace with whiteboards and natural light.", 800.0, 4.5, 'uploads/hyderabad_hub.svg', 'INR', None),
        ]
        cur.executemany(
            """
            INSERT INTO workspaces (name, description, price_per_hour, rating, image_path, currency, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            indian_examples,
        )
        conn.commit()

    conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    user = None
    user_id = session.get("user_id")
    if user_id:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
    # Expose the datetime class to all templates so base.html can call datetime.utcnow()
    return {"current_user": user, "datetime": datetime}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "danger")
            conn.close()
            return redirect(url_for("register"))

        conn.close()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username_or_email = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username_or_email, username_or_email),
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Logged in successfully.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))

        flash("Invalid credentials.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/explore")
def explore():
    conn = get_db_connection()
    workspaces = conn.execute("SELECT * FROM workspaces ORDER BY rating DESC").fetchall()
    conn.close()
    return render_template("explore.html", workspaces=workspaces)


@app.route("/workspace/<int:workspace_id>", methods=["GET", "POST"])
def workspace_detail(workspace_id):
    conn = get_db_connection()
    workspace = conn.execute(
        "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
    ).fetchone()
    # fetch reviews for this workspace with reviewer username
    reviews = conn.execute(
        "SELECT r.*, u.username as username FROM reviews r LEFT JOIN users u ON r.user_id = u.id WHERE r.workspace_id = ? ORDER BY r.created_at DESC",
        (workspace_id,),
    ).fetchall()
    conn.close()
    if workspace is None:
        flash("Workspace not found.", "danger")
        return redirect(url_for("explore"))

    if request.method == "POST":
        if "user_id" not in session:
            flash("Please log in to book a workspace.", "warning")
            return redirect(url_for("login", next=request.path))
        booking_date = request.form.get("booking_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        hours = request.form.get("hours", "1").strip()
        try:
            # validate hours
            hours_int = int(hours)
            if hours_int <= 0:
                raise ValueError
            # validate booking_date format YYYY-MM-DD
            try:
                booking_dt = datetime.strptime(booking_date, "%Y-%m-%d").date()
            except Exception:
                flash("Please enter a valid booking date.", "danger")
                return redirect(url_for("workspace_detail", workspace_id=workspace_id))
        except ValueError:
            flash("Please enter a valid number of hours.", "danger")
            return redirect(url_for("workspace_detail", workspace_id=workspace_id))
        # validate start_time format HH:MM (and ensure minutes are 00 for hourly slots)
        try:
            st = datetime.strptime(start_time, "%H:%M")
            if st.minute != 0:
                raise ValueError("Only hourly start times allowed")
            start_time_val = start_time
        except Exception:
            flash("Please select a valid hourly start time (e.g. 09:00).", "danger")
            return redirect(url_for("workspace_detail", workspace_id=workspace_id))
        total_price = hours_int * workspace["price_per_hour"]
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO bookings (user_id, workspace_id, booking_date, start_time, hours, total_price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                workspace_id,
                booking_date,
                start_time_val,
                hours_int,
                total_price,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        flash("Booking confirmed for {} at {}!".format(booking_date, start_time_val), "success")
        return redirect(url_for("dashboard"))

    return render_template("workspace_detail.html", workspace=workspace, reviews=reviews)


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection()
    bookings = conn.execute(
        """
        SELECT b.*, w.name as workspace_name, w.price_per_hour, w.rating
        FROM bookings b
        JOIN workspaces w ON b.workspace_id = w.id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return render_template("dashboard.html", bookings=bookings)


@app.route("/workspace/<int:workspace_id>/review", methods=["POST"])
@login_required
def submit_review(workspace_id):
    rating = request.form.get("rating", "").strip()
    comment = request.form.get("comment", "").strip()

    try:
        rating_int = int(rating)
        if rating_int < 1 or rating_int > 5:
            raise ValueError
    except Exception:
        flash("Please provide a rating between 1 and 5.", "danger")
        return redirect(url_for("workspace_detail", workspace_id=workspace_id))

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO reviews (user_id, workspace_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
        (session["user_id"], workspace_id, rating_int, comment or None, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

    flash("Thanks for your review!", "success")
    return redirect(url_for("workspace_detail", workspace_id=workspace_id))


@app.route("/workspaces/new", methods=["GET", "POST"])
@login_required
def new_workspace():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        rating = request.form.get("rating", "").strip()
        image_file = request.files.get("image")

        if not name or not price:
            flash("Name and price are required.", "danger")
            return redirect(url_for("new_workspace"))

        try:
            price_val = float(price)
        except ValueError:
            flash("Price must be a number.", "danger")
            return redirect(url_for("new_workspace"))

        rating_val = None
        if rating:
            try:
                rating_val = float(rating)
            except ValueError:
                flash("Rating must be a number.", "danger")
                return redirect(url_for("new_workspace"))

        image_path = None
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                image_file.save(save_path)
                image_path = f"uploads/{filename}"
            else:
                flash("Invalid image type.", "danger")
                return redirect(url_for("new_workspace"))

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO workspaces (name, description, price_per_hour, rating, image_path, owner_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                description,
                price_val,
                rating_val,
                image_path,
                session["user_id"],
            ),
        )
        conn.commit()
        conn.close()
        flash("Workspace added successfully.", "success")
        return redirect(url_for("explore"))

    return render_template("new_workspace.html")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # Optional direct serving route if needed
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
