-- 데이터베이스 생성
CREATE DATABASE bootapplication;
\c bootapplication;

-- 부트캠프 테이블
CREATE TABLE bootcamps (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    batch_number INTEGER NOT NULL,
    recruitment_start_date DATE NOT NULL,
    recruitment_end_date DATE,
    UNIQUE(id, batch_number)
);

-- 지원자 테이블
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    gender VARCHAR(10),
    birthdate DATE,
    application_date TIMESTAMP NOT NULL,
    application_status VARCHAR(50),
    pass_fail_status VARCHAR(50),
    bootcamp_id VARCHAR(50) REFERENCES bootcamps(id),
    class_participation VARCHAR(10),
    motivation TEXT,
    programming_skills TEXT
);

-- 이벤트 코멘트 테이블 추가
CREATE TABLE event_comments (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    comment TEXT NOT NULL,
    bootcamp_filter VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX idx_students_user_id ON students(user_id);
CREATE INDEX idx_students_bootcamp_id ON students(bootcamp_id);
CREATE INDEX idx_students_application_date ON students(application_date);
CREATE INDEX idx_bootcamps_batch_number ON bootcamps(batch_number);
CREATE INDEX idx_event_comments_date ON event_comments(date);
CREATE INDEX idx_event_comments_bootcamp ON event_comments(bootcamp_filter);