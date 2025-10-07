-- 간단한 방식으로 컬럼 추가 (하나씩)
ALTER TABLE students ADD COLUMN birth_date DATE;
ALTER TABLE students ADD COLUMN source VARCHAR(100);
ALTER TABLE students ADD COLUMN pass_status VARCHAR(10);
ALTER TABLE students ADD COLUMN hrd_conversion VARCHAR(10);
ALTER TABLE students ADD COLUMN call_required VARCHAR(10);
ALTER TABLE students ADD COLUMN last_call_date DATE;
ALTER TABLE students ADD COLUMN call_result VARCHAR(10);
ALTER TABLE students ADD COLUMN is_considering VARCHAR(10);
ALTER TABLE students ADD COLUMN final_call_date DATE;
ALTER TABLE students ADD COLUMN call_outcome VARCHAR(100);
