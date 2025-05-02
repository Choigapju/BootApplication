document.getElementById('uploadForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const fileInput = this.querySelector('input[type="file"]');
    
    if (!fileInput.files.length) {
        showAlert('error', '파일을 선택해주세요.');
        return;
    }
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showAlert('error', data.error);
        } else {
            showAlert('success', data.message);
            if (data.errors && data.errors.length > 0) {
                data.errors.forEach(error => {
                    showAlert('warning', error);
                });
            }
            // 폼 초기화
            this.reset();
            // 테이블 새로고침
            if (typeof refreshTable === 'function') {
                refreshTable();
            } else {
                window.location.reload();
            }
        }
    })
    .catch(error => {
        showAlert('error', '파일 업로드 중 오류가 발생했습니다: ' + error);
    });
});

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.querySelector('.card-body').insertBefore(alertDiv, document.querySelector('form'));
    
    // 5초 후 알림 자동 제거
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
} 