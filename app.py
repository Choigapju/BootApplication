import os
from flask import Flask, request, jsonify, render_template_string, render_template, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import pandas as pd
from dotenv import load_dotenv
import math
from collections import Counter
import io
import csv

load_dotenv()  # .env 파일 로드

app = Flask(__name__)
CORS(app)

# .env 파일의 DATABASE_URL 사용
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 모델 정의
class Bootcamp(db.Model):
    __tablename__ = 'bootcamps'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    generation = db.Column(db.String(50), nullable=False)
    students = db.relationship('Student', backref='bootcamp', lazy=True)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    phone = db.Column(db.String(30))
    status = db.Column(db.String(20), default='대상아님')
    memo = db.Column(db.Text)  # 메모 필드 추가
    bootcamp_id = db.Column(db.Integer, db.ForeignKey('bootcamps.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())  # 생성 시간
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())  # 수정 시간
    considering_reason = db.Column(db.String(255))  # 고민이유 추가
    card_owned = db.Column(db.String(20))  # 내배카 보유 여부 (길이를 20으로 늘림)
    created_at_csv = db.Column(db.String(30))  # 또는 db.DateTime

def safe_str(val):
    # NaN, None, float('nan') 모두 ''로 변환
    if val is None:
        return ''
    if isinstance(val, float) and math.isnan(val):
        return ''
    return str(val).strip()

def normalize_phone(phone):
    # 숫자만 남기고, 10자리면 010 붙이기, 11자리면 그대로
    digits = ''.join(filter(str.isdigit, str(phone)))
    if len(digits) == 10 and digits.startswith('10'):
        digits = '0' + digits
    return digits.zfill(11)

def normalize_email(email):
    return str(email).strip().lower()

# CSV 업로드 및 DB 저장
@app.route('/upload', methods=['POST'])
def upload_csv():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'error': '파일이 없습니다.'}), 400

        # 파일명에서 부트캠프 종류와 기수 정보 추출
        filename = file.filename
        print("업로드된 파일명:", filename)  # 디버깅용
        try:
            parts = filename.split('_')[0].split('-')
            if len(parts) >= 3:
                bootcamp_type = parts[1]
                generation = parts[2]
                bootcamp_mapping = {
                    'design': 'UXUI 디자인 부트캠프',
                    'growth': '그로스마케팅 부트캠프',
                    'frontend': '프론트엔드 부트캠프',
                    'backend': '백엔드 부트캠프',
                    'aiw' : 'AI 웹 부트캠프',
                    'android' : '안드로이드 부트캠프',
                    'ios' : '아이폰 앱 개발 부트캠프',
                    'ugm' : '유니티 부트캠프',
                    'dataanalysis' : '데이터 분석 부트캠프',
                    'cloud' : '클라우드 부트캠프',
                }
                bootcamp_name = bootcamp_mapping.get(bootcamp_type, f'{bootcamp_type} 부트캠프')
                print("추출된 부트캠프:", bootcamp_name)
                print("추출된 기수:", generation)
            else:
                return jsonify({'error': '파일명 형식이 올바르지 않습니다.'}), 400
        except Exception as e:
            print("부트캠프/기수 추출 에러:", str(e))
            return jsonify({'error': '파일명에서 부트캠프/기수를 추출할 수 없습니다.'}), 400

        try:
            df = pd.read_csv(file, dtype=str)
            print("CSV 컬럼명:", df.columns.tolist())
            df = df.fillna('')
        except Exception as e:
            print("CSV 읽기 에러:", str(e))
            return jsonify({'error': 'CSV 파일을 읽을 수 없습니다.'}), 400

        column_mapping = {
            'name': '가입 이름',
            'email': '가입 이메일',
            'gender': '성별',
            'age': '생년월일',
            'phone': '가입 연락처'
        }
        try:
            df = df.rename(columns=column_mapping)
        except Exception as e:
            print("컬럼명 변경 에러:", str(e))
            return jsonify({'error': 'CSV 파일의 컬럼명을 변경할 수 없습니다.'}), 400

        # 부트캠프 객체 미리 조회/생성
        bootcamp = Bootcamp.query.filter_by(
            name=bootcamp_name,
            generation=generation
        ).first()
        if not bootcamp:
            bootcamp = Bootcamp(name=bootcamp_name, generation=generation)
            db.session.add(bootcamp)
            db.session.commit()

        # 이미 등록된 지원자 (email, phone) 쌍 미리 조회 (id, status 포함)
        existing_students = {}
        for s in Student.query.filter_by(bootcamp_id=bootcamp.id).all():
            key = (normalize_email(s.email), normalize_phone(s.phone))
            existing_students[key] = s

        status_map = {
            '대상아님': '대상아님',
            '검토전': '검토전',
            '합격': '합격',
            '고민중': '고민중',
            'HRD최종등록': 'HRD최종등록',
            '지원취소': '지원취소',
            '예비합격': '예비합격',
            '불합격': '불합격'
        }
        new_students = []
        for _, row in df.iterrows():
            email = normalize_email(row.get('가입 이메일', ''))
            phone_str = normalize_phone(row.get('가입 연락처', ''))
            key = (email, phone_str)
            try:
                birth_year = int(str(row['생년월일']).split('-')[0])
                current_year = 2024
                age = current_year - birth_year
            except:
                age = None
            status_val = status_map.get(str(row.get('합불상태', '')).strip(), '대상아님')

            # 중복 지원자 처리
            existing = existing_students.get(key)
            if existing:
                old_status = existing.status
                if old_status == '대상아님' and status_val == '검토전':
                    db.session.delete(existing)
                elif old_status in ['검토전', '합격'] and status_val == '지원취소':
                    db.session.delete(existing)
                elif old_status == '검토전' and status_val == '합격':
                    db.session.delete(existing)
                elif old_status == '검토전' and status_val in ['예비합격', '불합격']:
                    db.session.delete(existing)
                elif old_status == '대상아님' and status_val == '합격':
                    db.session.delete(existing)
                else:
                    continue
                db.session.flush()
            # 신규 또는 삭제 후 추가
            student = Student(
                name=row['가입 이름'],
                email=email,
                gender=row.get('성별', ''),
                age=age,
                phone=phone_str,
                bootcamp_id=bootcamp.id,
                card_owned=row.get('내배카 보유', ''),
                status=status_val,
                created_at_csv=row.get('최초작성일', '')
            )
            db.session.add(student)
            # 새로 추가한 지원자도 existing_students에 즉시 반영
            existing_students[key] = student
        db.session.commit()
        return jsonify({'message': '업로드 및 저장 완료'})
    except Exception as e:
        db.session.rollback()
        print("전체 에러:", str(e))
        return jsonify({'error': f'처리 중 에러가 발생했습니다: {str(e)}'}), 500

