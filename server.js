// server.js
const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const csvParser = require('csv-parser');
const XLSX = require('xlsx');
const cors = require('cors');
const bodyParser = require('body-parser');

// Express 앱 초기화
const app = express();
const port = process.env.PORT || 3000;

// 미들웨어 설정
app.use(cors());
app.use(bodyParser.json());
app.use(express.static('public')); // HTML, CSS, JS 파일 서빙

// 파일 업로드를 위한 multer 설정
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'uploads/'); // 업로드된 파일이 저장될 디렉토리
  },
  filename: (req, file, cb) => {
    cb(null, Date.now() + path.extname(file.originalname)); // 파일 이름 중복 방지
  }
});

const upload = multer({ 
  storage,
  fileFilter: (req, file, cb) => {
    // 허용할 파일 타입
    if (
      file.mimetype === 'text/csv' || 
      file.mimetype === 'application/vnd.ms-excel' || 
      file.mimetype === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ) {
      cb(null, true);
    } else {
      cb(new Error('지원되지 않는 파일 형식입니다. CSV 또는 Excel 파일만 업로드 가능합니다.'));
    }
  }
});

// 업로드 디렉토리 생성
if (!fs.existsSync('uploads')) {
  fs.mkdirSync('uploads');
}

// 데이터 저장소 (간단한 In-Memory DB)
let students = [];
let courses = [];
let courseStudents = {}; // 과정별 학생 데이터 저장

// 부트캠프 정보 저장소
let bootcamps = [
  { id: 'frontend', name: '프론트엔드' },
  { id: 'backend', name: '백엔드' },
  { id: 'ios', name: 'iOS 개발' },
  { id: 'android', name: 'Android 개발' },
  { id: 'data', name: '데이터 분석' },
  { id: 'uxui', name: 'UX/UI 디자인' },
  { id: 'startup', name: '스타트업 스테이션' },
  { id: 'shortterm', name: '단기 심화' },
  { id: 'ai-service', name: 'AI 웹 서비스 개발' },
  { id: 'game', name: '유니티 게임 개발' },
  { id: 'cloud', name: '클라우드 엔지니어링' },
  { id: 'ai', name: 'AI' },
  { id: 'blockchain', name: '블록체인' },
  { id: 'growth', name: '그로스 마케팅' }
];

// 부트캠프별 학생 데이터
let bootcampStudents = {};

// CSV 파일을 직접 파싱하는 함수 (인덱스 기반 접근)
function parseCSV(filePath, callback) {
  const results = [];
  
  fs.createReadStream(filePath)
    .pipe(csvParser({
      headers: false,
      skipLines: 1
    }))
    .on('data', (row) => {
      // 이름과 전화번호 확인
      const name = row[7]; // H열: 가입 이름
      const phone = row[8]; // I열: 가입 연락처
      
      // 이름이나 전화번호가 없는 경우 건너뛰기
      if (!name || !phone) return;
      
      // 전화번호 형식 확인 및 표준화
      let formattedPhone = String(phone).replace(/[^0-9-]/g, '');
      if (!formattedPhone.includes('-')) {
        // 숫자만 있는 경우 010-0000-0000 형식으로 변환
        if (formattedPhone.length === 11) {
          formattedPhone = `${formattedPhone.substring(0, 3)}-${formattedPhone.substring(3, 7)}-${formattedPhone.substring(7)}`;
        } else if (formattedPhone.length === 10) {
          formattedPhone = `${formattedPhone.substring(0, 3)}-${formattedPhone.substring(3, 6)}-${formattedPhone.substring(6)}`;
        }
      }
      
      // 나이 계산
      let age = 0;
      const birthDate = row[10]; // K열의 생년월일
      if (birthDate) {
        age = getAge(birthDate);
      }

      const student = {
        id: Date.now() + Math.floor(Math.random() * 1000),
        name: name,
        gender: row[11] || determineGender(name), // L열: 성별
        age: age,
        phone: formattedPhone,
        email: row[9] || '', // J열: 지원서 이메일
        status: 'applying',
        consideringReason: null,
        lastContactDate: new Date().toISOString().split('T')[0],
        notes: '',
        updatedAt: new Date().toISOString()
      };
      
      console.log('Created student:', student);
      results.push(student);
    })
    .on('end', () => {
      callback(results);
      fs.unlink(filePath, (err) => {
        if (err) console.error('Error deleting file:', err);
      });
    });
}

