import os, json, traceback
from datetime import datetime
from flask import Flask, render_template, request, redirect, flash, url_for, send_from_directory
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed")

# Database Configuration
database_url = os.getenv("STORAGE_URL") or os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")

if database_url:
    # Handle the postgresql protocol for pg8000
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+pg8000://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+pg8000://", 1)
    
    # Remove sslmode if it exists in the URL, as pg8000 handles it differently
    if "sslmode=" in database_url:
        import re
        database_url = re.sub(r'[\?&]sslmode=[^&]*', '', database_url)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Connection pooling settings for serverless environments
# We remove pool_pre_ping if it's causing issues with certain drivers, 
# but generally it's safe for pg8000.
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
}

db = SQLAlchemy(app)

# Mail Configuration
app.config.update(
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "true").lower() == "true",
    MAIL_USE_SSL=os.getenv("MAIL_USE_SSL", "false").lower() == "true",
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME")),
)

mail = Mail(app)
RECIPIENT = os.getenv("MAIL_RECIPIENT", "jmwanguwe3@gmail.com")

# Database Model
class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp_utc = db.Column(db.DateTime, default=datetime.utcnow)

@app.before_request
def create_tables():
    if not hasattr(app, '_db_initialized'):
        if app.config['SQLALCHEMY_DATABASE_URI']:
            try:
                db.create_all()
                app._db_initialized = True
            except Exception as e:
                print(f"Database init error: {e}")

@app.route("/")
def my_home():
    tech_stack = ["TypeScript", "JavaScript", "HTML", "Python", "Java", "CSS"]
    return render_template("index.html", tech_stack=tech_stack)

@app.route("/static/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/x-icon')

@app.route("/send", methods=["POST"])
def send_email():
    name    = request.form.get("name")
    email   = request.form.get("email")
    message = request.form.get("message")

    if not all([name, email, message]):
        flash("Please fill in every field.", "danger")
        return redirect(url_for("my_home") + "#section_5")

    db_success = False
    db_error = ""
    if app.config['SQLALCHEMY_DATABASE_URI']:
        try:
            new_msg = ContactMessage(name=name, email=email, message=message)
            db.session.add(new_msg)
            db.session.commit()
            db_success = True
        except Exception as exc:
            db_error = str(exc)
            print(f"Database error: {db_error}")
            db.session.rollback()

    email_success = False
    email_error = ""
    try:
        # Check for credentials before attempting to send
        if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
            raise Exception("Email credentials missing in Vercel environment variables.")

        msg = Message(
            subject   = f"Portfolio Contact | {name}",
            sender    = app.config.get("MAIL_DEFAULT_SENDER"),
            recipients = [RECIPIENT],
            reply_to  = email,
            body      = f"Name: {name}\nEmail: {email}\n\n{message}"
        )
        mail.send(msg)
        email_success = True
    except Exception as exc:
        email_error = str(exc)
        print(f"Email error: {email_error}")

    if email_success and db_success:
        flash("Thanks! Your message has been sent and saved ✔", "success")
    elif email_success:
        flash(f"Message sent! (Database storage had a minor issue, but I received your email) ✔", "warning")
    elif db_success:
        flash(f"Message saved! (Email failed to send, but I'll see it in my database) ✔", "warning")
    else:
        # Both failed - provide a cleaner error message
        flash("Sorry, there was a temporary error. Please try again in a few minutes.", "danger")
        print(f"DEBUG - DB: {db_error} | Email: {email_error}")

    return redirect(url_for("my_home") + "#section_5")

if __name__ == "__main__":
    app.run(debug=True)