# 부트캠프/기수별 지원자 리스트
@app.route('/students', methods=['GET'])
def get_students():
    bootcamp = request.args.get('bootcamp', '')
    generation = request.args.get('generation', '')
    status = request.args.get('status', '')
    search = request.args.get('search', '').strip()
    query = db.session.query(Student, Bootcamp).join(Bootcamp)
    if bootcamp:
        query = query.filter(Bootcamp.name == bootcamp)
    if generation:
        query = query.filter(Bootcamp.generation == generation)
    if status:
        query = query.filter(Student.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Student.name.ilike(like), Student.phone.ilike(like), Student.email.ilike(like))
        )
    results = []
    for student, bootcamp in query.all():
        results.append({
            'id': student.id,
            'bootcamp': bootcamp.name or '',
            'generation': bootcamp.generation or '',
            'name': student.name or '',
            'email': student.email or '',
            'gender': student.gender or '',
            'age': student.age if student.age is not None else '',
            'phone': student.phone or '',
            'status': student.status or '',
            'memo': student.memo or '',
            'card_owned': student.card_owned or '',
            'considering_reason': student.considering_reason or ''
        })
    return jsonify(results)

# 전체 지원자 통계
@app.route('/stats', methods=['GET'])
def get_stats():
    total = Student.query.count()
    male = Student.query.filter_by(gender='남').count()
    female = Student.query.filter_by(gender='여').count()
    avg_age = db.session.query(db.func.avg(Student.age)).scalar()
    return jsonify({
        'total': total,
        'male': male,
        'female': female,
        'avg_age': round(avg_age, 1) if avg_age else None
    })

# 부트캠프/기수 목록 반환 API
@app.route('/bootcamps', methods=['GET'])
def get_bootcamps():
    bootcamps = Bootcamp.query.all()
    result = []
    for b in bootcamps:
        result.append({'name': b.name, 'generation': b.generation})
    return jsonify(result)

