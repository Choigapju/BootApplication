from flask import render_template, request, redirect, url_for, flash, jsonify
from app import app, db
from app.models import Student, Bootcamp
import pandas as pd
from datetime import datetime
import os
import re
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

# 허용된 파일 확장자 설정
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return redirect(url_for('list_students'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다.'}), 400
    
    file = request.files['file']
    duplicate_option = request.form.get('duplicate_option', '1')  # 1: 첫번째 유지, 2: 모두 건너뛰기
    bootcamp_id = request.form.get('bootcamp_id', 'game')
    batch_number = int(request.form.get('batch_number', 5))
    
    if file.filename == '':
        return jsonify({'error': '선택된 파일이 없습니다.'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # 파일을 DataFrame으로 읽기
            df = pd.read_csv(file, encoding='utf-8')
            
            # 컬럼명 매핑
            column_mapping = {
                '가입 이름': 'name',
                '이름': 'name',
                '성별': 'gender',
                '생년월일': 'birth_date',
                '가입 연락처': 'phone',
                '연락처': 'phone',
                '전화번호': 'phone',
                '휴대폰': 'phone',
                '지원서 이메일': 'email',
                '이메일': 'email',
                '게임 개발에 관심을 가지게 된 계기와, 게임 개발자가 되기로 결심한 이유에 대해 서술해주세요.': 'considering_reason',
                '지원동기': 'considering_reason'
            }
            
            # 실제 존재하는 컬럼만 매핑
            for orig_col, new_col in column_mapping.items():
                if orig_col in df.columns:
                    df = df.rename(columns={orig_col: new_col})
            
            # 필수 컬럼 확인
            required_columns = ['name', 'phone']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return jsonify({'error': f'필수 컬럼이 없습니다: {", ".join(missing_columns)}'}), 400
            
            # 중복 전화번호 처리
            if duplicate_option == '1':
                # 첫 번째 항목만 유지
                df = df.drop_duplicates(subset=['phone'], keep='first')
            elif duplicate_option == '2':
                # 중복된 전화번호를 가진 모든 항목 제거
                df = df.drop_duplicates(subset=['phone'], keep=False)
            
            success_count = 0
            error_count = 0
            error_messages = []
            
            for _, row in df.iterrows():
                try:
                    # 전화번호 정제 (하이픈 제거)
                    phone = str(row['phone']).strip().replace('-', '')
                    
                    # 기존 전화번호 확인
                    existing_student = Student.query.filter_by(
                        phone=phone,
                        batch_number=batch_number
                    ).first()
                    
                    if existing_student:
                        error_count += 1
                        error_messages.append(f"전화번호 중복: {row['name']}({phone})")
                        continue
                    
                    student = Student(
                        name=str(row['name']).strip(),
                        phone=phone,
                        email=str(row.get('email', '')).strip(),
                        gender=str(row.get('gender', '')).strip(),
                        age=int(row.get('age', 0)) if pd.notna(row.get('age')) else 0,
                        bootcamp_id=bootcamp_id,
                        status='지원완료',
                        considering_reason=str(row.get('considering_reason', '')).strip(),
                        batch_number=batch_number
                    )
                    db.session.add(student)
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_messages.append(f"데이터 처리 오류: {row['name']} - {str(e)}")
            
            if success_count > 0:
                db.session.commit()
            
            return jsonify({
                'message': f'파일 처리 완료. 성공: {success_count}건, 실패: {error_count}건',
                'errors': error_messages
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'파일 처리 중 오류 발생: {str(e)}'}), 500
            
    return jsonify({'error': '허용되지 않는 파일 형식입니다.'}), 400

@app.route('/students')
def list_students():
    bootcamp_id = request.args.get('bootcamp_id')
    batch_number = request.args.get('batch_number')
    status = request.args.get('status')
    search = request.args.get('search', '').strip()
    
    # 기본 쿼리 생성
    query = Student.query
    
    # 필터 적용
    if bootcamp_id:
        query = query.filter_by(bootcamp_id=bootcamp_id)
    if batch_number:
        query = query.filter_by(batch_number=batch_number)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            (Student.name.ilike(f'%{search}%')) |
            (Student.phone.ilike(f'%{search}%')) |
            (Student.email.ilike(f'%{search}%'))
        )
    
    # 현황 데이터 조회
    status_counts = db.session.query(
        Student.status,
        func.count(Student.id)
    ).group_by(Student.status).all()
    
    # 현황 데이터를 딕셔너리로 변환
    status_counts_dict = {status: count for status, count in status_counts}
    total_count = sum(status_counts_dict.values())
    
    students = query.all()
    bootcamps = Bootcamp.query.all()
    
    return render_template('students.html',
                         students=students,
                         bootcamps=bootcamps,
                         status_counts=status_counts_dict,
                         total_count=total_count)

@app.route('/update_status/<int:id>', methods=['POST'])
def update_status(id):
    data = request.get_json()
    student = Student.query.get_or_404(id)
    student.status = data.get('status')
    student.last_contact_date = datetime.now()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/update_memo/<int:id>', methods=['POST'])
def update_memo(id):
    data = request.get_json()
    student = Student.query.get_or_404(id)
    student.notes = data.get('memo')
    student.last_contact_date = datetime.now()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/delete_student/<int:id>', methods=['DELETE'])
def delete_student(id):
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/student/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        student.status = request.form.get('status')
        student.notes = request.form.get('notes')
        student.last_contact_date = datetime.now()
        db.session.commit()
        flash('학생 정보가 업데이트되었습니다')
        return redirect(url_for('list_students'))
    
    return render_template('edit_student.html', student=student) 