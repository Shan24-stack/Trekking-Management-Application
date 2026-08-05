from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database import db
from models.models import User, Trek, Booking, Admin, Staff

from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask import session

from datetime import datetime

app = Flask(__name__)

# Database Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///trek.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "trek-secret-key"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):

    role, id = user_id.split(":")

    if role == "user":
        return User.query.get(int(id))

    elif role == "staff":
        return Staff.query.get(int(id))

    elif role == "admin":
        return Admin.query.get(int(id))

    return None


@app.route("/create_admin")
def create_admin():

    if not Admin.query.filter_by(email="admin@trek.com").first():

        admin = Admin(
            fullname="System Admin",
            email="admin@trek.com",
            password=generate_password_hash("admin123")
        )

        db.session.add(admin)
        db.session.commit()

    return "Admin Created"


@app.route("/")
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        # Check Admin table
        admin = Admin.query.filter_by(email=email).first()

        if admin and check_password_hash(admin.password, password):
            login_user(admin)
            flash("Admin Login Successful!", "success")
            return redirect(url_for("admin_dashboard"))

        # Check Staff table
        staff = Staff.query.filter_by(email=email).first()

        if staff and check_password_hash(staff.password, password):

            if staff.is_blacklisted:
                flash("Your account has been blacklisted. Contact the administrator.", "danger")
                return redirect(url_for("login"))

            if not staff.is_approved:
                flash("Your account is pending admin approval.", "warning")
                return redirect(url_for("login"))

            login_user(staff)
            flash("Staff Login Successful!", "success")
            return redirect(url_for("staff_dashboard"))

        # Check User table
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            if user.status == "inactive":
                flash("Your account has been deactivated by the administrator.", "danger")
                return redirect(url_for("login"))

            login_user(user)
            flash("User Login Successful!", "success")
            return redirect(url_for("user_dashboard"))

        flash("Invalid Email or Password.", "danger")

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]
        new_password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("forgot_password"))

        # Check Admin
        admin = Admin.query.filter_by(email=email).first()

        if admin:
            admin.password = generate_password_hash(new_password)
            db.session.commit()

            flash("Password updated successfully. Please login.", "success")
            return redirect(url_for("login"))

        # Check Staff
        staff = Staff.query.filter_by(email=email).first()

        if staff:
            staff.password = generate_password_hash(new_password)
            db.session.commit()

            flash("Password updated successfully. Please login.", "success")
            return redirect(url_for("login"))

        # Check User
        user = User.query.filter_by(email=email).first()

        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()

            flash("Password updated successfully. Please login.", "success")
            return redirect(url_for("login"))

        flash("Email not found.", "danger")

    return render_template("forgot_password.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        phone_number = request.form["phone_number"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        role = request.form["role"]

        # Password validation
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        # Check email in User table
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        # Check email in Staff table
        if Staff.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        if role == "user":

            new_user = User(
                fullname=fullname,
                phone_number=phone_number,
                email=email,
                password=hashed_password,
                role="user",
                status="active",
                is_approved=False
            )

            db.session.add(new_user)

        elif role == "staff":

            new_staff = Staff(
                fullname=fullname,
                phone_number=phone_number,
                email=email,
                password=hashed_password,
                is_approved=False,
                is_blacklisted=False
            )

            db.session.add(new_staff)

        else:
            flash("Please select a valid role.", "danger")
            return redirect(url_for("register"))

        db.session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/admin/dashboard")
@login_required
def admin_dashboard():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    total_treks = Trek.query.count()
    total_users = User.query.count()
    total_staff = Staff.query.count()
    total_bookings = Booking.query.count()

    bookings = Booking.query.order_by(
        Booking.id.desc()
    ).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_treks=total_treks,
        total_users=total_users,
        total_staff=total_staff,
        total_bookings=total_bookings,
        bookings=bookings
    )

@app.route("/admin/treks")
@login_required
def treks():

    if not isinstance(current_user, Admin):
        flash("Access Denied", "danger")
        return redirect(url_for("login"))

    treks = Trek.query.all()

    return render_template("admin/treks.html", treks=treks)

