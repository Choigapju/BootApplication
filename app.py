# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import pandas as pd
import csv
import json
import shutil
import time
import random
import re
import datetime
from werkzeug.utils import secure_filename

# Flask 앱 초기화
app = Flask(__name__, static_folder='public')
CORS(app)  # CORS 미들웨어 설정
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 파일 크기 제한 (16MB)

# 업로드 디렉토리 생성
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 데이터 저장소 (간단한 In-Memory DB)
students = []
courses = []
course_students = {}  # 과정별 학생 데이터 저장

# 부트캠프 정보 저장소
bootcamps = [
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

# 부트캠프별 학생 데이터
bootcamp_students = {}

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
            formatted_phone = f"{formatted_phone[:3]}-{formatted_phone[3:6]}-{formatted_phone[6:]}"
    
    return formatted_phone

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
            
            # 학생 데이터 생성
            student = {
                "id": int(time.time() * 1000 + random.randint(0, 1000)),
                "name": name,
                "gender": gender,
                "age": age,
                "phone": formatted_phone,
                "email": email if email else '',
                "status": "applying",
                "consideringReason": None,
                "lastContactDate": datetime.datetime.now().strftime("%Y-%m-%d"),
                "notes": "",
                "updatedAt": datetime.datetime.now().isoformat()
            }
            
            # 부트캠프 ID가 제공된 경우 추가
            if bootcamp_id:
                student["bootcampId"] = bootcamp_id
                
            results.append(student)
            
    except Exception as e:
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
            
            # 학생 데이터 생성
            student = {
                "id": int(time.time() * 1000 + i),
                "name": name,
                "gender": gender,
                "age": age,
                "phone": formatted_phone,
                "email": email if email else '',
                "status": "applying",
                "consideringReason": None,
                "lastContactDate": datetime.datetime.now().strftime("%Y-%m-%d"),
                "notes": "",
                "updatedAt": datetime.datetime.now().isoformat()
            }
            
            # 부트캠프 ID가 제공된 경우 추가
            if bootcamp_id:
                student["bootcampId"] = bootcamp_id
                
            results.append(student)
            
    except Exception as e:
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
    global students
    
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
            
        # 기존 데이터에 새 데이터 누적 반영
        # 전화번호를 기준으로 중복 체크
        phone_numbers = set(student["phone"] for student in students)
        new_students = [student for student in parsed_data if student["phone"] not in phone_numbers]
        
        # 기존 데이터에 추가
        students.extend(new_students)
        
        return jsonify({"success": True, "count": len(new_students)})
    
    return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400

@app.route('/api/students', methods=['GET'])
def get_students():
    """모든 학생 데이터 가져오기"""
    return jsonify(students)

@app.route('/api/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    """학생 상태 업데이트"""
    global students
    
    updated_data = request.get_json()
    
    student_index = -1
    for i, student in enumerate(students):
        if student["id"] == student_id:
            student_index = i
            break
    
    if student_index == -1:
        return jsonify({"error": "학생을 찾을 수 없습니다."}), 404
    
    # 데이터 업데이트
    students[student_index].update(updated_data)
    students[student_index]["updatedAt"] = datetime.datetime.now().isoformat()
    
    # 부트캠프별 데이터에서도 학생 정보 업데이트
    bootcamp_id = students[student_index].get("bootcampId")
    if bootcamp_id and bootcamp_id in bootcamp_students:
        bootcamp_student_index = -1
        for i, student in enumerate(bootcamp_students[bootcamp_id]):
            if student["id"] == student_id:
                bootcamp_student_index = i
                break
                
        if bootcamp_student_index != -1:
            bootcamp_students[bootcamp_id][bootcamp_student_index].update(updated_data)
            bootcamp_students[bootcamp_id][bootcamp_student_index]["updatedAt"] = datetime.datetime.now().isoformat()
    
    return jsonify(students[student_index])

@app.route('/api/courses', methods=['GET'])
def get_courses():
    """과정 목록 조회"""
    return jsonify(courses)

@app.route('/api/courses/<string:course_id>', methods=['GET'])
def get_course(course_id):
    """특정 과정 조회"""
    course = next((c for c in courses if c["id"] == course_id), None)
    if not course:
        return jsonify({"error": "과정을 찾을 수 없습니다."}), 404
    return jsonify(course)

@app.route('/api/bootcamps', methods=['GET'])
def get_bootcamps():
    """모든 부트캠프 정보 가져오기"""
    return jsonify(bootcamps)

@app.route('/api/bootcamps/<string:bootcamp_id>', methods=['GET'])
def get_bootcamp(bootcamp_id):
    """특정 부트캠프 정보 가져오기"""
    bootcamp = next((b for b in bootcamps if b["id"] == bootcamp_id), None)
    if not bootcamp:
        return jsonify({"error": "부트캠프를 찾을 수 없습니다."}), 404
    return jsonify(bootcamp)

@app.route('/api/bootcamps/<string:bootcamp_id>/students', methods=['GET'])
def get_bootcamp_students(bootcamp_id):
    """부트캠프별 학생 데이터 가져오기"""
    # 해당 부트캠프의 학생 데이터가 없으면 빈 배열 반환
    bootcamp_student_list = bootcamp_students.get(bootcamp_id, [])
    return jsonify(bootcamp_student_list)

@app.route('/api/bootcamps/<string:bootcamp_id>/upload', methods=['POST'])
def upload_bootcamp_file(bootcamp_id):
    """부트캠프별 학생 데이터 업로드 처리"""
    global students, bootcamp_students
    
    # 부트캠프 존재 여부 확인
    bootcamp = next((b for b in bootcamps if b["id"] == bootcamp_id), None)
    if not bootcamp:
        return jsonify({"error": "부트캠프를 찾을 수 없습니다."}), 404
    
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
            
        # 기존 부트캠프 데이터가 없으면 초기화
        if bootcamp_id not in bootcamp_students:
            bootcamp_students[bootcamp_id] = []
        
        # 전화번호를 기준으로 중복 체크 - 부트캠프 내 중복
        phone_numbers = set(student["phone"] for student in bootcamp_students[bootcamp_id])
        new_bootcamp_students = [student for student in parsed_data if student["phone"] not in phone_numbers]
        
        # 기존 부트캠프 데이터에 추가
        bootcamp_students[bootcamp_id].extend(new_bootcamp_students)
        
        # 전체 데이터에도 추가 (중복 체크)
        all_phone_numbers = set(student["phone"] for student in students)
        new_overall_students = [student for student in new_bootcamp_students if student["phone"] not in all_phone_numbers]
        
        # 전체 데이터에 추가
        students.extend(new_overall_students)
        
        return jsonify({"success": True, "count": len(new_bootcamp_students)})
    
    return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400

@app.route('/api/bootcamps/<string:bootcamp_id>/stats', methods=['GET'])
def get_bootcamp_stats(bootcamp_id):
    """부트캠프별 통계 API"""
    students_list = bootcamp_students.get(bootcamp_id, [])
    
    stats = {
        "total": len(students_list),
        "statusCount": {
            "applying": sum(1 for s in students_list if s["status"] == "applying"),
            "accepted": sum(1 for s in students_list if s["status"] == "accepted"),
            "considering": sum(1 for s in students_list if s["status"] == "considering"),
            "registered": sum(1 for s in students_list if s["status"] == "registered"),
            "canceled": sum(1 for s in students_list if s["status"] == "canceled")
        },
        "consideringReasons": {}
    }
    
    # 고민중 이유 집계
    for student in students_list:
        if student["status"] == "considering" and student["consideringReason"]:
            reason = student["consideringReason"]
            stats["consideringReasons"][reason] = stats["consideringReasons"].get(reason, 0) + 1
    
    return jsonify(stats)

@app.route('/api/bootcamps/<string:bootcamp_id>/students/<int:student_id>', methods=['PUT'])
def update_bootcamp_student(bootcamp_id, student_id):
    """학생 상태 업데이트 (부트캠프 ID 포함)"""
    global students, bootcamp_students
    
    if bootcamp_id not in bootcamp_students:
        return jsonify({"error": "부트캠프를 찾을 수 없습니다."}), 404
    
    updated_data = request.get_json()
    
    student_index = -1
    for i, student in enumerate(bootcamp_students[bootcamp_id]):
        if student["id"] == student_id:
            student_index = i
            break
    
    if student_index == -1:
        return jsonify({"error": "학생을 찾을 수 없습니다."}), 404
    
    # 데이터 업데이트
    bootcamp_students[bootcamp_id][student_index].update(updated_data)
    bootcamp_students[bootcamp_id][student_index]["updatedAt"] = datetime.datetime.now().isoformat()
    
    # 전체 데이터에서도 학생 정보 업데이트
    all_student_index = -1
    for i, student in enumerate(students):
        if student["id"] == student_id:
            all_student_index = i
            break
            
    if all_student_index != -1:
        students[all_student_index].update(updated_data)
        students[all_student_index]["updatedAt"] = datetime.datetime.now().isoformat()
    
    return jsonify(bootcamp_students[bootcamp_id][student_index])

if __name__ == '__main__':
    # 서버 시작 (환경 변수에서 포트 가져오기)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', debug=True, port=port)