// Excel 파일 파싱 함수 개선
function parseExcel(filePath, callback) {
  try {
    const workbook = XLSX.readFile(filePath);
    const sheetName = workbook.SheetNames[0];
    const worksheet = workbook.Sheets[sheetName];
    const jsonData = XLSX.utils.sheet_to_json(worksheet, {header: 1});
    
    console.log('Excel 파싱 시작:', filePath);
    console.log('Excel 헤더:', jsonData[0]);
    
    // 결과 배열
    const results = [];
    
    // 헤더 행의 인덱스 식별
    let headerRowIndex = 0;
    for (let i = 0; i < Math.min(10, jsonData.length); i++) {
      const row = jsonData[i];
      // 이름, 연락처, 이메일 열이 있는지 확인 (H, I, J)
      if (row && row.length > 9 && 
          (typeof row[7] === 'string' || typeof row[8] === 'string')) {
        headerRowIndex = i;
        break;
      }
    }
    
    // 헤더 행 이후의 데이터만 처리
    for (let i = headerRowIndex + 1; i < jsonData.length; i++) {
      const row = jsonData[i];
      
      if (!row || row.length < 8) continue; // 데이터가 부족한 행 건너뛰기
      
      const name = row.length > 7 ? row[7] : '';
      const phone = row.length > 8 ? String(row[8]).replace(/[^0-9-]/g, '') : '';
      const email = row.length > 9 ? row[9] : '';
      const birthdate = row.length > 10 ? row[10] : '';
      
      // 이름이나 전화번호가 없는 경우 건너뛰기
      if (!name || !phone) continue;
      
      // 전화번호 형식 확인 및 표준화
      let formattedPhone = phone;
      if (!phone.includes('-')) {
        // 숫자만 있는 경우 010-0000-0000 형식으로 변환
        if (phone.length === 11) {
          formattedPhone = `${phone.substring(0, 3)}-${phone.substring(3, 7)}-${phone.substring(7)}`;
        } else if (phone.length === 10) {
          formattedPhone = `${phone.substring(0, 3)}-${phone.substring(3, 6)}-${phone.substring(6)}`;
        }
      }
      
      const formattedData = {
        id: Date.now() + i,
        name: name || '',
        gender: row.length > 11 ? row[11] : determineGender(name),
        age: getAge(birthdate),
        phone: formattedPhone,
        email: email || '',
        status: 'applying',
        consideringReason: null,
        lastContactDate: new Date().toISOString().split('T')[0],
        notes: '',
        updatedAt: new Date().toISOString()
      };
      
      results.push(formattedData);
    }
    
    console.log(`총 ${results.length}명의 Excel 데이터가 파싱되었습니다.`);
    callback(results);
    
    // 임시 파일 삭제
    fs.unlink(filePath, (err) => {
      if (err) console.error('Error deleting file:', err);
    });
  } catch (error) {
    console.error('Excel parsing error:', error);
    callback([]);
  }
}

// 부트캠프 정보가 포함된 CSV 파싱 함수
function parseCSVWithBootcamp(filePath, bootcampId, callback) {
  const results = [];
  
  fs.createReadStream(filePath)
    .pipe(csvParser({
      headers: false,
      skipLines: 1
    }))
    .on('data', (row) => {
      // 이름과 전화번호 확인
      const name = row[7]; // H열: 가입 이름
      const phone = row[8]; // I열: 가입 연락처
      
      // 이름이나 전화번호가 없는 경우 건너뛰기
      if (!name || !phone) return;
      
      // 전화번호 형식 확인 및 표준화
      let formattedPhone = String(phone).replace(/[^0-9-]/g, '');
      if (!formattedPhone.includes('-')) {
        // 숫자만 있는 경우 010-0000-0000 형식으로 변환
        if (formattedPhone.length === 11) {
          formattedPhone = `${formattedPhone.substring(0, 3)}-${formattedPhone.substring(3, 7)}-${formattedPhone.substring(7)}`;
        } else if (formattedPhone.length === 10) {
          formattedPhone = `${formattedPhone.substring(0, 3)}-${formattedPhone.substring(3, 6)}-${formattedPhone.substring(6)}`;
        }
      }
      
      // 나이 계산
      let age = 0;
      const birthDate = row[10]; // K열의 생년월일
      if (birthDate) {
        age = getAge(birthDate);
      }

      // 부트캠프 ID 추가
      const student = {
        id: Date.now() + Math.floor(Math.random() * 1000),
        name: name,
        gender: row[11] || determineGender(name), // L열: 성별
        age: age,
        phone: formattedPhone,
        email: row[9] || '', // J열: 지원서 이메일
        bootcampId: bootcampId, // 부트캠프 ID
        status: 'applying',
        consideringReason: null,
        lastContactDate: new Date().toISOString().split('T')[0],
        notes: '',
        updatedAt: new Date().toISOString()
      };
      
      console.log('Created student for bootcamp:', student);
      results.push(student);
    })
    .on('end', () => {
      callback(results);
      fs.unlink(filePath, (err) => {
        if (err) console.error('Error deleting file:', err);
      });
    });
}