@app.route("/admin/treks/add", methods=["GET", "POST"])
@login_required
def add_trek():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        location = request.form["location"]
        difficulty = request.form["difficulty"]
        duration = request.form["duration"]
        status = request.form["status"]

        total_slots = int(request.form["total_slots"])
        available_slots = total_slots

        start_date = datetime.strptime(
           request.form["start_date"], "%Y-%m-%d"
        ).date()

        end_date = datetime.strptime(
           request.form["end_date"], "%Y-%m-%d"
        ).date()

        if end_date < start_date:
            flash("End date cannot be earlier than the start date.", "danger")
            return redirect(url_for("add_trek"))

        assigned_staff_id = request.form.get("assigned_staff_id")

        if assigned_staff_id:
            assigned_staff_id = int(assigned_staff_id)
        else:
            assigned_staff_id = None

        price = float(request.form["price"])

        if total_slots <= 0:
            flash("Total slots must be greater than 0.", "danger")
            return redirect(url_for("add_trek"))

        if price <= 0:
            flash("Price must be greater than 0.", "danger")
            return redirect(url_for("add_trek"))
    
        trek = Trek(
            name=name,
            description=description,
            location=location,
            difficulty=difficulty,
            duration=duration,
            total_slots=total_slots,
            available_slots=available_slots,
            assigned_staff_id=assigned_staff_id,
            start_date=start_date,
            end_date=end_date,
            price=price,
            status=status
        )

        try:
            db.session.add(trek)
            db.session.commit()

            flash("Trek added successfully!", "success")
        
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")

        return redirect(url_for("treks"))
        

    staff_members = Staff.query.filter_by(
        is_approved=True,
        is_blacklisted=False
    ).all()

    return render_template(
        "admin/add_trek.html",
        staff_members=staff_members
)

