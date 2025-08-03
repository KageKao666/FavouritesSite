<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');

define('MESSAGES_FILE', 'messages.json');

if (file_exists(MESSAGES_FILE)) {
    readfile(MESSAGES_FILE);
} else {
    echo '[]';
}
?>
