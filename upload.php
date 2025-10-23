<?php
header('Content-Type: application/json; charset=utf-8');

define('UPLOADS_DIR', 'uploads');
define('MESSAGES_FILE', 'messages.json');
$blacklisted_extensions = ['php', 'phtml', 'php3', 'php4', 'php5', 'php7', 'phps', 'phar', 'htaccess', 'sh', 'exe', 'bat', 'cmd', 'js', 'asp', 'aspx'];

function send_error($message, $code = 400) {
    http_response_code($code);
    echo json_encode(['error' => $message]);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    send_error('Неверный метод запроса', 405);
}

if (!is_dir(UPLOADS_DIR) && !mkdir(UPLOADS_DIR, 0755, true)) {
    send_error('Не удалось создать директорию для загрузок.', 500);
}

$message_text = isset($_POST['message']) ? trim($_POST['message']) : '';
$file = isset($_FILES['file']) ? $_FILES['file'] : null;

if ($message_text === '!delete') {
    // Delete all files in uploads directory
    $files = glob(UPLOADS_DIR . '/*');
    foreach($files as $file_path) {
        if(is_file($file_path)) {
            unlink($file_path);
        }
    }
    
    // Clear messages.json
    $handle = fopen(MESSAGES_FILE, 'c+');
    if ($handle) {
        flock($handle, LOCK_EX);
        ftruncate($handle, 0);
        rewind($handle);
        fwrite($handle, '[]');
        fflush($handle);
        flock($handle, LOCK_UN);
        fclose($handle);
    }
    http_response_code(200);
    echo json_encode(['success' => 'All data deleted']);
    exit;
}

if (empty($message_text) && (!$file || $file['error'] !== UPLOAD_ERR_OK)) {
    send_error('Сообщение не может быть пустым, если не прикреплен файл.');
}

$saved_filename = null;
$original_filename = null;
$thumbnail = null;

if ($file && $file['error'] === UPLOAD_ERR_OK) {
    $original_filename = basename($file['name']);
    $extension = strtolower(pathinfo($original_filename, PATHINFO_EXTENSION));

    if (in_array($extension, $blacklisted_extensions, true)) {
        send_error('Недопустимый тип файла.', 403);
    }

    $safe_extension = preg_replace('/[^a-z0-9]/', '', $extension);
    $saved_filename = uniqid('file_', true) . ($safe_extension ? '.' . $safe_extension : '');

    if (!move_uploaded_file($file['tmp_name'], UPLOADS_DIR . '/' . $saved_filename)) {
        send_error('Не удалось сохранить загруженный файл.', 500);
    }

    $image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
    if (in_array($extension, $image_extensions)) {
        $thumbnail = 'thumb_' . $saved_filename;
        $thumb_path = UPLOADS_DIR . '/' . $thumbnail;
        if (function_exists('imagecreatefromjpeg') || function_exists('imagecreatefrompng')) {
            $source = null;
            if ($extension === 'jpg' || $extension === 'jpeg') {
                $source = imagecreatefromjpeg(UPLOADS_DIR . '/' . $saved_filename);
            } elseif ($extension === 'png') {
                $source = imagecreatefrompng(UPLOADS_DIR . '/' . $saved_filename);
            } elseif ($extension === 'gif') {
                $source = imagecreatefromgif(UPLOADS_DIR . '/' . $saved_filename);
            } elseif ($extension === 'webp' && function_exists('imagecreatefromwebp')) {
                $source = imagecreatefromwebp(UPLOADS_DIR . '/' . $saved_filename);
            }
            if ($source) {
                $width = imagesx($source);
                $height = imagesy($source);
                $max_thumb_size = 400;
                $thumb_width = $max_thumb_size;
                $thumb_height = ($height * $max_thumb_size) / $width;
                if ($thumb_height > $max_thumb_size) {
                    $thumb_height = $max_thumb_size;
                    $thumb_width = ($width * $max_thumb_size) / $height;
                }
                $thumb = imagecreatetruecolor($thumb_width, $thumb_height);
                imagecopyresampled($thumb, $source, 0, 0, 0, 0, $thumb_width, $thumb_height, $width, $height);
                if ($extension === 'jpg' || $extension === 'jpeg') {
                    imagejpeg($thumb, $thumb_path, 80);
                } else {
                    imagepng($thumb, $thumb_path, 6);
                }
                imagedestroy($source);
                imagedestroy($thumb);
            }
        }
    }
}

$new_message = [
    'id'               => uniqid(),
    'text'             => $message_text,
    'file'             => $saved_filename,
    'thumbnail'        => $thumbnail,
    'originalFilename' => $original_filename,
    'timestamp'        => date('c')
];

$temp_file = MESSAGES_FILE . '.tmp';
$json_content = json_encode([], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
$handle = fopen(MESSAGES_FILE, 'r');
if ($handle) {
    $contents = stream_get_contents($handle);
    fclose($handle);
    $messages = empty($contents) ? [] : json_decode($contents, true);
    if ($messages === null) {
        $messages = [];
    }
    $messages[] = $new_message;
    $json_content = json_encode($messages, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
}

if (file_put_contents($temp_file, $json_content) === false) {
    unlink($temp_file);
    send_error('Не удалось сохранить файл сообщений.', 500);
} else {
    if (rename($temp_file, MESSAGES_FILE)) {
        http_response_code(201);
        echo json_encode($new_message);
    } else {
        unlink($temp_file);
        send_error('Не удалось обновить файл сообщений.', 500);
    }
}
?>