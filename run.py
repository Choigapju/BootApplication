from app import app, db
from app.models import Bootcamp
from datetime import datetime

def init_db():
    with app.app_context():
        db.create_all()
        
        # 기존 부트캠프가 없는 경우에만 초기 데이터 추가
        if not Bootcamp.query.first():
            bootcamps = [
                Bootcamp(id='backend', name='백엔드', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='ios', name='iOS 개발', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='android', name='Android 개발', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='data', name='데이터 분석', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='uxui', name='UX/UI 디자인', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='startup', name='스타트업 스테이션', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='shortterm', name='단기 실무', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='ai-service', name='AI 웹 서비스 개발', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='game', name='유니티 게임 개발', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='cloud', name='클라우드 엔지니어링', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='ai', name='AI', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='blockchain', name='블록체인', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='frontend', name='프론트엔드', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date()),
                Bootcamp(id='growth', name='그로스 마케팅', batch_number=1,
                        recruitment_start_date=datetime(2024, 1, 1).date(),
                        recruitment_end_date=datetime(2024, 12, 31).date())
            ]
            for bootcamp in bootcamps:
                db.session.add(bootcamp)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=10000) 