// 부트캠프 정보가 포함된 Excel 파싱 함수
function parseExcelWithBootcamp(filePath, bootcampId, callback) {
  try {
    const workbook = XLSX.readFile(filePath);
    const sheetName = workbook.SheetNames[0];
    const worksheet = workbook.Sheets[sheetName];
    const jsonData = XLSX.utils.sheet_to_json(worksheet, {header: 1});
    
    console.log('Excel 파싱 시작:', filePath);
    console.log('Excel 헤더:', jsonData[0]);
    
    // 결과 배열
    const results = [];
    
    // 헤더 행의 인덱스 식별
    let headerRowIndex = 0;
    for (let i = 0; i < Math.min(10, jsonData.length); i++) {
      const row = jsonData[i];
      // 이름, 연락처, 이메일 열이 있는지 확인 (H, I, J)
      if (row && row.length > 9 && 
          (typeof row[7] === 'string' || typeof row[8] === 'string')) {
        headerRowIndex = i;
        break;
      }
    }
    
    // 헤더 행 이후의 데이터만 처리
    for (let i = headerRowIndex + 1; i < jsonData.length; i++) {
      const row = jsonData[i];
      
      if (!row || row.length < 8) continue; // 데이터가 부족한 행 건너뛰기
      
      const name = row.length > 7 ? row[7] : '';
      const phone = row.length > 8 ? String(row[8]).replace(/[^0-9-]/g, '') : '';
      const email = row.length > 9 ? row[9] : '';
      const birthdate = row.length > 10 ? row[10] : '';
      
      // 이름이나 전화번호가 없는 경우 건너뛰기
      if (!name || !phone) continue;
      
      // 전화번호 형식 확인 및 표준화
      let formattedPhone = phone;
      if (!phone.includes('-')) {
        // 숫자만 있는 경우 010-0000-0000 형식으로 변환
        if (phone.length === 11) {
          formattedPhone = `${phone.substring(0, 3)}-${phone.substring(3, 7)}-${phone.substring(7)}`;
        } else if (phone.length === 10) {
          formattedPhone = `${phone.substring(0, 3)}-${phone.substring(3, 6)}-${phone.substring(6)}`;
        }
      }
      
      const formattedData = {
        id: Date.now() + i,
        name: name || '',
        gender: row.length > 11 ? row[11] : determineGender(name),
        age: getAge(birthdate),
        phone: formattedPhone,
        email: email || '',
        bootcampId: bootcampId, // 부트캠프 ID 추가
        status: 'applying',
        consideringReason: null,
        lastContactDate: new Date().toISOString().split('T')[0],
        notes: '',
        updatedAt: new Date().toISOString()
      };
      
      results.push(formattedData);
    }
    
    console.log(`총 ${results.length}명의 Excel 데이터가 부트캠프 ${bootcampId}에 파싱되었습니다.`);
    callback(results);
    
    // 임시 파일 삭제
    fs.unlink(filePath, (err) => {
      if (err) console.error('Error deleting file:', err);
    });
  } catch (error) {
    console.error('Excel parsing error:', error);
    callback([]);
  }
}