# 부트캠프/기수 삭제 API
@app.route('/bootcamp/delete', methods=['POST'])
def delete_bootcamp():
    data = request.get_json()
    bootcamp_name = data.get('name')
    generation = data.get('generation')
    
    try:
        # 먼저 해당 부트캠프/기수의 ID를 찾습니다
        bootcamp = Bootcamp.query.filter_by(
            name=bootcamp_name,
            generation=generation
        ).first()
        
        if not bootcamp:
            return jsonify({'error': '해당 부트캠프/기수를 찾을 수 없습니다.'}), 404
        
        # 해당 부트캠프 ID를 가진 모든 지원자 삭제
        Student.query.filter_by(bootcamp_id=bootcamp.id).delete()
        
        # 부트캠프/기수 삭제
        db.session.delete(bootcamp)
        
        db.session.commit()
        return jsonify({'message': '성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# 지원자 상태 업데이트 API
@app.route('/student/update', methods=['POST'])
def update_student():
    data = request.get_json()
    student_id = data.get('id')
    status = data.get('status')
    memo = data.get('memo')
    card_owned = data.get('card_owned')
    considering_reason = data.get('considering_reason')

    try:
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': '지원자를 찾을 수 없습니다.'}), 404

        if status:
            student.status = status
        if memo is not None:
            student.memo = memo
        if card_owned is not None:
            student.card_owned = card_owned
        if considering_reason is not None:
            # 빈 문자열 또는 '선택'이면 NULL로 저장
            if considering_reason.strip() == '' or considering_reason == '선택':
                student.considering_reason = None
            else:
                student.considering_reason = considering_reason

        db.session.commit()
        return jsonify({'message': '성공적으로 업데이트되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# 프론트엔드 테스트용 HTML
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stats_by_status', methods=['GET'])
def stats_by_status():
    bootcamp = request.args.get('bootcamp')
    generation = request.args.get('generation')
    query = db.session.query(Student.status, db.func.count(Student.id)).join(Bootcamp)
    if bootcamp:
        query = query.filter(Bootcamp.name == bootcamp)
    if generation:
        query = query.filter(Bootcamp.generation == generation)
    query = query.group_by(Student.status)
    result = {status: count for status, count in query.all()}
    return jsonify(result)

@app.route('/recent_memos', methods=['GET'])
def recent_memos():
    bootcamp = request.args.get('bootcamp')
    generation = request.args.get('generation')
    bootcamp = bootcamp if bootcamp else None
    generation = generation if generation else None

    if bootcamp or generation:
        query = Student.query.join(Bootcamp)
        if bootcamp:
            query = query.filter(Bootcamp.name == bootcamp)
        if generation:
            query = query.filter(Bootcamp.generation == generation)
    else:
        query = Student.query

    memos = (
        query
        .filter(Student.memo != None, Student.memo != '', db.func.length(Student.memo) > 0)
        .order_by(Student.updated_at.desc())
        .limit(200)
        .all()
    )
    # 같은 내용의 메모는 count를 합산
    memo_counter = Counter((s.memo or '').strip() for s in memos if s.memo)
    result = [
        {'memo': memo, 'count': count}
        for memo, count in memo_counter.items()
    ]
    return jsonify(result)

@app.route('/stats_by_reason', methods=['GET'])
def stats_by_reason():
    bootcamp = request.args.get('bootcamp')
    generation = request.args.get('generation')
    query = db.session.query(Student.considering_reason, db.func.count(Student.id)).join(Bootcamp)
    if bootcamp:
        query = query.filter(Bootcamp.name == bootcamp)
    if generation:
        query = query.filter(Bootcamp.generation == generation)
    # 고민이유가 NULL 또는 빈 문자열이 아닌 것만 카운트
    query = query.filter(Student.considering_reason != None, Student.considering_reason != '')
    query = query.group_by(Student.considering_reason)
    result = {reason: count for reason, count in query.all()}
    return jsonify(result)

@app.route('/download_students')
def download_students():
    bootcamp = request.args.get('bootcamp', '')
    generation = request.args.get('generation', '')
    status = request.args.get('status', '')
    search = request.args.get('search', '')

    # 쿼리 필터링 로직 (Student 모델 기준)
    query = Student.query
    if bootcamp:
        query = query.filter_by(bootcamp=bootcamp)
    if generation:
        query = query.filter_by(generation=generation)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            (Student.name.ilike(f'%{search}%')) | (Student.phone.ilike(f'%{search}%'))
        )
    students = query.all()

    # CSV 생성
    output = io.StringIO()
    writer = csv.writer(output)
    # 헤더
    writer.writerow(['부트캠프', '기수', '이름', '이메일', '성별', '나이', '전화번호', '상태', '메모', '내배카 보유', '고민이유'])
    for s in students:
        writer.writerow([
            s.bootcamp, s.generation, s.name, s.email, s.gender, s.age, s.phone,
            s.status, s.memo, s.card_owned, s.considering_reason
        ])
    # utf-8-sig로 인코딩
    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers['Content-Disposition'] = 'attachment; filename=students.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 테이블이 없을 때만 생성(데이터는 보존)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)