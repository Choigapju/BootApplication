# app.py
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import os
import pandas as pd
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import re

# .env 파일 로드
load_dotenv()

app = Flask(__name__)
CORS(app)

# 설정
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/bootaplication')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 업로드 폴더 생성
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

# 데이터베이스 모델
class Bootcamp(db.Model):
    __tablename__ = 'bootcamps'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    batch_number = db.Column(db.Integer, nullable=False)
    recruitment_start_date = db.Column(db.Date, nullable=False)
    recruitment_end_date = db.Column(db.Date, nullable=True)
    
    students = db.relationship('Student', backref='bootcamp', lazy=True)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100), nullable=False)
    bootcamp_id = db.Column(db.String(50), db.ForeignKey('bootcamps.id'), nullable=False)
    status = db.Column(db.String(20))
    considering_reason = db.Column(db.Text)
    last_contact_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime)
    batch_number = db.Column(db.Integer, nullable=False)

# 유틸리티 함수
def parse_date(date_str):
    """날짜 문자열을 datetime 객체로 변환"""
    if not date_str or pd.isna(date_str):
        return None
    
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return None

def parse_birthdate(date_str):
    """생년월일 문자열을 date 객체로 변환"""
    if not date_str or pd.isna(date_str):
        return None
    
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

def allowed_file(filename):
    """허용된 파일 확장자 확인"""
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_age(birthdate_str):
    try:
        birthdate = datetime.strptime(birthdate_str, '%Y-%m-%d')
        today = datetime.today()
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    except:
        return None

def process_uploaded_file(file_path, bootcamp_id, batch_number):
    df = pd.read_csv(file_path)
    for _, row in df.iterrows():
        name = str(row['가입 이름']) if '가입 이름' in row else None
        email = str(row['지원서 이메일']) if '지원서 이메일' in row and pd.notna(row['지원서 이메일']) else str(row['가입 이메일'])
        gender = str(row['성별']) if '성별' in row and pd.notna(row['성별']) else None
        # age: int 변환
        try:
            age = int(row['나이']) if '나이' in row and pd.notna(row['나이']) else None
        except:
            age = None
        phone = str(row['가입 연락처']) if '가입 연락처' in row and pd.notna(row['가입 연락처']) else None
        status = str(row['합불상태']) if '합불상태' in row and pd.notna(row['합불상태']) else None
        considering_reason = str(row['지원취소 사유']) if '지원취소 사유' in row and pd.notna(row['지원취소 사유']) else None
        # last_contact_date: 날짜 변환
        last_contact_date = parse_date(row['최초작성일']) if '최초작성일' in row and pd.notna(row['최초작성일']) else None
        notes = None
        updated_at = datetime.now()
        # batch_number: int 변환
        try:
            batch_num = int(batch_number)
        except:
            batch_num = None

        student = Student(
            name=name,
            gender=gender,
            age=age,
            phone=phone,
            email=email,
            bootcamp_id=bootcamp_id,
            status=status,
            considering_reason=considering_reason,
            last_contact_date=last_contact_date,
            notes=notes,
            updated_at=updated_at,
            batch_number=batch_num
        )
        db.session.add(student)
    db.session.commit()

def parse_bootcamp_and_batch_from_filename(filename):
    # 예시: kdt-design-5th_지원서_2025_05_02_11_42_49.csv
    # 부트캠프명: design, 기수: 5
    match = re.search(r'kdt-([a-zA-Z]+)-(\d+)th', filename)
    if match:
        bootcamp_name = match.group(1).lower()
        batch_number = int(match.group(2))
        # DB의 bootcamp_id와 매칭 필요 (예: design -> uxui)
        bootcamp_id_map = {
            'design': 'uxui',
            'frontend': 'frontend',
            'backend': 'backend',
            'ios': 'ios',
            'android': 'android',
            'data': 'data',
            'game': 'game',
            'cloud': 'cloud',
            'ai': 'ai',
            'growth': 'growth',
            'aiw': 'aiw'
        }
        bootcamp_id = bootcamp_id_map.get(bootcamp_name, bootcamp_name)
        return bootcamp_id, batch_number
    return None, None

