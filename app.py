from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from io import BytesIO
import os
from dotenv import load_dotenv
import pandas as pd
import csv
import json
import re
import datetime
from werkzeug.utils import secure_filename

# 1. 환경 변수 로딩
load_dotenv()

# 환경 변수에서 DB 정보 가져오기
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")  # 기본값 5432
DB_NAME = os.getenv("DB_NAME")

# 연결 문자열 만들기 전 유효성 검사
DATABASE_URL = None  # 변수 초기화
if not all([DB_USERNAME, DB_PASSWORD, DB_HOST, DB_NAME]):
    print("경고: 필수 데이터베이스 환경 변수가 설정되지 않았습니다!")
    # 환경 변수에서 DATABASE_URL 직접 가져오기 시도
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        print("DATABASE_URL 환경 변수도 없습니다. SQLite 기본값을 사용합니다.")
else:
    # 유효한 포트 확인
    try:
        port = int(DB_PORT)
    except ValueError:
        print(f"경고: 잘못된 포트 번호 '{DB_PORT}', 기본값 5432로 설정합니다.")
        port = 5432
        
    DATABASE_URL = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{port}/{DB_NAME}"

print(f"사용되는 DATABASE_URL: {DATABASE_URL}")

# Flask 앱 초기화
app = Flask(__name__)
CORS(app)

# Flask 앱에 DB 설정 반영
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# SQLAlchemy 초기화
db = SQLAlchemy(app)

# 파일 업로드 설정
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 파일 크기 제한 (16MB)

# 업로드 디렉토리 생성
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 학생 모델 정의
class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100))
    bootcamp_id = db.Column(db.String(50))
    status = db.Column(db.String(20), default='applying')
    considering_reason = db.Column(db.String(50))
    last_contact_date = db.Column(db.Date, default=datetime.datetime.now().date())
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender,
            'age': self.age,
            'phone': self.phone,
            'email': self.email,
            'bootcampId': self.bootcamp_id,
            'status': self.status,
            'consideringReason': self.considering_reason,
            'lastContactDate': self.last_contact_date.strftime('%Y-%m-%d') if self.last_contact_date else None,
            'notes': self.notes,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

# 부트캠프 모델 정의
class Bootcamp(db.Model):
    __tablename__ = 'bootcamps'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'csv', 'xlsx', 'xls'}

def determine_gender(name, gender_data=None):
    """이름으로 성별 추측"""
    # CSV 파일에서 제공된 성별 데이터가 있으면 해당 데이터 사용
    if gender_data and gender_data != '':
        # 'male', 'female' 형식으로 저장된 값을 한글로 변환
        if gender_data.lower() == 'male':
            return '남'
        elif gender_data.lower() == 'female':
            return '여'
        else:
            # 이미 다른 형식(예: '남', '여')으로 저장된 값은 그대로 사용
            return gender_data
    
    # 성별 데이터가 없는 경우에만 이름으로 성별 추측
    if not name:
        return ''
    
    # 여성 이름에 많이 사용되는 글자
    female_chars = ['지', '지현', '현', '예', '민', '지민', '현아', '서', '서연', '연', '은', '지은', '은지']
    # 남성 이름에 많이 사용되는 글자
    male_chars = ['민', '준', '현', '민준', '준호', '석', '승', '우', '석우', '승호', '민우', '철', '석호']
    
    # 이름 맨 앞 성씨 제외
    name_without_last_name = name[1:] if len(name) > 1 else ''
    
    # 여성 이름에 많이 사용되는 글자가 포함되어 있는지 확인
    for char in female_chars:
        if char in name_without_last_name:
            return '여'
    
    # 남성 이름에 많이 사용되는 글자가 포함되어 있는지 확인
    for char in male_chars:
        if char in name_without_last_name:
            return '남'
    
    return ''  # 결정할 수 없는 경우

def get_age(birthdate):
    """생년월일에서 나이 계산 함수"""
    if not birthdate:
        return 0
    
    # 문자열로 변환하여 처리 (숫자인 경우 대비)
    birthdate = str(birthdate)
    
    # 다양한 날짜 형식 처리 시도
    birth_year = None
    
    # YYYY-MM-DD 또는 YYYY/MM/DD 형식
    if re.match(r'^\d{4}[\-\/]\d{1,2}[\-\/]\d{1,2}$', birthdate):
        birth_year = int(re.split(r'[\-\/]', birthdate)[0])
    # YYMMDD 또는 YY-MM-DD 형식
    elif re.match(r'^\d{2}[\-\/]?\d{2}[\-\/]?\d{2}$', birthdate):
        year = birthdate[:2]
        birth_year = int(year) + (1900 if int(year) > 30 else 2000)
    # 년월일 형식 (예: 1990년 01월 01일)
    elif '년' in birthdate:
        match = re.search(r'(\d{4})년', birthdate)
        if match:
            birth_year = int(match.group(1))
    # 8자리 숫자 (YYYYMMDD)
    elif re.match(r'^\d{8}$', birthdate):
        birth_year = int(birthdate[:4])
    # 6자리 숫자 (YYMMDD)
    elif re.match(r'^\d{6}$', birthdate):
        year = birthdate[:2]
        birth_year = int(year) + (1900 if int(year) > 30 else 2000)
    
    if birth_year:
        current_year = datetime.datetime.now().year
        return current_year - birth_year
    
    return 0

