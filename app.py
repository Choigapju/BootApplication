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
    signup_email = db.Column(db.String(100))  # 가입 이메일 추가

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

            # 지원완료일을 datetime으로 변환(정렬을 위해)
            df['지원완료일'] = pd.to_datetime(df['지원완료일'], errors='coerce')

            # 내림차순 정렬(최신 데이터가 위로)
            df = df.sort_values('지원완료일', ascending=False)

            # 중복 제거: 이름, 전화번호, 지원서이메일, 가입이메일 중 하나라도 같으면 첫 번째(최신)만 남김
            df = df.drop_duplicates(subset=['가입 이름', '가입 연락처', '지원서 이메일', '가입 이메일'], keep='first')

            # 지원완료일을 문자열로 변환, NaT는 ''로 대체
            df['지원완료일'] = df['지원완료일'].astype(str).replace('NaT', '')
        except Exception as e:
            print("CSV 읽기 에러:", str(e))
            return jsonify({'error': 'CSV 파일을 읽을 수 없습니다.'}), 400

        # 부트캠프 객체 미리 조회/생성
        bootcamp = Bootcamp.query.filter_by(
            name=bootcamp_name,
            generation=generation
        ).first()
        if not bootcamp:
            bootcamp = Bootcamp(name=bootcamp_name, generation=generation)
            db.session.add(bootcamp)
            db.session.commit()

        # 업로드 시작 전에
        Student.query.filter(
            Student.bootcamp_id == bootcamp.id,
            Student.status != 'HRD최종등록'
        ).delete()
        db.session.commit()

        # 1. 기존 지원자 정보로 모든 조합의 키를 만든다
        existing_students = {}
        for s in Student.query.filter_by(bootcamp_id=bootcamp.id).all():
            emails = set([normalize_email(s.email)])
            if getattr(s, 'signup_email', None):
                emails.add(normalize_email(s.signup_email))
            phones = set([normalize_phone(s.phone)])
            for e in emails:
                for p in phones:
                    existing_students[(e, p)] = s
            # 이메일끼리도 키로 추가
            for e1 in emails:
                for e2 in emails:
                    existing_students[(e1, e2)] = s

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
            email = normalize_email(row.get('지원서 이메일', ''))
            signup_email = normalize_email(row.get('가입 이메일', ''))
            phone_str = normalize_phone(row.get('가입 연락처', ''))
            name = row.get('가입 이름', '').strip()

            # 기존 지원자 찾기 (이름, 전화번호, 이메일(둘 다) 중 하나라도 일치하면)
            candidates = Student.query.filter_by(bootcamp_id=bootcamp.id).all()
            found = None
            for s in candidates:
                if (
                    s.name == name or
                    normalize_phone(s.phone) == phone_str or
                    normalize_email(s.email) == email or
                    (getattr(s, 'signup_email', None) and normalize_email(s.signup_email) == signup_email)
                ):
                    found = s
                    break

            status_val = status_map.get(str(row.get('합불상태', '')).strip(), '대상아님')
            should_add = True

            # 1. HRD최종등록자가 이미 있으면, 업로드 데이터는 무시(추가하지 않음)
            if found and found.status == 'HRD최종등록':
                should_add = False  # 기존 데이터 유지, 새로 추가하지 않음

            # 2. 그 외에는 기존 지원자 삭제 후 새로 추가
            elif found:
                db.session.delete(found)

            if should_add:
                try:
                    birth_year = int(str(row['생년월일']).split('-')[0])
                    current_year = 2024
                    age = current_year - birth_year
                except:
                    age = None

                student = Student(
                    name=name,
                    email=email,
                    signup_email=signup_email,
                    gender=row.get('성별', ''),
                    age=age,
                    phone=phone_str,
                    bootcamp_id=bootcamp.id,
                    card_owned=row.get('내배카 보유', ''),
                    status=status_val,
                    created_at_csv=row.get('지원완료일', ''),
                    memo='',
                    considering_reason=row.get('고민이유', ''),
                )
                db.session.add(student)
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
            'considering_reason': student.considering_reason or '',
            'signup_email': student.signup_email or ''
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

    # Bootcamp와 조인
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
    students = query.all()

    # CSV 생성
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['지원완료일', '부트캠프', '기수', '이름', '가입 이메일', '지원서 이메일', '성별', '나이', '전화번호', '상태', '메모', '내배카 보유', '고민이유'])
    for student, bootcamp in students:
        writer.writerow([
            student.created_at_csv or '',  # 지원완료일(제일 앞)
            bootcamp.name,
            bootcamp.generation,
            student.name,
            student.signup_email or '',   # 가입 이메일
            student.email or '',          # 지원서 이메일
            student.gender,
            student.age,
            student.phone,
            student.status,
            student.memo,
            student.card_owned,
            student.considering_reason
        ])
    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers['Content-Disposition'] = 'attachment; filename=students.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    return response

