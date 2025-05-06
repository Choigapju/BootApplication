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
import sys
import logging
from sqlalchemy import text  # 추가

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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
    phone = db.Column(db.String(20), nullable=False)  # unique 제거 (여러 부트캠프 지원 가능)
    email = db.Column(db.String(100))
    bootcamp_id = db.Column(db.String(50), db.ForeignKey('bootcamps.id'), nullable=False)  # 외래 키 설정
    status = db.Column(db.String(20), default='applying')
    considering_reason = db.Column(db.String(50))
    last_contact_date = db.Column(db.Date, default=datetime.datetime.now().date())
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    batch_number = db.Column(db.Integer)
    
    # 관계 설정
    bootcamp = db.relationship('Bootcamp', backref=db.backref('students', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender,
            'age': self.age,
            'phone': self.phone,
            'email': self.email,
            'bootcampId': self.bootcamp_id,
            'batchNumber': self.batch_number,
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
    batch_number = db.Column(db.Integer, default=1)
    recruitment_start_date = db.Column(db.Date, default=datetime.datetime.now().date())
    recruitment_end_date = db.Column(db.Date)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'batchNumber': self.batch_number,
            'recruitmentStartDate': self.recruitment_start_date.strftime('%Y-%m-%d') if self.recruitment_start_date else None,
            'recruitmentEndDate': self.recruitment_end_date.strftime('%Y-%m-%d') if self.recruitment_end_date else None
        }
    

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

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
    
    # 문자열로 변환하고 숫자만 추출
    phone = ''.join(filter(str.isdigit, str(phone)))
    
    # 11자리 번호인 경우 (01012345678)
    if len(phone) == 11:
        return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
    # 10자리 번호인 경우 (0101234567)
    elif len(phone) == 10:
        return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    # 그 외의 경우는 원본 반환
    return phone

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

def detect_bootcamp_from_filename(filename):
    """파일명에서 부트캠프와 기수 정보 추출"""
    logger.info(f"\n=== 파일명 분석 시작: {filename} ===")
    
    bootcamp_code_mapping = {
        'frontend': ['fe', 'frontend'],
        'backend': ['be', 'backend'],
        'ios': ['ios'],
        'android': ['android'],
        'data': ['data'],
        'uxui': ['design', 'uxui'],
        'startup': ['startup'],
        'shortterm': ['shortterm'],
        'ai-service': ['ai-service'],
        'game': ['ugm', 'game'],  # 'ugm'이 먼저 오도록 수정
        'cloud': ['cloud'],
        'ai': ['ai'],
        'blockchain': ['blockchain'],
        'growth': ['growth']
    }
    
    # 파일명에서 부트캠프와 기수 정보 추출
    match = re.search(r'kdt[_-]([a-zA-Z0-9-]+)[_-](\d+)', filename.lower())
    logger.info(f"정규식 매칭 결과: {match.groups() if match else '매칭 실패'}")
    
    if match:
        bootcamp_code = match.group(1)
        batch_number = int(match.group(2))
        logger.info(f"추출된 정보 - 코드: {bootcamp_code}, 기수: {batch_number}")
        
        # 부트캠프 ID 찾기
        for bootcamp_id, codes in bootcamp_code_mapping.items():
            if bootcamp_code in codes:
                logger.info(f"매칭된 부트캠프 ID: {bootcamp_id}, 기수: {batch_number}")
                return bootcamp_id, batch_number
    
    logger.error(f"부트캠프 정보 추출 실패 - 파일명: {filename}")
    return None, None

def check_db_connection():
    try:
        # text() 함수로 SQL 쿼리 래핑
        db.session.execute(text('SELECT 1'))
        logger.info("데이터베이스 연결 성공")
        return True
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {str(e)}")
        return False

def parse_csv(file_path, bootcamp_id, batch_number):
    """CSV 파일 파싱"""
    try:
        logger.info(f"\n=== CSV 파싱 시작 ===")
        logger.info(f"파일 경로: {file_path}")
        logger.info(f"부트캠프 ID: {bootcamp_id}, 기수: {batch_number}")
        
        # CSV 파일 읽기
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        logger.info(f"CSV 읽기 성공 - 총 {len(df)}행")
        logger.info(f"컬럼 목록: {df.columns.tolist()}")
        
        # 컬럼명 매핑
        column_mapping = {
            '이름': ['이름', '가입 이름', 'name'],
            '성별': ['성별', 'gender'],
            '나이': ['나이', '생년월일', 'age', 'birth'],
            '전화번호': ['전화번호', '가입 연락처', 'phone'],
            '이메일': ['이메일', '지원서 이메일', '가입 이메일', 'email']
        }
        
        students_data = []
        for index, row in df.iterrows():
            try:
                # 각 필드에 대해 가능한 모든 컬럼명 시도
                student_data = {}
                for field, possible_columns in column_mapping.items():
                    for col in possible_columns:
                        if col in df.columns and pd.notna(row[col]):
                            student_data[field] = row[col]
                            logger.debug(f"행 {index}: {field} = {row[col]} (컬럼: {col})")
                            break
                
                if len(student_data) < len(column_mapping):
                    missing_fields = set(column_mapping.keys()) - set(student_data.keys())
                    logger.warning(f"행 {index}: 필수 필드 누락 - {missing_fields}")
                    logger.warning(f"현재 행 데이터: {dict(row)}")
                    continue
                
                # 나이 처리 (생년월일인 경우 나이로 변환)
                age = student_data.get('나이')
                if isinstance(age, str) and '-' in age:  # 생년월일 형식
                    birth_year = int(age.split('-')[0])
                    current_year = datetime.datetime.now().year
                    age = current_year - birth_year + 1
                    logger.debug(f"생년월일 {age}를 나이로 변환: {age}세")
                
                student = Student(
                    name=str(student_data['이름']).strip(),
                    gender=str(student_data['성별']).strip(),
                    age=int(float(age)) if pd.notna(age) else 0,
                    phone=str(student_data['전화번호']).strip(),
                    email=str(student_data['이메일']).strip(),
                    bootcamp_id=bootcamp_id,
                    batch_number=batch_number,
                    status='접수'
                )
                students_data.append(student)
                
                if index == 0:
                    logger.info(f"첫 번째 학생 데이터 샘플:")
                    logger.info(f"이름: {student.name}")
                    logger.info(f"이메일: {student.email}")
                    logger.info(f"부트캠프: {student.bootcamp_id}")
                    logger.info(f"기수: {student.batch_number}")
                
            except Exception as e:
                logger.error(f"행 {index} 처리 중 오류: {str(e)}")
                logger.error(f"문제의 행 데이터: {dict(row)}")
                continue
        
        logger.info(f"처리된 총 학생 수: {len(students_data)}")
        return students_data
        
    except Exception as e:
        logger.error(f"CSV 파싱 중 오류: {str(e)}")
        raise

# 초기화 여부를 추적하기 위한 변수
_is_initialized = False

@app.before_request
def before_request():
    """모든 요청 전에 실행되는 함수"""
    global _is_initialized
    
    if not _is_initialized:
        logger.info("=== 서버 초기화 ===")
        check_db_connection()
        
        # 부트캠프 테이블 확인
        try:
            bootcamps = Bootcamp.query.all()
            logger.info(f"등록된 부트캠프: {[b.id for b in bootcamps]}")
        except Exception as e:
            logger.error(f"부트캠프 조회 실패: {str(e)}")
        
        _is_initialized = True

@app.route('/')
def index():
    """메인 HTML 페이지 서빙"""
    return send_from_directory('public', 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """파일 업로드 API"""
    logger.info("\n=== 파일 업로드 시작 ===")
    
    # 데이터베이스 연결 확인
    if not check_db_connection():
        return jsonify({"error": "데이터베이스 연결 실패"}), 500
    
    try:
        logger.info("1. 파일 존재 여부 확인")
        if 'file' not in request.files:
            logger.error("파일이 요청에 없음")
            return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
        
        file = request.files['file']
        logger.info(f"업로드된 파일명: {file.filename}")
        
        if file.filename == '':
            logger.error("파일명이 비어있음")
            return jsonify({"error": "선택된 파일이 없습니다."}), 400
        
        logger.info("2. 파일 형식 검증")
        if not file or not allowed_file(file.filename):
            logger.error(f"지원되지 않는 파일 형식: {file.filename}")
            return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400
        
        logger.info("3. 파일 내용 확인 시작")
        content = file.read()
        file.seek(0)
        logger.info(f"파일 크기: {len(content)} bytes")
        logger.debug(f"파일 내용 미리보기: {content[:200]}")
        
        logger.info("4. 파일명 처리")
        filename = secure_filename(file.filename)
        logger.info(f"보안 처리된 파일명: {filename}")
        
        logger.info("5. 임시 파일 저장")
        temp_path = os.path.join('/tmp', filename)
        try:
            file.save(temp_path)
            logger.info(f"임시 파일 저장됨: {temp_path}")
        except Exception as save_error:
            logger.error(f"임시 파일 저장 실패: {str(save_error)}")
            return jsonify({"error": "파일 저장에 실패했습니다."}), 500
        
        logger.info("6. 부트캠프 정보 추출")
        bootcamp_id, batch_number = detect_bootcamp_from_filename(filename)
        logger.info(f"추출된 부트캠프 정보 - ID: {bootcamp_id}, 기수: {batch_number}")
        
        if not bootcamp_id or not batch_number:
            logger.error("부트캠프 정보 추출 실패")
            os.remove(temp_path)
            return jsonify({"error": "파일명에서 부트캠프 정보를 추출할 수 없습니다."}), 400
        
        logger.info("7. 부트캠프 DB 확인")
        bootcamp = Bootcamp.query.filter_by(id=bootcamp_id).first()
        logger.info(f"조회된 부트캠프: {bootcamp and bootcamp.id}")
        
        if not bootcamp:
            logger.error(f"부트캠프 없음: {bootcamp_id}")
            os.remove(temp_path)
            return jsonify({"error": f"존재하지 않는 부트캠프입니다: {bootcamp_id}"}), 400
        
        logger.info("8. CSV 파일 처리")
        try:
            with open(temp_path, 'r', encoding='utf-8-sig') as f:
                logger.info(f"파일 내용 미리보기: {f.readline()}")
            
            students_data = parse_csv(temp_path, bootcamp_id, batch_number)
            logger.info(f"CSV 파싱 완료 - {len(students_data)}명의 학생 데이터")
            
            if not students_data:
                logger.error("처리할 학생 데이터가 없음")
                os.remove(temp_path)
                return jsonify({"error": "처리할 학생 데이터가 없습니다."}), 400
            
        except Exception as csv_error:
            logger.error(f"CSV 처리 중 오류: {str(csv_error)}")
            os.remove(temp_path)
            return jsonify({"error": f"CSV 파일 처리에 실패했습니다: {str(csv_error)}"}), 500
        
        logger.info("9. 데이터베이스 저장")
        try:
            db.session.bulk_save_objects(students_data)
            db.session.commit()
            logger.info(f"데이터베이스 저장 성공 - {len(students_data)}명")
        except Exception as save_error:
            logger.error(f"데이터베이스 저장 실패: {str(save_error)}")
            db.session.rollback()
            os.remove(temp_path)
            return jsonify({"error": "데이터베이스 저장에 실패했습니다."}), 500
        
        os.remove(temp_path)
        logger.info("=== 파일 업로드 완료 ===\n")
        
        return jsonify({
            "success": True,
            "count": len(students_data),
            "bootcamp": bootcamp_id,
            "batch": batch_number
        })
        
    except Exception as e:
        logger.error(f"최상위 오류 발생: {str(e)}")
        return jsonify({"error": str(e)}), 500

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
    try:
        if bootcamp_id == 'all':
            students = Student.query.all()
        else:
            students = Student.query.filter_by(bootcamp_id=bootcamp_id).all()
        result = []
        for student in students:
            result.append({
                'id': student.id,
                'name': student.name,
                'gender': student.gender,
                'age': student.age,
                'phone': format_phone(student.phone),  # 반드시 format_phone 사용
                'email': student.email,
                'bootcamp_id': student.bootcamp_id,
                'batch_number': student.batch_number,
                'status': student.status,
                'considering_reason': student.considering_reason,
                'last_contact_date': student.last_contact_date.isoformat() if student.last_contact_date else None,
                'notes': student.notes
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/bootcamps/<string:bootcamp_id>/upload', methods=['POST'])
def upload_bootcamp_file(bootcamp_id):
    """부트캠프별 학생 데이터 업로드 처리"""
    if 'file' not in request.files:
        return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "선택된 파일이 없습니다."}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "CSV 파일만 업로드 가능합니다."}), 400
        
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # 파일명에서 부트캠프와 기수 정보 추출
            detected_bootcamp, batch_number = detect_bootcamp_from_filename(filename)
            
            # 감지된 부트캠프가 있으면 해당 부트캠프로 저장, 없으면 URL의 부트캠프 ID 사용
            actual_bootcamp_id = detected_bootcamp if detected_bootcamp else bootcamp_id
            logger.info(f"실제 저장될 부트캠프: {actual_bootcamp_id}")
            
            # 부트캠프 존재 여부 확인
            bootcamp = db.session.query(Bootcamp).filter_by(id=actual_bootcamp_id).first()
            if not bootcamp:
                return jsonify({"error": f"존재하지 않는 부트캠프입니다: {actual_bootcamp_id}"}), 400
            
            parsed_data = parse_csv(file_path, actual_bootcamp_id, batch_number)
            
            return jsonify({
                "success": True, 
                "count": len(parsed_data), 
                "bootcamp": actual_bootcamp_id,
                "batchNumber": batch_number
            })
                
        except Exception as e:
            logger.error(f"파일 처리 중 오류 발생: {e}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "CSV 파일만 지원됩니다."}), 400

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

# 서버 설정 추가
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 최대 16MB 파일 크기 제한
app.config['SQLALCHEMY_POOL_SIZE'] = 10
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30

if __name__ == '__main__':
    # stdout 버퍼링 비활성화
    sys.stdout.reconfigure(line_buffering=True)
    
    # Flask 디버그 모드 활성화
    app.debug = True
    
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=10000)