// 이름으로 성별 추측 (간단한 구현)
function determineGender(name, genderData) {
  // CSV 파일에서 제공된 성별 데이터가 있으면 해당 데이터 사용
  if (genderData && genderData !== '') {
    // 'male', 'female' 형식으로 저장된 값을 한글로 변환
    if (genderData.toLowerCase() === 'male') {
      return '남';
    } else if (genderData.toLowerCase() === 'female') {
      return '여';
    } else {
      // 이미 다른 형식(예: '남', '여')으로 저장된 값은 그대로 사용
      return genderData;
    }
  }
  
  // 성별 데이터가 없는 경우에만 이름으로 성별 추측
  if (!name) return '';
  
  // 여성 이름에 많이 사용되는 글자
  const femaleChars = ['지', '지현', '현', '예', '민', '지민', '현아', '서', '서연', '연', '은', '지은', '은지'];
  // 남성 이름에 많이 사용되는 글자
  const maleChars = ['민', '준', '현', '민준', '준호', '석', '승', '우', '석우', '승호', '민우', '철', '석호'];
  
  // 이름 맨 앞 성씨 제외
  const nameWithoutLastName = name.length > 1 ? name.substring(1) : '';
  
  // 여성 이름에 많이 사용되는 글자가 포함되어 있는지 확인
  for (const char of femaleChars) {
    if (nameWithoutLastName.includes(char)) return '여';
  }
  
  // 남성 이름에 많이 사용되는 글자가 포함되어 있는지 확인
  for (const char of maleChars) {
    if (nameWithoutLastName.includes(char)) return '남';
  }
  
  return ''; // 결정할 수 없는 경우
}

// 생년월일에서 나이 계산 함수
function getAge(birthdate) {
  if (!birthdate) return 0;
  
  // 문자열로 변환하여 처리 (숫자인 경우 대비)
  birthdate = String(birthdate);
  
  // 다양한 날짜 형식 처리 시도
  let birthYear = null;
  
  // YYYY-MM-DD 또는 YYYY/MM/DD 형식
  if (birthdate.match(/^\d{4}[\-\/]\d{1,2}[\-\/]\d{1,2}$/)) {
    birthYear = parseInt(birthdate.split(/[\-\/]/)[0]);
  } 
  // YYMMDD 또는 YY-MM-DD 형식
  else if (birthdate.match(/^\d{2}[\-\/]?\d{2}[\-\/]?\d{2}$/)) {
    const year = birthdate.substring(0, 2);
    birthYear = parseInt(year) + (parseInt(year) > 30 ? 1900 : 2000);
  }
  // 년월일 형식 (예: 1990년 01월 01일)
  else if (birthdate.includes('년')) {
    const match = birthdate.match(/(\d{4})년/);
    if (match) birthYear = parseInt(match[1]);
  }
  // 8자리 숫자 (YYYYMMDD)
  else if (birthdate.match(/^\d{8}$/)) {
    birthYear = parseInt(birthdate.substring(0, 4));
  }
  // 6자리 숫자 (YYMMDD)
  else if (birthdate.match(/^\d{6}$/)) {
    const year = birthdate.substring(0, 2);
    birthYear = parseInt(year) + (parseInt(year) > 30 ? 1900 : 2000);
  }
  
  if (birthYear) {
    const currentYear = new Date().getFullYear();
    return currentYear - birthYear;
  }
  
  return 0;
}

// API 라우트 정의
// 기존 파일 업로드 API (전체 학생 데이터용)
app.post('/api/upload', upload.single('file'), (req, res) => {
  try {
    const file = req.file;
    if (!file) {
      return res.status(400).json({ error: '파일이 업로드되지 않았습니다.' });
    }

    const filePath = file.path;
    const fileExt = path.extname(file.originalname).toLowerCase();

    if (fileExt === '.csv') {
      parseCSV(filePath, (parsedData) => {
        // 기존 데이터에 새 데이터 누적 반영
        // 전화번호를 기준으로 중복 체크
        const phoneNumbers = new Set(students.map(s => s.phone));
        const newStudents = parsedData.filter(student => 
          !phoneNumbers.has(student.phone)
        );
        
        // 기존 데이터에 추가
        students = [...students, ...newStudents];
        
        res.json({ success: true, count: newStudents.length });
      });
    } else if (fileExt === '.xlsx' || fileExt === '.xls') {
      parseExcel(filePath, (parsedData) => {
        // 기존 데이터에 새 데이터 누적 반영
        // 전화번호를 기준으로 중복 체크
        const phoneNumbers = new Set(students.map(s => s.phone));
        const newStudents = parsedData.filter(student => 
          !phoneNumbers.has(student.phone)
        );
        
        // 기존 데이터에 추가
        students = [...students, ...newStudents];
        
        res.json({ success: true, count: newStudents.length });
      });
    } else {
      res.status(400).json({ error: '지원되지 않는 파일 형식입니다.' });
    }
  } catch (error) {
    console.error('File upload error:', error);
    res.status(500).json({ error: '파일 업로드 중 오류가 발생했습니다.' });
  }
});

