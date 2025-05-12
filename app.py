import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import pandas as pd
from dotenv import load_dotenv

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
            # kdt-{부트캠프종류}-{기수}th 형식에서 추출
            parts = filename.split('_')[0].split('-')  # ['kdt', 'design', '5th'] 또는 ['kdt', 'growth', '2nd'] 등
            if len(parts) >= 3:
                bootcamp_type = parts[1]  # design, growth, frontend 등
                generation = parts[2]  # 5th, 2nd, 14th 등
                
                # 부트캠프 종류 매핑
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
                print("추출된 부트캠프:", bootcamp_name)  # 디버깅용
                print("추출된 기수:", generation)  # 디버깅용
            else:
                return jsonify({'error': '파일명 형식이 올바르지 않습니다.'}), 400
                
        except Exception as e:
            print("부트캠프/기수 추출 에러:", str(e))
            return jsonify({'error': '파일명에서 부트캠프/기수를 추출할 수 없습니다.'}), 400
        
        try:
            df = pd.read_csv(file)
            print("CSV 컬럼명:", df.columns.tolist())  # 디버깅용
        except Exception as e:
            print("CSV 읽기 에러:", str(e))
            return jsonify({'error': 'CSV 파일을 읽을 수 없습니다.'}), 400
        
        # 컬럼명 매핑 (실제 CSV 파일의 컬럼명에 맞게 수정)
        column_mapping = {
            'name': '가입 이름',
            'email': '가입 이메일',
            'gender': '성별',
            'age': '생년월일',  # 생년월일에서 나이 계산
            'phone': '가입 연락처'
        }
        
        # 컬럼명 변경
        try:
            df = df.rename(columns=column_mapping)
        except Exception as e:
            print("컬럼명 변경 에러:", str(e))
            return jsonify({'error': 'CSV 파일의 컬럼명을 변경할 수 없습니다.'}), 400
        
        for _, row in df.iterrows():
            try:
                # 전화번호를 문자열로 변환
                phone_str = str(row.get('가입 연락처', '')).strip()
                # 이메일과 전화번호로 중복 체크
                existing_student = Student.query.join(Bootcamp).filter(
                    Student.email == row['가입 이메일'],
                    Student.phone == phone_str,
                    Bootcamp.name == bootcamp_name,
                    Bootcamp.generation == generation
                ).first()
                
                if existing_student:
                    print(f"중복 지원자 발견: {row['가입 이름']} ({row['가입 이메일']})")
                    continue  # 중복 지원자는 건너뜀
                
                # 부트캠프/기수 정보 추출
                bootcamp = Bootcamp.query.filter_by(
                    name=bootcamp_name,
                    generation=generation
                ).first()
                
                if not bootcamp:
                    bootcamp = Bootcamp(
                        name=bootcamp_name,
                        generation=generation
                    )
                    db.session.add(bootcamp)
                    db.session.commit()
                
                # 생년월일에서 나이 계산
                try:
                    birth_year = int(row['생년월일'].split('-')[0])
                    current_year = 2024  # 현재 연도
                    age = current_year - birth_year
                except:
                    age = None
                
                student = Student(
                    name=row['가입 이름'],
                    email=row['가입 이메일'],
                    gender=row.get('성별', ''),
                    age=age,
                    phone=phone_str,  # 여기도 문자열로 저장
                    bootcamp_id=bootcamp.id
                )
                db.session.add(student)
            except Exception as e:
                print("데이터 처리 에러:", str(e))
                return jsonify({'error': f'데이터 처리 중 에러가 발생했습니다: {str(e)}'}), 500
        
        try:
            db.session.commit()
            return jsonify({'message': '업로드 및 저장 완료'})
        except Exception as e:
            print("DB 저장 에러:", str(e))
            db.session.rollback()
            return jsonify({'error': '데이터베이스 저장 중 에러가 발생했습니다.'}), 500
    
    except Exception as e:
        print("전체 에러:", str(e))
        return jsonify({'error': f'처리 중 에러가 발생했습니다: {str(e)}'}), 500

