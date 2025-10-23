<?php
header('Content-Type: application/json; charset=utf-8');

define('UPLOADS_DIR', 'uploads');
define('MESSAGES_FILE', 'messages.json');

if ($_SERVER['REQUEST_METHOD'] !== 'DELETE') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

$id = $_GET['id'] ?? '';
if (empty($id)) {
    http_response_code(400);
    echo json_encode(['error' => 'ID required']);
    exit;
}

$temp_file = MESSAGES_FILE . '.tmp';
$handle = fopen(MESSAGES_FILE, 'r');
if ($handle) {
    $contents = stream_get_contents($handle);
    fclose($handle);
    $messages = empty($contents) ? [] : json_decode($contents, true);
    if ($messages === null) {
        $messages = [];
    }
    foreach ($messages as $key => $msg) {
        if ($msg['id'] === $id) {
            if (isset($msg['file']) && file_exists(UPLOADS_DIR . '/' . $msg['file'])) {
                unlink(UPLOADS_DIR . '/' . $msg['file']);
            }
            if (isset($msg['thumbnail']) && file_exists(UPLOADS_DIR . '/' . $msg['thumbnail'])) {
                unlink(UPLOADS_DIR . '/' . $msg['thumbnail']);
            }
            unset($messages[$key]);
            break;
        }
    }
    $messages = array_values($messages);
    $json_content = json_encode($messages, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
} else {
    $json_content = '[]';
}

if (file_put_contents($temp_file, $json_content) === false) {
    unlink($temp_file);
    http_response_code(500);
    echo json_encode(['error' => 'Failed to update messages']);
    exit;
}
if (rename($temp_file, MESSAGES_FILE)) {
    http_response_code(200);
    echo json_encode(['success' => true]);
} else {
    unlink($temp_file);
    http_response_code(500);
    echo json_encode(['error' => 'Failed to rename temp file']);
}
?>