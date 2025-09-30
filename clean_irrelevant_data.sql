-- 기존 DB에서 '대상아님' 상태의 지원자 데이터 삭제
DELETE FROM students WHERE status = '대상아님';

-- 삭제된 행 수 확인을 위한 쿼리 (실행 전 확인용)
-- SELECT COUNT(*) as deleted_count FROM students WHERE status = '대상아님';