// 모든 학생 데이터 가져오기
app.get('/api/students', (req, res) => {
  res.json(students);
});

// 학생 상태 업데이트
app.put('/api/students/:id', (req, res) => {
  const studentId = parseInt(req.params.id);
  const updatedData = req.body;
  
  const studentIndex = students.findIndex(s => s.id === studentId);
  
  if (studentIndex === -1) {
    return res.status(404).json({ error: '학생을 찾을 수 없습니다.' });
  }
  
  // 데이터 업데이트
  students[studentIndex] = {
    ...students[studentIndex],
    ...updatedData,
    updatedAt: new Date().toISOString()
  };
  
  // 부트캠프별 데이터에서도 학생 정보 업데이트
  const bootcampId = students[studentIndex].bootcampId;
  if (bootcampId && bootcampStudents[bootcampId]) {
    const bootcampStudentIndex = bootcampStudents[bootcampId].findIndex(s => s.id === studentId);
    if (bootcampStudentIndex !== -1) {
      bootcampStudents[bootcampId][bootcampStudentIndex] = {
        ...bootcampStudents[bootcampId][bootcampStudentIndex],
        ...updatedData,
        updatedAt: new Date().toISOString()
      };
    }
  }
  
  res.json(students[studentIndex]);
});

// 과정 목록 조회
app.get('/api/courses', (req, res) => {
  res.json(courses);
});

// 특정 과정 조회
app.get('/api/courses/:id', (req, res) => {
  const course = courses.find(c => c.id === req.params.id);
  if (!course) return res.status(404).json({ error: '과정을 찾을 수 없습니다.' });
  res.json(course);
});

// 모든 부트캠프 정보 가져오기
app.get('/api/bootcamps', (req, res) => {
  res.json(bootcamps);
});

// 특정 부트캠프 정보 가져오기
app.get('/api/bootcamps/:id', (req, res) => {
  const bootcamp = bootcamps.find(b => b.id === req.params.id);
  if (!bootcamp) return res.status(404).json({ error: '부트캠프를 찾을 수 없습니다.' });
  res.json(bootcamp);
});

// 부트캠프별 학생 데이터 가져오기
app.get('/api/bootcamps/:bootcampId/students', (req, res) => {
  const bootcampId = req.params.bootcampId;
  
  // 해당 부트캠프의 학생 데이터가 없으면 빈 배열 반환
  const bootcampStudentList = bootcampStudents[bootcampId] || [];
  res.json(bootcampStudentList);
});