# 부트캠프/기수별 지원자 리스트
@app.route('/students', methods=['GET'])
def get_students():
    bootcamp = request.args.get('bootcamp')
    generation = request.args.get('generation')
    query = db.session.query(Student, Bootcamp).join(Bootcamp)
    if bootcamp:
        query = query.filter(Bootcamp.name == bootcamp)
    if generation:
        query = query.filter(Bootcamp.generation == generation)
    results = []
    for student, bootcamp in query.all():
        results.append({
            'id': student.id,
            'bootcamp': bootcamp.name,
            'generation': bootcamp.generation,
            'name': student.name,
            'email': student.email,
            'gender': student.gender,
            'age': student.age,
            'phone': student.phone,
            'status': student.status,
            'memo': student.memo
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
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bootcamp 지원자 관리</title>
        <style>
            .bootcamp-item {
                display: inline-block;
                margin: 5px;
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            .delete-btn {
                margin-left: 5px;
                color: red;
                cursor: pointer;
            }
            .delete-btn:hover {
                background-color: #ffebee;
            }
            .status-select {
                padding: 5px;
                border-radius: 4px;
            }
            .memo-input {
                width: 200px;
                padding: 5px;
                border-radius: 4px;
            }
            .save-btn {
                padding: 5px 10px;
                margin-left: 5px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            .save-btn:hover {
                background-color: #45a049;
            }
            .status-지원중 { color: #2196F3; }
            .status-합격 { color: #4CAF50; }
            .status-고민중 { color: #FF9800; }
            .status-HRD최종등록 { color: #9C27B0; }
            .status-지원취소 { color: #F44336; }
        </style>
    </head>
    <body>
        <h2>CSV 업로드</h2>
        <form id="uploadForm" enctype="multipart/form-data">
            <input type="file" name="file" />
            <button type="submit">업로드</button>
        </form>
        <div id="uploadMessage"></div>
        <h2>지원자 조회</h2>
        <div id="toolbar"></div>
        <label>부트캠프: <input type="text" id="bootcamp"></label>
        <label>기수: <input type="text" id="generation"></label>
        <button onclick="fetchStudents()">조회</button>
        <table border="1" id="studentsTable">
            <thead>
                <tr>
                    <th>부트캠프</th>
                    <th>기수</th>
                    <th>이름</th>
                    <th>이메일</th>
                    <th>성별</th>
                    <th>나이</th>
                    <th>전화번호</th>
                    <th>상태</th>
                    <th>메모</th>
                    <th>액션</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
        <h2>통계</h2>
        <button onclick="fetchStats()">통계 조회</button>
        <div id="stats"></div>
        <script>
        const STATUS_OPTIONS = ['지원중', '합격', '고민중', 'HRD최종등록', '지원취소'];
        
        // 상태와 메모 업데이트 함수
        async function updateStudent(studentId, status, memo) {
            try {
                const res = await fetch('/student/update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        id: studentId,
                        status: status,
                        memo: memo
                    })
                });
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.error);
                }
                return data;
            } catch (error) {
                console.error('Update error:', error);
                alert('업데이트 중 에러가 발생했습니다.');
                throw error;
            }
        }
        
        // 지원자 목록 조회 함수 수정
        async function fetchStudents() {
            try {
                const bootcamp = document.getElementById('bootcamp').value;
                const generation = document.getElementById('generation').value;
                let url = `/students?bootcamp=${bootcamp}&generation=${generation}`;
                const res = await fetch(url);
                const data = await res.json();
                const tbody = document.querySelector('#studentsTable tbody');
                tbody.innerHTML = '';
                data.forEach(s => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${s.bootcamp}</td>
                        <td>${s.generation}</td>
                        <td>${s.name}</td>
                        <td>${s.email}</td>
                        <td>${s.gender}</td>
                        <td>${s.age}</td>
                        <td>${s.phone}</td>
                        <td>
                            <select class="status-select status-${s.status || '지원중'}" onchange="handleStatusChange(${s.id}, this)">
                                ${STATUS_OPTIONS.map(option => 
                                    `<option value="${option}" ${(s.status || '지원중') === option ? 'selected' : ''}>${option}</option>`
                                ).join('')}
                            </select>
                        </td>
                        <td>
                            <input type="text" class="memo-input" value="${s.memo || ''}" 
                                   onchange="handleMemoChange(${s.id}, this)" placeholder="메모 입력...">
                        </td>
                        <td>
                            <button class="save-btn" onclick="handleSave(${s.id}, this)">저장</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (error) {
                console.error('Fetch students error:', error);
                alert('지원자 목록을 불러오는 중 에러가 발생했습니다.');
            }
        }
        
        // 상태 변경 핸들러
        async function handleStatusChange(studentId, selectElement) {
            const row = selectElement.closest('tr');
            selectElement.className = `status-select status-${selectElement.value}`;
        }
        
        // 메모 변경 핸들러
        async function handleMemoChange(studentId, inputElement) {
            // 변경 사항은 저장 버튼 클릭 시 저장됨
        }
        
        // 저장 버튼 핸들러
        async function handleSave(studentId, buttonElement) {
            const row = buttonElement.closest('tr');
            const status = row.querySelector('.status-select').value;
            const memo = row.querySelector('.memo-input').value;
            
            try {
                await updateStudent(studentId, status, memo);
                alert('성공적으로 저장되었습니다.');
            } catch (error) {
                console.error('Save error:', error);
            }
        }
        
        // 부트캠프/기수 툴바 생성
        async function loadToolbar() {
            const res = await fetch('/bootcamps');
            const data = await res.json();
            const toolbar = document.getElementById('toolbar');
            toolbar.innerHTML = '';
            // 중복 제거
            const unique = Array.from(new Set(data.map(b => b.name + '||' + b.generation)))
                .map(str => {
                    const [name, generation] = str.split('||');
                    return {name, generation};
                });
            unique.forEach(b => {
                const container = document.createElement('div');
                container.className = 'bootcamp-item';
                
                const btn = document.createElement('button');
                btn.innerText = `${b.name} / ${b.generation}`;
                btn.onclick = function() {
                    document.getElementById('bootcamp').value = b.name;
                    document.getElementById('generation').value = b.generation;
                    fetchStudents();
                };
                
                const deleteBtn = document.createElement('button');
                deleteBtn.innerText = '삭제';
                deleteBtn.className = 'delete-btn';
                deleteBtn.onclick = async function() {
                    if (confirm(`정말로 ${b.name} ${b.generation}기 데이터를 삭제하시겠습니까?`)) {
                        try {
                            const res = await fetch('/bootcamp/delete', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    name: b.name,
                                    generation: b.generation
                                })
                            });
                            const data = await res.json();
                            if (res.ok) {
                                alert(data.message);
                                loadToolbar(); // 툴바 새로고침
                                fetchStudents(); // 학생 목록 새로고침
                                fetchStats(); // 통계 새로고침
                            } else {
                                alert(data.error || '삭제 중 에러가 발생했습니다.');
                            }
                        } catch (error) {
                            console.error('Delete error:', error);
                            alert('삭제 중 에러가 발생했습니다.');
                        }
                    }
                };
                
                container.appendChild(btn);
                container.appendChild(deleteBtn);
                toolbar.appendChild(container);
            });
        }
        document.addEventListener('DOMContentLoaded', loadToolbar);
        document.getElementById('uploadForm').onsubmit = async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            try {
                const res = await fetch('/upload', {method: 'POST', body: formData});
                const data = await res.json();
                if (res.ok) {
                    document.getElementById('uploadMessage').innerText = data.message;
                    document.getElementById('uploadMessage').style.color = 'green';
                    loadToolbar(); // 업로드 후 툴바 갱신
                } else {
                    document.getElementById('uploadMessage').innerText = data.error || '업로드 중 에러가 발생했습니다.';
                    document.getElementById('uploadMessage').style.color = 'red';
                }
            } catch (error) {
                document.getElementById('uploadMessage').innerText = '서버 연결 중 에러가 발생했습니다.';
                document.getElementById('uploadMessage').style.color = 'red';
                console.error('Upload error:', error);
            }
        }
        async function fetchStats() {
            try {
                const res = await fetch('/stats');
                const data = await res.json();
                document.getElementById('stats').innerText =
                    `총원: ${data.total}, 남: ${data.male}, 여: ${data.female}, 평균나이: ${data.avg_age}`;
            } catch (error) {
                console.error('Fetch stats error:', error);
                alert('통계를 불러오는 중 에러가 발생했습니다.');
            }
        }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 테이블이 없을 때만 생성(데이터는 보존)
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