@app.route("/admin/treks/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_trek(id):

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(id)

    staff_members = Staff.query.filter_by(
        is_approved=True,
        is_blacklisted=False
    ).all()

    if request.method == "POST":

        trek.name = request.form["name"]
        trek.description = request.form["description"]
        trek.location = request.form["location"]
        trek.difficulty = request.form["difficulty"]
        trek.duration = request.form["duration"]
        trek.status = request.form["status"]

        trek.total_slots = int(request.form["total_slots"])

        trek.assigned_staff_id = request.form.get("assigned_staff_id")

        if trek.assigned_staff_id == "":
            trek.assigned_staff_id = None
        else:
            trek.assigned_staff_id = int(trek.assigned_staff_id)

        trek.start_date = datetime.strptime(
            request.form["start_date"],
            "%Y-%m-%d"
        ).date()

        trek.end_date = datetime.strptime(
            request.form["end_date"],
            "%Y-%m-%d"
        ).date()

        if trek.end_date < trek.start_date:
            flash("End date cannot be earlier than Start date.", "danger")
            return redirect(url_for("edit_trek", id=id))

        trek.price = float(request.form["price"])

        try:

            db.session.commit()

            flash("Trek updated successfully!", "success")

            return redirect(url_for("treks"))

        except Exception as e:

            db.session.rollback()

            flash("Unable to update trek.", "danger")

            print(e)

    return render_template(
        "admin/edit_trek.html",
        trek=trek,
        staff_members=staff_members
    )

@app.route("/admin/treks/delete/<int:id>")
@login_required
def delete_trek(id):

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(id)

    # Check whether bookings exist
    if trek.bookings:
        flash("Delete not allowed. This trek has existing bookings. Cancel all bookings first.", "warning")
        return redirect(url_for("treks"))

    db.session.delete(trek)
    db.session.commit()

    flash("Trek deleted successfully!", "success")

    return redirect(url_for("treks"))

@app.route("/admin/staff")
@login_required
def staff_list():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    staff_members = Staff.query.all()

    pending_count = Staff.query.filter_by(
        is_approved=False,
        is_blacklisted=False
    ).count()

    approved_count = Staff.query.filter_by(
        is_approved=True,
        is_blacklisted=False
    ).count()

    blacklisted_count = Staff.query.filter_by(
        is_blacklisted=True
    ).count()

    return render_template(
        "admin/staff.html",
        staff_members=staff_members,
        pending_count=pending_count,
        approved_count=approved_count,
        blacklisted_count=blacklisted_count
    )

@app.route("/admin/staff/approve/<int:id>")
@login_required
def approve_staff(id):

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    staff = Staff.query.get_or_404(id)

    staff.is_approved = True
    staff.is_blacklisted = False

    db.session.commit()

    flash("Staff approved successfully!", "success")

    return redirect(url_for("staff_list"))

@app.route("/admin/staff/reject/<int:id>")
@login_required
def reject_staff(id):

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    staff = Staff.query.get_or_404(id)

    staff.is_approved = False
    staff.is_blacklisted = True

    db.session.commit()

    flash("Staff has been blacklisted.", "warning")

    return redirect(url_for("staff_list"))

@app.route("/admin/staff/blacklist/<int:id>")
@login_required
def blacklist_staff(id):

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    staff = Staff.query.get_or_404(id)

    staff.is_blacklisted = True

    db.session.commit()

    flash("Staff has been blacklisted successfully.", "success")

    return redirect(url_for("staff_list"))

@app.route("/admin/users")
@login_required
def manage_users():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    users = User.query.order_by(User.id).all()

    total_users = User.query.count()
    active_users = User.query.filter_by(status="active").count()
    inactive_users = User.query.filter_by(status="inactive").count()

    return render_template(
        "admin/users.html",
        users=users,
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users
    )

@app.route("/admin/users/deactivate/<int:id>")
@login_required
def deactivate_user(id):

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    user = User.query.get_or_404(id)

    user.status = "inactive"

    db.session.commit()

    flash("User deactivated successfully.", "success")

    return redirect(url_for("manage_users"))

@app.route("/admin/bookings")
@login_required
def manage_bookings():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    bookings = Booking.query.order_by(
        Booking.booking_date.desc()
    ).all()

    total_bookings = Booking.query.count()

    confirmed = Booking.query.filter_by(
        status="confirmed"
    ).count()

    pending = Booking.query.filter_by(
        status="pending"
    ).count()

    cancelled = Booking.query.filter_by(
        status="cancelled"
    ).count()

    return render_template(
        "admin/bookings.html",
        bookings=bookings,
        total_bookings=total_bookings,
        confirmed=confirmed,
        pending=pending,
        cancelled=cancelled
    )

@app.route("/admin/reports")
@login_required
def reports():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    total_users = User.query.count()
    total_staff = Staff.query.count()
    total_treks = Trek.query.count()
    total_bookings = Booking.query.count()

    open_treks = Trek.query.filter_by(status="Open").count()
    closed_treks = Trek.query.filter_by(status="Closed").count()

    return render_template(
        "admin/reports.html",
        total_users=total_users,
        total_staff=total_staff,
        total_treks=total_treks,
        total_bookings=total_bookings,
        open_treks=open_treks,
        closed_treks=closed_treks
    )

@app.route("/admin/search", methods=["GET"])
@login_required
def admin_search():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    query = request.args.get("query", "").strip()

    users = []
    staff = []
    treks = []

    if query:

        users = User.query.filter(
            User.fullname.ilike(f"%{query}%")
        ).all()

        staff = Staff.query.filter(
            Staff.fullname.ilike(f"%{query}%")
        ).all()

        treks = Trek.query.filter(
            Trek.name.ilike(f"%{query}%")
        ).all()

    return render_template(
        "admin/search.html",
        query=query,
        users=users,
        staff=staff,
        treks=treks
    )

@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():

    if not isinstance(current_user, Admin):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":

        fullname = request.form["fullname"]
        password = request.form["password"]

        current_user.fullname = fullname

        if password.strip():
            current_user.password = generate_password_hash(password)

        db.session.commit()

        flash("Settings updated successfully!", "success")

        return redirect(url_for("admin_settings"))

    return render_template("admin/settings.html")


@app.route("/staff/dashboard")
@login_required
def staff_dashboard():

    if not isinstance(current_user, Staff):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    assigned_treks = Trek.query.filter_by(
        assigned_staff_id=current_user.id
    ).all()

    total_treks = len(assigned_treks)

    upcoming_treks = Trek.query.filter(
        Trek.assigned_staff_id == current_user.id,
        Trek.status == "Upcoming"
    ).count()

    completed_treks = Trek.query.filter(
        Trek.assigned_staff_id == current_user.id,
        Trek.status == "Completed"
    ).count()

    return render_template(
        "staff/dashboard.html",
        assigned_treks=assigned_treks,
        total_treks=total_treks,
        upcoming_treks=upcoming_treks,
        completed_treks=completed_treks
    )

@app.route("/staff/my_treks")
@login_required
def my_treks():

    if not isinstance(current_user, Staff):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    treks = Trek.query.filter_by(
        assigned_staff_id=current_user.id
    ).all()

    return render_template(
        "staff/my_treks.html",
        treks=treks
    )

@app.route("/staff/trek/<int:trek_id>")
@login_required
def staff_trek_details(trek_id):

    if not isinstance(current_user, Staff):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(trek_id)

    # Ensure staff can only view their own assigned treks
    if trek.assigned_staff_id != current_user.id:
        flash("You are not authorized to view this trek.", "danger")
        return redirect(url_for("my_treks"))

    return render_template(
        "staff/trek_details.html",
        trek=trek
    )

@app.route("/staff/trek/<int:trek_id>/participants")
@login_required
def staff_participants(trek_id):

    if not isinstance(current_user, Staff):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(trek_id)

    if trek.assigned_staff_id != current_user.id:
        flash("You are not authorized to view participants.", "danger")
        return redirect(url_for("my_treks"))

    bookings = Booking.query.filter_by(
        trek_id=trek.id
    ).all()

    return render_template(
        "staff/participants.html",
        trek=trek,
        bookings=bookings
    )

@app.route("/staff/trek/<int:trek_id>/edit", methods=["GET", "POST"])
@login_required
def staff_edit_trek(trek_id):

    if not isinstance(current_user, Staff):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(trek_id)

    if trek.assigned_staff_id != current_user.id:
        flash("You can only manage your assigned treks.", "danger")
        return redirect(url_for("my_treks"))

    if request.method == "POST":

        trek.available_slots = int(request.form["available_slots"])
        trek.status = request.form["status"]

        db.session.commit()

        flash("Trek updated successfully!", "success")

        return redirect(url_for("my_treks"))

    return render_template(
        "staff/edit_trek.html",
        trek=trek
    )

@app.route("/staff/profile", methods=["GET", "POST"])
@login_required
def staff_profile():

    if not isinstance(current_user, Staff):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":

        current_user.fullname = request.form["fullname"]
        current_user.phone_number = request.form["phone_number"]

        password = request.form["password"]

        if password.strip():
            current_user.password = generate_password_hash(password)

        db.session.commit()

        flash("Profile updated successfully!", "success")

        return redirect(url_for("staff_profile"))

    return render_template("staff/profile.html")


@app.route("/user/dashboard")
@login_required
def user_dashboard():

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    available_treks = Trek.query.filter_by(status="Open").count()

    my_bookings = Booking.query.filter_by(
        user_id=current_user.id
    ).count()

    upcoming_bookings = Booking.query.join(Trek).filter(
        Booking.user_id == current_user.id,
        Trek.status == "Upcoming"
    ).count()

    latest_treks = Trek.query.filter_by(
        status="Open"
    ).order_by(Trek.id.desc()).limit(5).all()

    return render_template(
        "user/dashboard.html",
        available_treks=available_treks,
        my_bookings=my_bookings,
        upcoming_bookings=upcoming_bookings,
        latest_treks=latest_treks
    )

@app.route("/user/browse_treks")
@login_required
def browse_treks():

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    treks = Trek.query.filter_by(status="Open").all()

    return render_template(
        "user/browse_treks.html",
        treks=treks
    )

@app.route("/user/trek/<int:trek_id>")
@login_required
def user_trek_details(trek_id):

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(trek_id)

    return render_template(
        "user/trek_details.html",
        trek=trek
    )

@app.route("/user/book/<int:trek_id>")
@login_required
def book_trek(trek_id):

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(trek_id)

    # Check if trek is open
    if trek.status != "Open":
        flash("This trek is currently closed.", "danger")
        return redirect(url_for("user_trek_details", trek_id=trek.id))

    # Check available slots
    if trek.available_slots <= 0:
        flash("No slots available for this trek.", "danger")
        return redirect(url_for("user_trek_details", trek_id=trek.id))

    # Prevent duplicate booking
    existing_booking = Booking.query.filter_by(
        user_id=current_user.id,
        trek_id=trek.id
    ).first()

    if existing_booking:
        flash("You have already booked this trek.", "warning")
        return redirect(url_for("user_trek_details", trek_id=trek.id))

    # Create booking
    booking = Booking(
        user_id=current_user.id,
        trek_id=trek.id,
        status="confirmed"
    )

    db.session.add(booking)

    # Reduce available slots
    trek.available_slots -= 1

    db.session.commit()

    flash("Trek booked successfully!", "success")

    return redirect(url_for("my_bookings"))

@app.route("/user/my_bookings")
@login_required
def my_bookings():

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    bookings = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status != "cancelled"
    ).order_by(Booking.booking_date.desc()).all()

    return render_template(
        "user/my_bookings.html",
        bookings=bookings
    )


@app.route("/user/cancel_booking/<int:booking_id>")
@login_required
def cancel_booking(booking_id):

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    booking = Booking.query.get_or_404(booking_id)

    if booking.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("my_bookings"))

    trek = Trek.query.get(booking.trek_id)

    booking.status = "cancelled"

    trek.available_slots += 1

    db.session.commit()

    flash("Booking cancelled successfully.", "success")

    return redirect(url_for("my_bookings"))

@app.route("/user/history")
@login_required
def trek_history():

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    history = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status.in_(["completed", "cancelled"])
    ).order_by(Booking.booking_date.desc()).all()

    return render_template(
        "user/history.html",
        history=history
    )

@app.route("/user/profile", methods=["GET", "POST"])
@login_required
def user_profile():

    if not isinstance(current_user, User):
        flash("Access Denied!", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":

        current_user.fullname = request.form["fullname"]
        current_user.phone_number = request.form["phone_number"]

        password = request.form["password"]

        if password.strip():
            current_user.password = generate_password_hash(password)

        db.session.commit()

        flash("Profile updated successfully!", "success")

        return redirect(url_for("user_profile"))

    return render_template("user/profile.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)