# API 라우트
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        # 파일명에서 부트캠프명, 기수 추출
        bootcamp_id, batch_number = parse_bootcamp_and_batch_from_filename(file.filename)
        if not bootcamp_id or not batch_number:
            return jsonify({'error': '파일명에서 부트캠프명/기수 추출 실패'}), 400
        process_uploaded_file(filepath, bootcamp_id, batch_number)
        return jsonify({'message': '파일 업로드 및 처리 완료'}), 200
    return jsonify({'error': '허용되지 않는 파일 형식입니다.'}), 400

@app.route('/api/bootcamps', methods=['GET'])
def get_bootcamps():
    """모든 부트캠프 목록 조회"""
    bootcamps = Bootcamp.query.all()
    return jsonify([{
        'id': bc.id,
        'name': bc.name,
        'batch_number': bc.batch_number,
        'recruitment_start_date': bc.recruitment_start_date.isoformat(),
        'recruitment_end_date': bc.recruitment_end_date.isoformat() if bc.recruitment_end_date else None
    } for bc in bootcamps])

@app.route('/api/bootcamps/<bootcamp_id>/batches', methods=['GET'])
def get_bootcamp_batches(bootcamp_id):
    """특정 부트캠프의 기수 목록 조회"""
    batches = db.session.query(Bootcamp.batch_number).filter(
        Bootcamp.id == bootcamp_id
    ).distinct().all()
    
    return jsonify([batch[0] for batch in batches])

@app.route('/api/bootcamps/<bootcamp_id>/batch/<int:batch_number>/students', methods=['GET'])
def get_students_by_bootcamp_and_batch(bootcamp_id, batch_number):
    students = Student.query.filter_by(bootcamp_id=bootcamp_id, batch_number=batch_number).all()
    return jsonify([
        {
            'id': s.id,
            'name': s.name,
            'email': s.email,
            'gender': s.gender,
            'age': s.age,
            'phone': s.phone
        } for s in students
    ])

@app.route('/api/students', methods=['GET'])
def get_all_students():
    """모든 지원자 목록 조회"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = Student.query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    return jsonify({
        'students': [{
            'id': student.id,
            'name': student.name,
            'email': student.email,
            'phone': student.phone,
            'gender': student.gender,
            'birthdate': student.birthdate.isoformat() if student.birthdate else None,
            'application_date': student.application_date.isoformat(),
            'application_status': student.application_status,
            'pass_fail_status': student.pass_fail_status,
            'bootcamp_id': student.bootcamp_id
        } for student in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/students/<int:student_id>', methods=['GET'])
def get_student_detail(student_id):
    """특정 지원자 상세 정보 조회"""
    student = Student.query.get_or_404(student_id)
    
    return jsonify({
        'id': student.id,
        'name': student.name,
        'email': student.email,
        'phone': student.phone,
        'gender': student.gender,
        'birthdate': student.birthdate.isoformat() if student.birthdate else None,
        'application_date': student.application_date.isoformat(),
        'application_status': student.application_status,
        'pass_fail_status': student.pass_fail_status,
        'class_participation': student.class_participation,
        'motivation': student.motivation,
        'programming_skills': student.programming_skills,
        'bootcamp': {
            'id': student.bootcamp.id,
            'name': student.bootcamp.name,
            'batch_number': student.bootcamp.batch_number
        } if student.bootcamp else None
    })

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/test')
def test_api():
    return render_template('test_api.html')

if __name__ == '__main__':
    # 데이터베이스 테이블 생성
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created successfully!")
    
    # PORT 환경변수 사용
    port = int(os.getenv('PORT', 10000))
    app.run(debug=True, port=port)