from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask import Flask, render_template, redirect, url_for, flash, request ,jsonify
from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect
import os


app = Flask(__name__)
babel = Babel(app)
csrf = CSRFProtect(app)

# Flask app configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Initialize the SQLAlchemy part of the app instance
db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

# Database models
class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    phone_number = db.Column(db.String(1000), unique=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(100))
    done = db.Column(db.String(100))
    date = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(255))
    done = db.Column(db.String(3), default='no')
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    task_relation = db.relationship('Task', backref='subtasks')  # Relationship to Task

    def __repr__(self):
        return f'<Subtask {self.task}>'


# Admin view
class MyModelView(ModelView):
    def is_accessible(self):
        return True

# Create all tables
with app.app_context():
    db.create_all()

# Admin setup
admin = Admin(app)
admin.add_view(MyModelView(Users, db.session))
admin.add_view(MyModelView(Task, db.session))
admin.add_view(MyModelView(Subtask, db.session))

# Function to send task reminder
# def send_task_reminder(task, user):
#     msg = Message(
#         subject=f"Reminder: {task.task}",
#         recipients=[user.email],
#         sender=app.config['MAIL_DEFAULT_SENDER']  # Explicitly specifying the sender
#     )
#     msg.body = f"Hello {user.name}, do not forget you have a task: {task.task}."
#     mail.send(msg)

@app.route("/", methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = Users.query.filter_by(email=email).first()
        if user and user.password == password:
            login_user(user)
            return redirect("/dashboard")
        else:
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))
    return render_template("login.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone_number = request.form.get('phone')
        password = request.form.get('password')

        existing_user = Users.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered!')
            return redirect(url_for('register'))

        new_user = Users(
            name=name,
            email=email,
            phone_number=phone_number,
            password=password,
        )

        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Registration successful!')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route("/dashboard", methods=['GET', 'POST'])
@login_required
def dashboard():
    offset = request.args.get('offset', 0, type=int)
    today = datetime.utcnow().date()
    target_date = today + timedelta(days=offset)
    target_date_str = target_date.strftime('%Y-%m-%d')

    if offset == 0:
        # Show tasks scheduled for today and overdue tasks
        tasks = Task.query.filter(
            (Task.user_id == current_user.id) &
            ((Task.date == target_date_str) | (Task.date < today.strftime('%Y-%m-%d')) & (Task.done == 'no'))
        ).all()
    else:
        # Show tasks scheduled for the target_date and overdue tasks
        tasks = Task.query.filter(
            (Task.user_id == current_user.id) &
            ((Task.date == target_date_str) | (Task.date < today.strftime('%Y-%m-%d')) & (Task.done == 'no'))
        ).all()

    subtasks = Subtask.query.all()
    current_date = datetime.now().date()

    # Convert task dates from string to date objects for comparison
    for task in tasks:
        task.date = datetime.strptime(task.date, '%Y-%m-%d').date()

    return render_template('dashboard.html', tasks=tasks, subtasks=subtasks, offset=offset, current_date=current_date)



@app.route("/add_task", methods=['POST'])
@login_required
def add_task():
    task_content = request.form.get('task')
    task_date = request.form.get('date')
    done = "no"
    new_task = Task(task=task_content, date=task_date, done=done ,user_id=current_user.id)
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route("/edit_task", methods=['POST'])
@login_required
def edit_task():
    task_id = request.form.get('task_id')
    task = Task.query.get(task_id)
    task.task = request.form.get('task')
    task.date = request.form.get('date')
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route("/delete_task/<int:task_id>", methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route("/add_subtask", methods=['POST'])
@login_required
def add_subtask():
    subtask_content = request.form.get('task')
    parent_task_id = request.form.get('task_id')
    new_subtask = Subtask(task=subtask_content, task_id=parent_task_id)
    db.session.add(new_subtask)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route("/edit_subtask", methods=['POST'])
@login_required
def edit_subtask():
    subtask_id = request.form.get('subtask_id')
    subtask = Subtask.query.get(subtask_id)
    subtask.task = request.form.get('task')
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route("/delete_subtask/<int:subtask_id>", methods=['POST'])
@login_required
def delete_subtask(subtask_id):
    subtask = Subtask.query.get(subtask_id)
    db.session.delete(subtask)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/update_task_status', methods=['POST'])
@csrf.exempt  # Exempt CSRF protection for API routes if necessary
def update_task_status():
    try:
        task_id = request.form.get('task_id')
        done = request.form.get('done')

        # Validate input
        if not task_id or done not in ['yes', 'no']:
            return jsonify({'success': False, 'message': 'Invalid input'}), 400

        # Fetch the task from the database
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404

        # Update the task status
        task.done = done
        db.session.commit()

        # Update all related subtasks when the task is marked as done
        if done == 'yes':
            Subtask.query.filter_by(task_id=task_id).update({'done': 'yes'})
            db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        # Log the exception and return a failure response
        app.logger.error(f'Error updating task status: {e}')
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


@app.route('/update_subtask_status', methods=['POST'])
@csrf.exempt  # Exempt CSRF protection for API routes if necessary
def update_subtask_status():
    try:
        subtask_id = request.form.get('subtask_id')
        done = request.form.get('done')

        # Validate input
        if not subtask_id or done not in ['yes', 'no']:
            return jsonify({'success': False, 'message': 'Invalid input'}), 400

        # Fetch the subtask from the database
        subtask = Subtask.query.get(subtask_id)
        if not subtask:
            return jsonify({'success': False, 'message': 'Subtask not found'}), 404

        # Fetch the parent task
        parent_task = Task.query.get(subtask.task_id)
        if parent_task.done == 'yes':
            return jsonify({'success': False, 'message': 'Cannot update subtasks of a completed task'}), 403

        # Update the subtask status
        subtask.done = done
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        # Log the exception and return a failure response
        app.logger.error(f'Error updating subtask status: {e}')
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


if __name__ == "__main__":
    app.run(debug=True)
