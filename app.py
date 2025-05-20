import os
from flask import Flask, request, jsonify, render_template_string, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import pandas as pd
from dotenv import load_dotenv
import math

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
    status = db.Column(db.String(20), default='지원중')  # 상태 필드 추가
    memo = db.Column(db.Text)  # 메모 필드 추가
    bootcamp_id = db.Column(db.Integer, db.ForeignKey('bootcamps.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())  # 생성 시간
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())  # 수정 시간
    considering_reason = db.Column(db.String(255))  # 고민이유 추가

def safe_str(val):
    # NaN, None, float('nan') 모두 ''로 변환
    if val is None:
        return ''
    if isinstance(val, float) and math.isnan(val):
        return ''
    return str(val).strip()

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
                    'data' : '데이터 분석 부트캠프',
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
            df = pd.read_csv(file)
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

        # 이미 등록된 지원자 (email, phone) 쌍 미리 조회
        existing = set(
            (s.email, s.phone)
            for s in Student.query.filter_by(bootcamp_id=bootcamp.id).all()
        )

        new_students = []
        for _, row in df.iterrows():
            email = str(row.get('가입 이메일', '')).strip()
            phone_str = str(row.get('가입 연락처', '')).strip()
            if (email, phone_str) in existing:
                continue
            try:
                birth_year = int(row['생년월일'].split('-')[0])
                current_year = 2024
                age = current_year - birth_year
            except:
                age = None
            student = Student(
                name=row['가입 이름'],
                email=email,
                gender=row.get('성별', ''),
                age=age,
                phone=phone_str,
                bootcamp_id=bootcamp.id
            )
            new_students.append(student)
            existing.add((email, phone_str))  # 중복 방지

        if new_students:
            db.session.bulk_save_objects(new_students)
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
            'memo': student.memo or ''
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
    
    try:
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': '지원자를 찾을 수 없습니다.'}), 404
            
        if status:
            student.status = status
        if memo is not None:  # 빈 문자열도 허용
            student.memo = memo
            
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
    # 빈 문자열도 None처럼 처리
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
        .limit(1)
        .all()
    )
    result = [
        {'name': s.name or '', 'memo': s.memo or '', 'updated_at': s.updated_at.strftime('%Y-%m-%d %H:%M')}
        for s in memos
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
    query = query.group_by(Student.considering_reason)
    result = {reason if reason else '기타': count for reason, count in query.all()}
    return jsonify(result)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 테이블이 없을 때만 생성(데이터는 보존)
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)