def format_phone(phone):
    """전화번호 형식 표준화"""
    if not phone:
        return ''
    
    # 문자열로 변환
    phone = str(phone)
    
    # 숫자와 하이픈만 남기기
    formatted_phone = re.sub(r'[^0-9\-]', '', phone)
    
    # 하이픈이 없는 경우 형식 변환
    if '-' not in formatted_phone:
        if len(formatted_phone) == 11:  # 01012345678
            formatted_phone = f"{formatted_phone[:3]}-{formatted_phone[3:7]}-{formatted_phone[7:]}"
        elif len(formatted_phone) == 10:  # 0101234567
            formatted_phone = f"0{formatted_phone[:2]}-{formatted_phone[2:5]}-{formatted_phone[5:]}"
    
    return formatted_phone

def init_bootcamps():
    """부트캠프 초기 데이터 설정"""
    bootcamps_data = [
        {"id": "frontend", "name": "프론트엔드"},
        {"id": "backend", "name": "백엔드"},
        {"id": "ios", "name": "iOS 개발"},
        {"id": "android", "name": "Android 개발"},
        {"id": "data", "name": "데이터 분석"},
        {"id": "uxui", "name": "UX/UI 디자인"},
        {"id": "startup", "name": "스타트업 스테이션"},
        {"id": "shortterm", "name": "단기 심화"},
        {"id": "ai-service", "name": "AI 웹 서비스 개발"},
        {"id": "game", "name": "유니티 게임 개발"},
        {"id": "cloud", "name": "클라우드 엔지니어링"},
        {"id": "ai", "name": "AI"},
        {"id": "blockchain", "name": "블록체인"},
        {"id": "growth", "name": "그로스 마케팅"}
    ]
    
    for bootcamp_data in bootcamps_data:
        existing = db.session.query(Bootcamp).filter_by(id=bootcamp_data["id"]).first()
        if not existing:
            bootcamp = Bootcamp(id=bootcamp_data["id"], name=bootcamp_data["name"])
            db.session.add(bootcamp)
    
    db.session.commit()
    
    return [bootcamp.to_dict() for bootcamp in Bootcamp.query.all()]

def parse_csv(file_path, bootcamp_id=None):
    """CSV 파일 파싱"""
    results = []
    try:
        # pandas로 CSV 파일 읽기
        df = pd.read_csv(file_path, header=None, skiprows=1)
        
        # 각 행 처리
        for _, row in df.iterrows():
            # 인덱스 기반 접근 (H, I, J, K, L 열)
            if len(row) < 8:  # 최소한의 데이터가 있어야 함
                continue
            
            name = row.iloc[7] if len(row) > 7 and pd.notna(row.iloc[7]) else None
            phone = row.iloc[8] if len(row) > 8 and pd.notna(row.iloc[8]) else None
            
            # 이름이나 전화번호가 없는 경우 건너뛰기
            if not name or not phone:
                continue
                
            email = row.iloc[9] if len(row) > 9 and pd.notna(row.iloc[9]) else ''
            birthdate = row.iloc[10] if len(row) > 10 and pd.notna(row.iloc[10]) else None
            gender_data = row.iloc[11] if len(row) > 11 and pd.notna(row.iloc[11]) else None
            
            # 전화번호 형식 표준화
            formatted_phone = format_phone(phone)
            
            # 나이 계산
            age = get_age(birthdate)
            
            # 성별 결정
            gender = determine_gender(name, gender_data)
            
            # 기존 학생 확인
            existing_student = Student.query.filter_by(phone=formatted_phone).first()
            
            if existing_student:
                # 기존 학생 업데이트
                existing_student.name = name
                existing_student.gender = gender
                existing_student.age = age
                existing_student.email = email if email else ''
                
                if bootcamp_id and not existing_student.bootcamp_id:
                    existing_student.bootcamp_id = bootcamp_id
                
                db.session.add(existing_student)
                results.append(existing_student.to_dict())
            else:
                # 새 학생 생성
                student = Student(
                    name=name,
                    gender=gender,
                    age=age,
                    phone=formatted_phone,
                    email=email if email else '',
                    bootcamp_id=bootcamp_id,
                    status="applying",
                    last_contact_date=datetime.datetime.now().date()
                )
                db.session.add(student)
                db.session.flush()  # ID 생성을 위한 flush
                results.append(student.to_dict())
        
        db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        print(f"CSV 파싱 오류: {e}")
        
    # 완료 후 파일 삭제
    try:
        os.remove(file_path)
    except:
        pass
        
    return results

