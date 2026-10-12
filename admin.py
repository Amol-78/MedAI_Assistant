from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import json, os, uuid, string, random
from werkzeug.utils import secure_filename
from models import db, Doctor, PatientReport, DoctorRequest, Admin, Appointment, Feedback, Patient

admin_bp = Blueprint('admin', __name__)

def save_doctor_picture(file_obj):
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

ALLOWED_SPECIALIZATIONS = [
"Cardiologist", "Neurologist", "Dermatologist", "Orthopedic",
"General Physician", "Pediatrician", "ENT Specialist","Gastroenterologist", 
"Pulmonologist","Endocrinologist", "Psychiatrist","opthalmologist" ,"Oncologist",
"Rheumatologist", "Nephrologist", "Urologist", "Gynecologist", "Hematologist",
"Infectious Disease Specialist", "Allergist/Immunologist", "Geriatrician", 
"Physical Medicine & Rehabilitation Specialist", "Anesthesiologist","Dentist", 
"Ophthalmologist", "Radiologist", "Pathologist", "Surgeon", "Other"
]

@admin_bp.route('/doctors', methods=['GET'])
@jwt_required()
def get_doctors():
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
    doctors = Doctor.query.all()
    return jsonify([{
        'doctor_id': d.doctor_id,
        'name': d.name,
        'specialization': d.specialization,
        'email': d.email,
        'phone': d.phone,
        'online_treatment_fee': d.online_treatment_fee,
        'available': d.available,
        'profile_picture': d.profile_picture
    } for d in doctors]), 200

@admin_bp.route('/doctor', methods=['POST'])
@jwt_required()
def add_doctor():
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
    
    if request.is_json:
        data = request.get_json() or {}
        pic_file = None
    else:
        data = request.form.to_dict()
        pic_file = request.files.get('profile_picture')

    specialization = data.get('specialization', '').strip()
    # Case-insensitive or flexible check
    matched_spec = next((s for s in ALLOWED_SPECIALIZATIONS if s.lower() == specialization.lower()), None)
    if not matched_spec:
        matched_spec = specialization or "General Physician"
    
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    if Doctor.query.filter_by(email=email).first() or Doctor.query.filter_by(phone=phone).first():
        return jsonify({'msg': 'Doctor with this email/phone already exists'}), 400

    pic_filename = save_doctor_picture(pic_file)

    raw_fee = data.get('online_treatment_fee') or data.get('fee') or data.get('consultation_fee')
    try:
        parsed_fee = int(float(raw_fee)) if raw_fee is not None and str(raw_fee).strip() != '' else 500
    except (ValueError, TypeError):
        parsed_fee = 500

    doctor = Doctor(
        name=data.get('name', '').strip(),
        age=int(data.get('age', 35)) if data.get('age') else 35,
        gender=data.get('gender', 'Other'),
        education=data.get('education', '').strip(),
        experience_years=int(data.get('experience_years', 0)) if data.get('experience_years') else 0,
        specialization=matched_spec,
        online_treatment_fee=parsed_fee,
        email=email,
        phone=phone,
        profile_picture=pic_filename
    )
    doctor.set_password(data.get('password', 'password123'))  # default password, can be changed later
    db.session.add(doctor)
    db.session.commit()
    return jsonify({'msg': 'Doctor added successfully'}), 201

