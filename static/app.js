document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const uploadBtn = document.querySelector('button[type="submit"]') || document.getElementById('upload-btn');
    const fileInput = document.querySelector('input[type="file"]');

    // Upload button click
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            if (!fileInput.files[0]) {
                alert('Please select a file first!');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            const statusDiv = document.getElementById('upload-status') || document.getElementById('status');
            if (statusDiv) statusDiv.innerHTML = '⏳ Uploading... Please wait';

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    if (statusDiv) statusDiv.innerHTML = '✅ ' + result.message + ' (' + result.characters + ' chars)';
                    alert('Success! Document uploaded: ' + result.filename);
                } else {
                    if (statusDiv) statusDiv.innerHTML = '❌ ' + result.message;
                    alert('Error: ' + result.message);
                }
            } catch (error) {
                if (statusDiv) statusDiv.innerHTML = '❌ Upload failed: ' + error;
                console.error(error);
            }
        });
    }
});