def parse_excel(file_path, bootcamp_id=None):
    """Excel 파일 파싱"""
    results = []
    try:
        # pandas로 Excel 파일 읽기
        df = pd.read_excel(file_path, header=None)
        
        # 헤더 행의 인덱스 식별
        header_row_index = 0
        for i in range(min(10, len(df))):
            row = df.iloc[i]
            # 이름, 연락처, 이메일 열이 있는지 확인 (H, I, J)
            if len(row) > 9 and (isinstance(row.iloc[7], str) or isinstance(row.iloc[8], str)):
                header_row_index = i
                break
        
        # 헤더 행 이후의 데이터만 처리
        for i in range(header_row_index + 1, len(df)):
            row = df.iloc[i]
            
            if len(row) < 8:  # 최소한의 데이터가 있어야 함
                continue
                
            name = row.iloc[7] if len(row) > 7 and pd.notna(row.iloc[7]) else None
            phone = row.iloc[8] if len(row) > 8 and pd.notna(row.iloc[8]) else None
            
            # 이름이나 전화번호가 없는 경우 건너뛰기
            if not name or not phone:
                continue
                
            email = row.iloc[9] if len(row) > 9 and pd.notna(row.iloc[9]) else ''
            birthdate = row.iloc[10] if len(row) > 10 and pd.notna(row.iloc[10]) else None
            gender_data = row.iloc[11] if len(row) > 11 and pd.notna(row.iloc[11]) else None
            
            # 전화번호 형식 표준화
            formatted_phone = format_phone(phone)
            
            # 나이 계산
            age = get_age(birthdate)
            
            # 성별 결정
            gender = determine_gender(name, gender_data)
            
            # 기존 학생 확인
            existing_student = Student.query.filter_by(phone=formatted_phone).first()
            
            if existing_student:
                # 기존 학생 업데이트
                existing_student.name = name
                existing_student.gender = gender
                existing_student.age = age
                existing_student.email = email if email else ''
                
                if bootcamp_id and not existing_student.bootcamp_id:
                    existing_student.bootcamp_id = bootcamp_id
                
                db.session.add(existing_student)
                results.append(existing_student.to_dict())
            else:
                # 새 학생 생성
                student = Student(
                    name=name,
                    gender=gender,
                    age=age,
                    phone=formatted_phone,
                    email=email if email else '',
                    bootcamp_id=bootcamp_id,
                    status="applying",
                    last_contact_date=datetime.datetime.now().date()
                )
                db.session.add(student)
                db.session.flush()  # ID 생성을 위한 flush
                results.append(student.to_dict())
        
        db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        print(f"Excel 파싱 오류: {e}")
        
    # 완료 후 파일 삭제
    try:
        os.remove(file_path)
    except:
        pass
        
    return results

# 라우트 정의
@app.route('/')
def index():
    """메인 HTML 페이지 서빙"""
    return send_from_directory('public', 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """파일 업로드 API (전체 학생 데이터용)"""
    if 'file' not in request.files:
        return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "선택된 파일이 없습니다."}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext == '.csv':
            parsed_data = parse_csv(file_path)
        elif file_ext in ['.xlsx', '.xls']:
            parsed_data = parse_excel(file_path)
        else:
            return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400
            
        return jsonify({"success": True, "count": len(parsed_data)})
    
    return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400

@app.route('/api/students', methods=['GET'])
def get_students():
    """모든 학생 데이터 가져오기"""
    students = Student.query.all()
    return jsonify([student.to_dict() for student in students])

