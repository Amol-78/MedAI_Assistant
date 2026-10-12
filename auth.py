from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token
from models import db, Patient, Doctor, Admin, DoctorRequest, bcrypt
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename
import json, os, uuid

auth_bp = Blueprint('auth', __name__)

def save_profile_picture(file_obj):
    if not file_obj or not file_obj.filename:
        return None
    ext = file_obj.filename.rsplit('.', 1)[-1].lower() if '.' in file_obj.filename else ''
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
    if ext not in allowed:
        return None
    clean_name = secure_filename(file_obj.filename)
    filename = f"doc_{uuid.uuid4().hex[:10]}_{clean_name}"
    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file_obj.save(os.path.join(upload_dir, filename))
    return filename

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    identifier = data.get('identifier', '').strip()  # email or phone
    password = data.get('password')
    role = data.get('role')  # 'patient', 'doctor', 'admin'

    user = None
    if role == 'patient':
        user = Patient.query.filter((Patient.email == identifier) | (Patient.phone == identifier)).first()
    elif role == 'doctor':
        user = Doctor.query.filter((Doctor.email == identifier) | (Doctor.phone == identifier)).first()
    elif role == 'admin':
        user = Admin.query.filter((Admin.email == identifier) | (Admin.phone == identifier)).first()

    if user and bcrypt.check_password_hash(user.password_hash, password):
        identity_payload = {'id': getattr(user, f'{role}_id'), 'role': role}
        
        is_super = False
        # Inject Super Admin flag into JWT payload explicitly
        if role == 'admin' and getattr(user, 'is_super_admin', False):
            identity_payload['is_super_admin'] = True
            is_super = True
            
        identity_str = json.dumps(identity_payload)
        access_token = create_access_token(identity=identity_str, expires_delta=timedelta(days=1))
        return jsonify(access_token=access_token, role=role, is_super_admin=is_super), 200
    return jsonify({'msg': 'Invalid credentials'}), 401

@auth_bp.route('/register/patient', methods=['POST'])
def register_patient():
    data = request.get_json()
    # Validate required fields
    if Patient.query.filter_by(email=data['email']).first() or Patient.query.filter_by(phone=data['phone']).first():
        return jsonify({'msg': 'Email or phone already exists'}), 400
    patient = Patient(
        name=data['name'],
        age=data['age'],
        gender=data['gender'],
        email=data['email'],
        phone=data['phone']
    )
    patient.set_password(data['password'])
    db.session.add(patient)
    db.session.commit()
    return jsonify({'msg': 'Patient registered successfully'}), 201

@auth_bp.route('/request_doctor', methods=['POST'])
def request_doctor():
    # Handle both multipart/form-data and JSON
    if request.is_json:
        data = request.get_json() or {}
        pic_file = None
    else:
        data = request.form.to_dict()
        pic_file = request.files.get('profile_picture')

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    education = data.get('education', '').strip()
    specialization = data.get('specialization', '').strip()
    
    if not name or not email or not phone or not specialization:
        return jsonify({'msg': 'Please provide all required fields.'}), 400

    if DoctorRequest.query.filter_by(email=email).first() or Doctor.query.filter_by(email=email).first():
        return jsonify({'msg': 'Email already registered or requested'}), 400
    if DoctorRequest.query.filter_by(phone=phone).first() or Doctor.query.filter_by(phone=phone).first():
        return jsonify({'msg': 'Phone already registered or requested'}), 400

    pic_filename = save_profile_picture(pic_file)
    if not pic_filename and not request.is_json and pic_file:
        return jsonify({'msg': 'Invalid image format. Allowed formats: PNG, JPG, JPEG, WEBP.'}), 400

    raw_fee = data.get('online_treatment_fee') or data.get('fee') or data.get('consultation_fee')
    try:
        parsed_fee = int(float(raw_fee)) if raw_fee is not None and str(raw_fee).strip() != '' else 500
    except (ValueError, TypeError):
        parsed_fee = 500

    doc_req = DoctorRequest(
        name=name,
        age=int(data.get('age', 30)) if data.get('age') else None,
        gender=data.get('gender', 'Other'),
        email=email,
        phone=phone,
        education=education,
        experience_years=int(data.get('experience_years', 0)) if data.get('experience_years') else 0,
        specialization=specialization,
        online_treatment_fee=parsed_fee,
        profile_picture=pic_filename
    )
    
    password = data.get('password')
    if password:
        doc_req.set_password(password)

    db.session.add(doc_req)
    db.session.commit()
    return jsonify({'msg': 'Verification request submitted successfully'}), 201