// 부트캠프별 학생 데이터 업로드 처리
app.post('/api/bootcamps/:bootcampId/upload', upload.single('file'), (req, res) => {
  try {
    const bootcampId = req.params.bootcampId;
    const file = req.file;

    if (!file) {
      return res.status(400).json({ error: '파일이 업로드되지 않았습니다.' });
    }

    // 부트캠프 존재 여부 확인
    const bootcamp = bootcamps.find(b => b.id === bootcampId);
    if (!bootcamp) {
      return res.status(404).json({ error: '부트캠프를 찾을 수 없습니다.' });
    }

    const filePath = file.path;
    const fileExt = path.extname(file.originalname).toLowerCase();

    // 파일 처리 시 부트캠프 ID 포함하여 파싱
    if (fileExt === '.csv') {
      parseCSVWithBootcamp(filePath, bootcampId, (parsedData) => {
        // 기존 부트캠프 데이터가 없으면 초기화
        if (!bootcampStudents[bootcampId]) {
          bootcampStudents[bootcampId] = [];
        }
        
        // 전화번호를 기준으로 중복 체크 - 부트캠프 내 중복
        const phoneNumbers = new Set(bootcampStudents[bootcampId].map(s => s.phone));
        const newBootcampStudents = parsedData.filter(student => 
          !phoneNumbers.has(student.phone)
        );
        
        // 기존 부트캠프 데이터에 추가
        bootcampStudents[bootcampId] = [...bootcampStudents[bootcampId], ...newBootcampStudents];
        
        // 전체 데이터에도 추가 (중복 체크)
        const allPhoneNumbers = new Set(students.map(s => s.phone));
        const newOverallStudents = newBootcampStudents.filter(student => 
          !allPhoneNumbers.has(student.phone)
        );
        
        // 전체 데이터에 추가
        students = [...students, ...newOverallStudents];
        
        res.json({ success: true, count: newBootcampStudents.length });
      });
    } else if (fileExt === '.xlsx' || fileExt === '.xls') {
      parseExcelWithBootcamp(filePath, bootcampId, (parsedData) => {
        // 기존 부트캠프 데이터가 없으면 초기화
        if (!bootcampStudents[bootcampId]) {
          bootcampStudents[bootcampId] = [];
        }
        
        // 전화번호를 기준으로 중복 체크 - 부트캠프 내 중복
        const phoneNumbers = new Set(bootcampStudents[bootcampId].map(s => s.phone));
        const newBootcampStudents = parsedData.filter(student => 
          !phoneNumbers.has(student.phone)
        );
        
        // 기존 부트캠프 데이터에 추가
        bootcampStudents[bootcampId] = [...bootcampStudents[bootcampId], ...newBootcampStudents];
        
        // 전체 데이터에도 추가 (중복 체크)
        const allPhoneNumbers = new Set(students.map(s => s.phone));
        const newOverallStudents = newBootcampStudents.filter(student => 
          !allPhoneNumbers.has(student.phone)
        );
        
        // 전체 데이터에 추가
        students = [...students, ...newOverallStudents];
        
        res.json({ success: true, count: newBootcampStudents.length });
      });
    } else {
      res.status(400).json({ error: '지원되지 않는 파일 형식입니다.' });
    }
  } catch (error) {
    console.error('File upload error:', error);
    res.status(500).json({ error: '파일 업로드 중 오류가 발생했습니다.' });
  }
});

// 부트캠프별 통계 API
app.get('/api/bootcamps/:bootcampId/stats', (req, res) => {
  const bootcampId = req.params.bootcampId;
  const students = bootcampStudents[bootcampId] || [];
  
  const stats = {
    total: students.length,
    statusCount: {
      applying: students.filter(s => s.status === 'applying').length,
      accepted: students.filter(s => s.status === 'accepted').length,
      considering: students.filter(s => s.status === 'considering').length,
      registered: students.filter(s => s.status === 'registered').length,
      canceled: students.filter(s => s.status === 'canceled').length
    },
    consideringReasons: {} // 고민중 이유 집계
  };
  
  // 고민중 이유 집계
  students
    .filter(s => s.status === 'considering')
    .forEach(s => {
      if (s.consideringReason) {
        stats.consideringReasons[s.consideringReason] = 
          (stats.consideringReasons[s.consideringReason] || 0) + 1;
      }
    });
    
  res.json(stats);
});

// 학생 상태 업데이트 (부트캠프 ID 포함)
app.put('/api/bootcamps/:bootcampId/students/:id', (req, res) => {
  const bootcampId = req.params.bootcampId;
  const studentId = parseInt(req.params.id);
  const updatedData = req.body;
  
  if (!bootcampStudents[bootcampId]) {
    return res.status(404).json({ error: '부트캠프를 찾을 수 없습니다.' });
  }
  
  const studentIndex = bootcampStudents[bootcampId].findIndex(s => s.id === studentId);
  
  if (studentIndex === -1) {
    return res.status(404).json({ error: '학생을 찾을 수 없습니다.' });
  }
  
  // 데이터 업데이트
  bootcampStudents[bootcampId][studentIndex] = {
    ...bootcampStudents[bootcampId][studentIndex],
    ...updatedData,
    updatedAt: new Date().toISOString()
  };
  
  // 전체 데이터에서도 학생 정보 업데이트
  const allStudentIndex = students.findIndex(s => s.id === studentId);
  if (allStudentIndex !== -1) {
    students[allStudentIndex] = {
      ...students[allStudentIndex],
      ...updatedData,
      updatedAt: new Date().toISOString()
    };
  }
  
  res.json(bootcampStudents[bootcampId][studentIndex]);
});

// 메인 HTML 페이지 서빙
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 서버 시작
app.listen(port, () => {
  console.log(`서버가 http://localhost:${port} 에서 실행 중입니다.`);
});