@app.route('/api/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    """학생 상태 업데이트"""
    student = db.session.query(Student).filter_by(id=student_id).first_or_404()
    
    data = request.get_json()
    
    if 'status' in data:
        student.status = data['status']
    
    if 'consideringReason' in data:
        student.considering_reason = data['consideringReason']
    
    if 'notes' in data:
        student.notes = data['notes']
    
    if 'lastContactDate' in data:
        try:
            student.last_contact_date = datetime.datetime.strptime(data['lastContactDate'], '%Y-%m-%d').date()
        except:
            pass  # 날짜 형식이 잘못된 경우 무시
    
    student.updated_at = datetime.datetime.now()
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
    return jsonify(student.to_dict())

@app.route('/api/bootcamps', methods=['GET'])
def get_bootcamps():
    """모든 부트캠프 정보 가져오기"""
    bootcamps = Bootcamp.query.all()
    if not bootcamps:
        # 부트캠프 데이터가 없으면 초기화
        return jsonify(init_bootcamps())
    return jsonify([bootcamp.to_dict() for bootcamp in bootcamps])

@app.route('/api/bootcamps/<string:bootcamp_id>', methods=['GET'])
def get_bootcamp(bootcamp_id):
    """특정 부트캠프 정보 가져오기"""
    bootcamp = db.session.query(Bootcamp).filter_by(id=bootcamp_id).first_or_404()
    return jsonify(bootcamp.to_dict())

@app.route('/api/bootcamps/<string:bootcamp_id>/students', methods=['GET'])
def get_bootcamp_students(bootcamp_id):
    """부트캠프별 학생 데이터 가져오기"""
    # 존재하는 부트캠프인지 확인
    bootcamp = db.session.query(Bootcamp).filter_by(id=bootcamp_id).first_or_404()
    
    # 해당 부트캠프의 학생 데이터
    students = Student.query.filter_by(bootcamp_id=bootcamp_id).all()
    return jsonify([student.to_dict() for student in students])

@app.route('/api/bootcamps/<string:bootcamp_id>/upload', methods=['POST'])
def upload_bootcamp_file(bootcamp_id):
    """부트캠프별 학생 데이터 업로드 처리"""
    # 부트캠프 존재 여부 확인
    bootcamp = db.session.query(Bootcamp).filter_by(id=bootcamp_id).first_or_404()
    
    if 'file' not in request.files:
        return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "선택된 파일이 없습니다."}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext == '.csv':
            parsed_data = parse_csv(file_path, bootcamp_id)
        elif file_ext in ['.xlsx', '.xls']:
            parsed_data = parse_excel(file_path, bootcamp_id)
        else:
            return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400
            
        return jsonify({"success": True, "count": len(parsed_data)})
    
    return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400

@app.route('/api/bootcamps/<string:bootcamp_id>/stats', methods=['GET'])
def get_bootcamp_stats(bootcamp_id):
    """부트캠프별 통계 API"""
    # 존재하는 부트캠프인지 확인
    bootcamp = db.session.query(Bootcamp).filter_by(id=bootcamp_id).first_or_404()
    
    # 해당 부트캠프의 학생 데이터
    students = Student.query.filter_by(bootcamp_id=bootcamp_id).all()
    
    stats = {
        "total": len(students),
        "statusCount": {
            "applying": sum(1 for s in students if s.status == "applying"),
            "accepted": sum(1 for s in students if s.status == "accepted"),
            "considering": sum(1 for s in students if s.status == "considering"),
            "registered": sum(1 for s in students if s.status == "registered"),
            "canceled": sum(1 for s in students if s.status == "canceled")
        },
        "consideringReasons": {}
    }
    
    # 고민중 이유 집계
    for student in students:
        if student.status == "considering" and student.considering_reason:
            reason = student.considering_reason
            stats["consideringReasons"][reason] = stats["consideringReasons"].get(reason, 0) + 1
    
    return jsonify(stats)

@app.route('/api/bootcamps/<string:bootcamp_id>/students/<int:student_id>', methods=['PUT'])
def update_bootcamp_student(bootcamp_id, student_id):
    """학생 상태 업데이트 (부트캠프 ID 포함)"""
    # 부트캠프 존재 여부 확인
    bootcamp = db.session.query(Bootcamp).filter_by(id=bootcamp_id).first_or_404()
    
    # 학생 조회
    student = db.session.query(Student).filter_by(id=student_id).first_or_404()
    
    # 해당 부트캠프에 속한 학생인지 확인
    if student.bootcamp_id != bootcamp_id:
        return jsonify({"error": "해당 부트캠프에 속한 학생이 아닙니다."}), 404
    
    data = request.get_json()
    
    if 'status' in data:
        student.status = data['status']
    
    if 'consideringReason' in data:
        student.considering_reason = data['consideringReason']
    
    if 'notes' in data:
        student.notes = data['notes']
    
    if 'lastContactDate' in data:
        try:
            student.last_contact_date = datetime.datetime.strptime(data['lastContactDate'], '%Y-%m-%d').date()
        except:
            pass  # 날짜 형식이 잘못된 경우 무시
    
    student.updated_at = datetime.datetime.now()
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
    return jsonify(student.to_dict())

if __name__ == '__main__':
    with app.app_context():
        # 데이터베이스 테이블 생성
        db.create_all()
        # 부트캠프 데이터 초기화
        init_bootcamps()

    # 서버 시작 (환경 변수에서 포트 가져오기)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', debug=False, port=port)