@app.route('/students/bulk_update', methods=['POST'])
def bulk_update_students():
    data = request.get_json()
    updates = data.get('updates', [])
    try:
        for upd in updates:
            student = Student.query.get(upd['id'])
            if not student:
                continue
            if 'status' in upd:
                student.status = upd['status']
            if 'memo' in upd:
                student.memo = upd['memo']
            if 'card_owned' in upd:
                student.card_owned = upd['card_owned']
            if 'considering_reason' in upd:
                cr = upd['considering_reason']
                student.considering_reason = None if cr.strip() == '' or cr == '선택' else cr
        db.session.commit()
        return jsonify({'message': '전체 저장 완료'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# 지원 추이 분석 페이지
@app.route('/trends')
def trends():
    return render_template('trends.html')

# 일별 지원 완료자 추이 API
@app.route('/trends/daily_applications')
def get_daily_trends():
    period = request.args.get('period', '30')
    bootcamp = request.args.get('bootcamp', '')
    
    try:
        # 기본 쿼리
        query = db.session.query(Student, Bootcamp).join(Bootcamp)
        
        # 부트캠프 필터
        if bootcamp:
            bootcamp_name, generation = bootcamp.split('||')
            query = query.filter(Bootcamp.name == bootcamp_name)
            if generation:
                query = query.filter(Bootcamp.generation == generation)
        
        # 기간 필터
        if period != 'all':
            days = int(period)
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.filter(Student.created_at_csv >= cutoff_date.strftime('%Y-%m-%d'))
        
        students = query.all()
        
        # 일별 집계
        daily_counts = {}
        for student, bootcamp in students:
            if student.created_at_csv:
                try:
                    # 날짜 파싱 (YYYY-MM-DD 형식 가정)
                    date_str = str(student.created_at_csv).split(' ')[0]  # 시간 부분 제거
                    if date_str in daily_counts:
                        daily_counts[date_str] += 1
                    else:
                        daily_counts[date_str] = 1
                except:
                    continue
        
        # 날짜순 정렬
        sorted_dates = sorted(daily_counts.keys())
        labels = sorted_dates
        data = [daily_counts[date] for date in sorted_dates]
        
        # 통계 계산
        total = sum(data)
        average = round(total / len(data), 1) if data else 0
        max_count = max(data) if data else 0
        recent = data[-1] if data else 0
        
        return jsonify({
            'labels': labels,
            'datasets': [{
                'label': '일별 지원 완료자',
                'data': data,
                'borderColor': '#FF7710',
                'backgroundColor': 'rgba(255, 119, 16, 0.1)',
                'tension': 0.1
            }],
            'stats': {
                'total': total,
                'average': average,
                'max': max_count,
                'recent': recent
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 날짜 파싱 유틸 함수 추가
from datetime import datetime, timedelta

def try_parse_date(date_str):
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%Y.%m.%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

# 주별 지원 완료자 추이 API
@app.route('/trends/weekly_applications')
def get_weekly_trends():
    period = request.args.get('period', '30')
    bootcamp = request.args.get('bootcamp', '')

    try:
        query = db.session.query(Student, Bootcamp).join(Bootcamp)
        if bootcamp:
            bootcamp_name, generation = bootcamp.split('||')
            query = query.filter(Bootcamp.name == bootcamp_name)
            if generation:
                query = query.filter(Bootcamp.generation == generation)
        students = query.all()

        # 기간 필터를 파이썬에서 직접 처리
        if period != 'all':
            days = int(period)
            cutoff_date = datetime.now() - timedelta(days=days)
        else:
            cutoff_date = None

        weekly_counts = {}
        for student, bootcamp in students:
            date_str = (student.created_at_csv or '').strip()
            if not date_str or date_str in ['NaT', 'nan', 'None', ' ']:
                continue
            date_obj = try_parse_date(date_str)
            if not date_obj:
                continue
            if cutoff_date and date_obj < cutoff_date:
                continue
            week_start = date_obj - timedelta(days=date_obj.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1

        sorted_weeks = sorted(weekly_counts.keys())
        labels = [f"{week}주차" for week in sorted_weeks]
        data = [weekly_counts[week] for week in sorted_weeks]
        total = sum(data)
        average = round(total / len(data), 1) if data else 0
        max_count = max(data) if data else 0
        recent = data[-1] if data else 0

        return jsonify({
            'labels': labels,
            'datasets': [{
                'label': '주별 지원 완료자',
                'data': data,
                'borderColor': '#6EC6FF',
                'backgroundColor': 'rgba(110, 198, 255, 0.1)',
                'tension': 0.1
            }],
            'stats': {
                'total': total,
                'average': average,
                'max': max_count,
                'recent': recent
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 일자별 지원자 통계표 API (누적 추이)
@app.route('/trends/daily_stats_table')
def get_daily_stats_table():
    period = request.args.get('period', '30')
    bootcamp = request.args.get('bootcamp', '')
    from datetime import datetime, timedelta

    try:
        query = db.session.query(Student, Bootcamp).join(Bootcamp)
        if bootcamp:
            bootcamp_name, generation = bootcamp.split('||')
            query = query.filter(Bootcamp.name == bootcamp_name)
            if generation:
                query = query.filter(Bootcamp.generation == generation)
        students = query.all()

        # 기간 필터를 파이썬에서 직접 처리
        if period != 'all':
            days = int(period)
            cutoff_date = datetime.now() - timedelta(days=days)
        else:
            cutoff_date = None

        # 날짜별 통계 집계
        daily_stats = {}
        for student, bootcamp in students:
            date_str = (student.created_at_csv or '').strip()
            if not date_str or date_str in ['NaT', 'nan', 'None', ' ']:
                continue
            # 날짜 파싱 (시간 포함 가능)
            date_obj = None
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%Y.%m.%d'):
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    break
                except:
                    continue
            if not date_obj:
                continue
            if cutoff_date and date_obj < cutoff_date:
                continue
            day = date_obj.strftime('%Y-%m-%d')
            if day not in daily_stats:
                daily_stats[day] = {
                    '지원완료': 0,
                    '합격': 0,
                    '예비합격': 0,
                    '지원취소': 0,
                    '불합격': 0
                }
            daily_stats[day]['지원완료'] += 1
            if student.status == '합격':
                daily_stats[day]['합격'] += 1
            elif student.status == '예비합격':
                daily_stats[day]['예비합격'] += 1
            elif student.status == '지원취소':
                daily_stats[day]['지원취소'] += 1
            elif student.status == '불합격':
                daily_stats[day]['불합격'] += 1

        # 날짜순 정렬 및 누적 합계 계산
        sorted_days = sorted(daily_stats.keys())
        result = []
        acc = {'지원완료': 0, '합격': 0, '예비합격': 0, '지원취소': 0, '불합격': 0}
        for day in sorted_days:
            acc['지원완료'] += daily_stats[day]['지원완료']
            acc['합격'] += daily_stats[day]['합격']
            acc['예비합격'] += daily_stats[day]['예비합격']
            acc['지원취소'] += daily_stats[day]['지원취소']
            acc['불합격'] += daily_stats[day]['불합격']
            row = {'date': day}
            row.update({k: acc[k] for k in acc})
            result.append(row)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 부트캠프 비교 API
@app.route('/trends/compare_bootcamps')
def compare_bootcamps():
    period = request.args.get('period', '30')
    bootcamp1 = request.args.get('bootcamp1', '')
    bootcamp2 = request.args.get('bootcamp2', '')
    trend_type = request.args.get('type', 'daily')  # daily 또는 weekly
    
    from datetime import datetime, timedelta
    
    try:
        # 기간 필터 설정
        if period != 'all':
            days = int(period)
            cutoff_date = datetime.now() - timedelta(days=days)
        else:
            cutoff_date = None
        
        datasets = []
        colors = ['#FF7710', '#6EC6FF', '#FF6B6B', '#4ECDC4', '#45B7D1']
        
        # 첫 번째 부트캠프 데이터
        if bootcamp1:
            data1 = get_bootcamp_trend_data(bootcamp1, cutoff_date, trend_type)
            if data1:
                datasets.append({
                    'label': bootcamp1.replace('||', ' / '),
                    'data': data1['data'],
                    'labels': data1['labels'],
                    'borderColor': colors[0],
                    'backgroundColor': colors[0].replace(')', ', 0.1)').replace('rgb', 'rgba'),
                    'tension': 0.1
                })
        
        # 두 번째 부트캠프 데이터
        if bootcamp2:
            data2 = get_bootcamp_trend_data(bootcamp2, cutoff_date, trend_type)
            if data2:
                datasets.append({
                    'label': bootcamp2.replace('||', ' / '),
                    'data': data2['data'],
                    'labels': data2['labels'],
                    'borderColor': colors[1],
                    'backgroundColor': colors[1].replace(')', ', 0.1)').replace('rgb', 'rgba'),
                    'tension': 0.1
                })
        
        # 공통 라벨 생성 (날짜 범위)
        all_labels = set()
        for dataset in datasets:
            if 'labels' in dataset:
                all_labels.update(dataset['labels'])
        
        labels = sorted(list(all_labels)) if all_labels else []
        
        # 각 데이터셋의 데이터를 라벨에 맞게 정렬
        for dataset in datasets:
            if 'labels' in dataset:
                # 라벨과 데이터를 매칭하여 정렬된 데이터 생성
                label_data_map = dict(zip(dataset['labels'], dataset['data']))
                dataset['data'] = [label_data_map.get(label, 0) for label in labels]
                del dataset['labels']  # labels는 별도로 전송
        
        return jsonify({
            'labels': labels,
            'datasets': datasets
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_bootcamp_trend_data(bootcamp_filter, cutoff_date, trend_type):
    """부트캠프별 트렌드 데이터를 가져오는 헬퍼 함수"""
    try:
        query = db.session.query(Student, Bootcamp).join(Bootcamp)
        
        if bootcamp_filter:
            bootcamp_name, generation = bootcamp_filter.split('||')
            query = query.filter(Bootcamp.name == bootcamp_name)
            if generation:
                query = query.filter(Bootcamp.generation == generation)
        
        students = query.all()
        
        if trend_type == 'daily':
            # 일별 집계
            daily_counts = {}
            for student, bootcamp in students:
                if student.created_at_csv:
                    try:
                        date_str = str(student.created_at_csv).split(' ')[0]
                        if cutoff_date:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            if date_obj < cutoff_date:
                                continue
                        if date_str in daily_counts:
                            daily_counts[date_str] += 1
                        else:
                            daily_counts[date_str] = 1
                    except:
                        continue
            
            sorted_dates = sorted(daily_counts.keys())
            return {
                'labels': sorted_dates,
                'data': [daily_counts[date] for date in sorted_dates]
            }
        
        elif trend_type == 'weekly':
            # 주별 집계
            weekly_counts = {}
            for student, bootcamp in students:
                date_str = (student.created_at_csv or '').strip()
                if not date_str or date_str in ['NaT', 'nan', 'None', ' ']:
                    continue
                date_obj = try_parse_date(date_str)
                if not date_obj:
                    continue
                if cutoff_date and date_obj < cutoff_date:
                    continue
                week_start = date_obj - timedelta(days=date_obj.weekday())
                week_key = week_start.strftime('%Y-%m-%d')
                weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1
            
            sorted_weeks = sorted(weekly_counts.keys())
            return {
                'labels': [f"{week}주차" for week in sorted_weeks],
                'data': [weekly_counts[week] for week in sorted_weeks]
            }
        
        return None
        
    except Exception as e:
        print(f"부트캠프 데이터 가져오기 오류: {e}")
        return None

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 테이블이 없을 때만 생성(데이터는 보존)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)