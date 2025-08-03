<?php
header('Content-Type: application/json; charset=utf-8');

// --- КОНФИГУРАЦИЯ ---
define('UPLOADS_DIR', 'uploads');
define('MESSAGES_FILE', 'messages.json');
define('MAX_FILE_SIZE', 25 * 1024 * 1024); // 25 MB
define('ALLOWED_MIMES', [
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
    'video/mp4', 'video/webm', 'video/quicktime',
    'audio/mpeg', 'audio/ogg', 'audio/wav',
    'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/zip', 'application/x-rar-compressed', 'application/gzip',
    'text/plain', 'text/csv'
]);

function send_error($message, $code = 400) {
    http_response_code($code);
    echo json_encode(['error' => $message]);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    send_error('Неверный метод запроса', 405);
}

// NEW: Automatically create uploads directory if it doesn't exist
if (!is_dir(UPLOADS_DIR) && !mkdir(UPLOADS_DIR, 0755, true)) {
    send_error('Не удалось создать директорию для загрузок.', 500);
}

$message_text = isset($_POST['message']) ? trim($_POST['message']) : '';
$file = isset($_FILES['file']) ? $_FILES['file'] : null;

if (empty($message_text) && (!$file || $file['error'] !== UPLOAD_ERR_OK)) {
    send_error('Сообщение не может быть пустым, если не прикреплен файл.');
}

$saved_filename = null;
$original_filename = null;

if ($file && $file['error'] === UPLOAD_ERR_OK) {
    if ($file['size'] > MAX_FILE_SIZE) {
        send_error('Файл слишком большой. Максимум: ' . (MAX_FILE_SIZE / 1024 / 1024) . ' МБ.');
    }

    $mime_type = finfo_file(finfo_open(FILEINFO_MIME_TYPE), $file['tmp_name']);

    if (!in_array($mime_type, ALLOWED_MIMES, true)) {
        send_error('Недопустимый тип файла: ' . htmlspecialchars($mime_type));
    }

    $original_filename = basename($file['name']);
    $extension = strtolower(pathinfo($original_filename, PATHINFO_EXTENSION));
    $safe_extension = preg_replace('/[^a-z0-9]/', '', $extension);
    $saved_filename = uniqid('file_', true) . ($safe_extension ? '.' . $safe_extension : '');

    if (!move_uploaded_file($file['tmp_name'], UPLOADS_DIR . '/' . $saved_filename)) {
        send_error('Не удалось сохранить загруженный файл.', 500);
    }
}

$new_message = [
    'text'             => $message_text,
    'file'             => $saved_filename,
    'originalFilename' => $original_filename,
    'timestamp'        => date('c') // ISO 8601 format, JS-friendly
];

// --- NEW: Atomic and safe JSON file update to prevent race conditions ---
$handle = fopen(MESSAGES_FILE, 'c+');
if (!$handle) {
    send_error('Не удалось открыть файл сообщений.', 500);
}

// Lock the file for exclusive writing
if (!flock($handle, LOCK_EX)) {
    fclose($handle);
    send_error('Не удалось заблокировать файл сообщений.', 500);
}

$contents = stream_get_contents($handle);
$messages = empty($contents) ? [] : json_decode($contents, true);

// If JSON is corrupted, start fresh but log the error
if ($messages === null) {
    error_log('Corrupted messages.json detected. Starting fresh.');
    $messages = [];
}

$messages[] = $new_message;

// Go to the beginning of the file, write new content, and truncate to new size
ftruncate($handle, 0);
rewind($handle);
fwrite($handle, json_encode($messages, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
fflush($handle); // Flush output before releasing the lock
flock($handle, LOCK_UN); // Release the lock
fclose($handle);

http_response_code(201); // 201 Created
echo json_encode($new_message);
?>
