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
    bootcamp_id = db.Column(db.Integer, db.ForeignKey('bootcamps.id'), nullable=False)

# CSV 업로드 및 DB 저장
@app.route('/upload', methods=['POST'])
def upload_csv():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'error': '파일이 없습니다.'}), 400
            
        # 파일명에서 기수 정보 추출 (kdt-design-5th_지원서_2024-05-11.csv -> 5th)
        filename = file.filename
        print("업로드된 파일명:", filename)  # 디버깅용
        
        try:
            generation = filename.split('_')[0].split('-')[-1]  # kdt-design-5th -> 5th
            print("추출된 기수:", generation)  # 디버깅용
        except Exception as e:
            print("기수 추출 에러:", str(e))
            return jsonify({'error': '파일명에서 기수를 추출할 수 없습니다.'}), 400
        
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
                # 부트캠프/기수 정보 추출
                bootcamp = Bootcamp.query.filter_by(
                    name='UXUI 디자인 부트캠프',  # 고정값
                    generation=generation  # 파일명에서 추출한 기수 사용
                ).first()
                
                if not bootcamp:
                    bootcamp = Bootcamp(
                        name='UXUI 디자인 부트캠프',
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
                    phone=row.get('가입 연락처', ''),
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
            'name': student.name,
            'email': student.email,
            'gender': student.gender,
            'age': student.age,
            'phone': student.phone,
            'bootcamp': bootcamp.name,
            'generation': bootcamp.generation
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

# 프론트엔드 테스트용 HTML
@app.route('/')
def index():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bootcamp 지원자 관리</title>
    </head>
    <body>
        <h2>CSV 업로드</h2>
        <form id="uploadForm" enctype="multipart/form-data">
            <input type="file" name="file" />
            <button type="submit">업로드</button>
        </form>
        <div id="uploadMessage"></div>
        <h2>지원자 조회</h2>
        <label>부트캠프: <input type="text" id="bootcamp"></label>
        <label>기수: <input type="text" id="generation"></label>
        <button onclick="fetchStudents()">조회</button>
        <table border="1" id="studentsTable">
            <thead>
                <tr><th>이름</th><th>이메일</th><th>성별</th><th>나이</th><th>전화번호</th><th>부트캠프</th><th>기수</th></tr>
            </thead>
            <tbody></tbody>
        </table>
        <h2>통계</h2>
        <button onclick="fetchStats()">통계 조회</button>
        <div id="stats"></div>
        <script>
        document.getElementById('uploadForm').onsubmit = async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            try {
                const res = await fetch('/upload', {method: 'POST', body: formData});
                const data = await res.json();
                if (res.ok) {
                    document.getElementById('uploadMessage').innerText = data.message;
                    document.getElementById('uploadMessage').style.color = 'green';
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
                    tbody.innerHTML += `<tr>
                        <td>${s.name}</td><td>${s.email}</td><td>${s.gender}</td>
                        <td>${s.age}</td><td>${s.phone}</td>
                        <td>${s.bootcamp}</td><td>${s.generation}</td>
                    </tr>`;
                });
            } catch (error) {
                console.error('Fetch students error:', error);
                alert('지원자 목록을 불러오는 중 에러가 발생했습니다.');
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
        # 기존 테이블 삭제 후 재생성
        db.drop_all()  # 기존 테이블 삭제
        db.create_all()  # 테이블 새로 생성
        print("데이터베이스 테이블이 생성되었습니다.")
    
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