@admin_bp.route('/doctor/<int:doctor_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def manage_doctor(doctor_id):
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
    doctor = Doctor.query.get_or_404(doctor_id)
    if request.method == 'DELETE':
        db.session.delete(doctor)
        db.session.commit()
        return jsonify({'msg': 'Doctor deleted'}), 200
    else:  # PUT
        data = request.get_json()
        if 'specialization' in data and data['specialization'] not in ALLOWED_SPECIALIZATIONS:
            return jsonify({'msg': 'Invalid specialization'}), 400
        for key, value in data.items():
            if hasattr(doctor, key) and key not in ['doctor_id', 'password_hash', 'created_at']:
                setattr(doctor, key, value)
        db.session.commit()
        return jsonify({'msg': 'Doctor updated'}), 200

@admin_bp.route('/reports', methods=['GET'])
@jwt_required()
def view_reports():
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
    reports = PatientReport.query.all()
    # Return reports with patient details etc.
    return jsonify([{
        'report_id': r.report_id,
        'patient_id': r.patient_id,
        'symptoms': r.symptoms_text,
        'severity': r.severity_level,
        'status': r.status
    } for r in reports]), 200

@admin_bp.route('/doctor_requests', methods=['GET'])
@jwt_required()
def get_requests():
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
    requests = DoctorRequest.query.filter_by(status='pending').all()
    return jsonify([{
        'request_id': r.request_id,
        'name': r.name,
        'age': r.age,
        'gender': r.gender,
        'email': r.email,
        'phone': r.phone,
        'education': r.education,
        'experience_years': r.experience_years,
        'specialization': r.specialization,
        'online_treatment_fee': r.online_treatment_fee,
        'profile_picture': r.profile_picture,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
    } for r in requests]), 200

@admin_bp.route('/approve_request/<int:req_id>', methods=['POST'])
@jwt_required()
def approve_request(req_id):
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
    req = DoctorRequest.query.get_or_404(req_id)
    if req.status != 'pending':
        return jsonify({'msg': 'Request already processed'}), 400
        
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    doctor = Doctor(
        name=req.name,
        age=req.age or 30,
        gender=req.gender or 'Other',
        education=req.education,
        experience_years=req.experience_years,
        specialization=req.specialization,
        online_treatment_fee=req.online_treatment_fee if req.online_treatment_fee is not None else 500,
        email=req.email,
        phone=req.phone,
        profile_picture=req.profile_picture
    )
    if req.password_hash:
        doctor.password_hash = req.password_hash
        password_to_show = "(Password set by doctor during request)"
    else:
        doctor.set_password(temp_password)
        password_to_show = temp_password

    db.session.add(doctor)
    req.status = 'approved'
    db.session.commit()
    
    return jsonify({
        'msg': 'Doctor approved.',
        'temp_password': password_to_show,
        'email': req.email
    }), 200

@admin_bp.route('/reject_request/<int:req_id>', methods=['POST'])
@jwt_required()
def reject_request(req_id):
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
    req = DoctorRequest.query.get_or_404(req_id)
    req.status = 'rejected'
    db.session.commit()
    return jsonify({'msg': 'Request rejected'}), 200

@admin_bp.route('/add_admin', methods=['POST'])
@jwt_required()
def add_admin():
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin' or not identity.get('is_super_admin', False):
        return jsonify({'msg': 'Unauthorized. Only Super Admin can perform this action.'}), 403
    
    data = request.get_json()
    if Admin.query.filter_by(email=data['email']).first() or Admin.query.filter_by(phone=data['phone']).first():
        return jsonify({'msg': 'Admin with this email/phone already exists'}), 400
        
    admin = Admin(
        name=data['name'],
        gender=data.get('gender', 'Other'),
        email=data['email'],
        phone=data['phone']
    )
    admin.set_password(data['password'])
    db.session.add(admin)
    db.session.commit()
    return jsonify({'msg': 'Admin successfully created'}), 201

@admin_bp.route('/doctor_profile/<int:doctor_id>', methods=['GET'])
@jwt_required()
def doctor_profile(doctor_id):
    identity = json.loads(get_jwt_identity())
    if identity['role'] != 'admin':
        return jsonify({'msg': 'Unauthorized'}), 403
        
    doctor = Doctor.query.get_or_404(doctor_id)
    
    # Work Summary
    reports = PatientReport.query.filter_by(assigned_doctor_id=doctor_id).all()
    total_assigned = len(reports)
    total_completed = sum(1 for r in reports if r.status == 'Completed')
    total_pending = sum(1 for r in reports if r.status == 'pending')
    
    # Case Progress List
    cases_handled = []
    for r in reports:
        patient = Patient.query.get(r.patient_id)
        patient_name = patient.name if patient else "Unknown"
        cases_handled.append({
            'report_id': r.report_id,
            'patient_name': patient_name,
            'symptoms': r.symptoms_text[:100] + '...' if len(r.symptoms_text) > 100 else r.symptoms_text,
            'status': r.status,
            'date': r.created_at.strftime('%Y-%m-%d %H:%M')
        })
        
    cases_handled.sort(key=lambda x: x['date'], reverse=True)
    
    # Feedback & Ratings
    feedbacks = Feedback.query.filter_by(doctor_id=doctor_id).all()
    total_reviews = len(feedbacks)
    average_rating = round(sum(f.rating for f in feedbacks) / total_reviews, 1) if total_reviews > 0 else 0
    
    feedback_list = []
    for f in feedbacks:
        feedback_list.append({
            'rating': f.rating,
            'comment': f.comment if f.comment else "",
            'date': f.created_at.strftime('%Y-%m-%d')
        })
        
    feedback_list.sort(key=lambda x: x['date'], reverse=True)
    
    return jsonify({
        'doctor_info': {
            'name': doctor.name,
            'specialization': doctor.specialization,
            'education': doctor.education,
            'experience': doctor.experience_years,
            'email': doctor.email,
            'phone': doctor.phone,
            'profile_picture': doctor.profile_picture
        },
        'work_summary': {
            'total_assigned': total_assigned,
            'total_completed': total_completed,
            'total_pending': total_pending
        },
        'cases': cases_handled,
        'feedback_stats': {
            'average_rating': average_rating,
            'total_reviews': total_reviews
        },
        'feedbacks': feedback_list
    }), 200