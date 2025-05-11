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
    file = request.files['file']
    df = pd.read_csv(file)
    for _, row in df.iterrows():
        # 부트캠프/기수 정보 추출
        bootcamp = Bootcamp.query.filter_by(name=row['bootcamp'], generation=row['generation']).first()
        if not bootcamp:
            bootcamp = Bootcamp(name=row['bootcamp'], generation=row['generation'])
            db.session.add(bootcamp)
            db.session.commit()
        student = Student(
            name=row['name'],
            email=row['email'],
            gender=row.get('gender', ''),
            age=int(row['age']) if pd.notnull(row['age']) else None,
            phone=row.get('phone', ''),
            bootcamp_id=bootcamp.id
        )
        db.session.add(student)
    db.session.commit()
    return jsonify({'message': '업로드 및 저장 완료'})

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
            const res = await fetch('/upload', {method: 'POST', body: formData});
            alert((await res.json()).message);
        }
        async function fetchStudents() {
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
        }
        async function fetchStats() {
            const res = await fetch('/stats');
            const data = await res.json();
            document.getElementById('stats').innerText =
                `총원: ${data.total}, 남: ${data.male}, 여: ${data.female}, 평균나이: ${data.avg_age}`;
        }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
