import os
import json

# Define the target directory
target_dir = '/storage/emulated/0/Download/Structure'

# Create the directory if it doesn't exist
os.makedirs(target_dir, exist_ok=True)
os.makedirs(os.path.join(target_dir, 'uploads'), exist_ok=True)

# Create empty messages.json
messages_json_path = os.path.join(target_dir, 'messages.json')
with open(messages_json_path, 'w', encoding='utf-8') as f:
    json.dump([], f, ensure_ascii=False, indent=2)

# messages.php (unchanged)
messages_php = '''<?php
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
?>'''

with open(os.path.join(target_dir, 'messages.php'), 'w', encoding='utf-8') as f:
    f.write(messages_php)

# upload.php (unchanged)
upload_php = '''<?php
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
?>'''

with open(os.path.join(target_dir, 'upload.php'), 'w', encoding='utf-8') as f:
    f.write(upload_php)

# delete.php
delete_php = '''<?php
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
?>'''

with open(os.path.join(target_dir, 'delete.php'), 'w', encoding='utf-8') as f:
    f.write(delete_php)

# Completely redesigned index.html
index_html = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Избранное</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent !important;
            outline: none !important;
        }

        *:focus {
            outline: none !important;
            box-shadow: none !important;
        }

        *:active {
            outline: none !important;
        }

        :root {
            --bg-primary: #000000;
            --bg-secondary: #000000;
            --bg-message: #0a0a0a;
            --bg-input: #0a0a0a;
            --text-primary: #ffffff;
            --text-secondary: #808080;
            --accent: #ffffff;
            --accent-hover: #e8e8e8;
            --border: #1a1a1a;
            --delete-color: #ff4444;
            --shadow: rgba(0, 0, 0, 0.9);
        }

        html {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            scroll-behavior: smooth;
        }

        body {
            background: #000000;
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            width: 100%;
            max-width: 900px;
            height: 90vh;
            max-height: 900px;
            background: var(--bg-secondary);
            border-radius: 24px;
            box-shadow: 0 0 0 1px var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid var(--border);
        }

        #messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            -webkit-overflow-scrolling: touch;
        }

        #messages-container::-webkit-scrollbar {
            display: none;
        }

        #messages-container {
            scrollbar-width: none;
        }

        .message {
            background: var(--bg-message);
            border-radius: 16px;
            padding: 16px;
            max-width: 80%;
            align-self: flex-end;
            position: relative;
            border: 1px solid var(--border);
            transition: all 0.2s ease;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }

        .message:hover {
            border-color: #2a2a2a;
            box-shadow: 0 4px 12px rgba(255, 255, 255, 0.05);
        }



        .message-text {
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 8px;
            white-space: pre-wrap;
            color: var(--text-primary);
            word-break: break-word;
        }

        .message-text a {
            color: var(--accent);
            text-decoration: underline;
            pointer-events: auto;
        }

        .message-text a:hover {
            opacity: 0.8;
        }

        .code-block {
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            margin: 8px 0;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: all;
            outline: none;
            -webkit-tap-highlight-color: transparent;
        }

        .code-block:hover {
            border-color: var(--accent);
            background: #121212;
        }

        .code-block::after {
            content: '';
        }



        .file-link {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--accent);
            text-decoration: none;
            font-size: 14px;
            padding: 6px 12px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            transition: all 0.2s ease;
            margin: 8px 0;
        }

        .file-link:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateX(4px);
        }

        .message-image {
            max-width: 100%;
            border-radius: 12px;
            margin-top: 8px;
            cursor: pointer;
            transition: transform 0.2s ease;
        }

        .message-image:hover {
            transform: scale(1.02);
        }

        #form-container {
            padding: 20px 24px;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border);
        }

        .form-wrapper {
            display: flex;
            align-items: flex-end;
            gap: 8px;
            background: var(--bg-input);
            border-radius: 16px;
            padding: 8px;
            border: 1px solid var(--border);
            transition: border-color 0.2s ease;
        }

        .form-wrapper:focus-within {
            border-color: var(--accent);
        }

        textarea {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-size: 15px;
            resize: none;
            min-height: 24px;
            max-height: 120px;
            font-family: inherit;
            line-height: 1.5;
            padding: 8px 12px;
            overflow-y: auto;
        }

        textarea::-webkit-scrollbar {
            display: none;
        }

        textarea {
            scrollbar-width: none;
        }

        textarea:focus {
            outline: none !important;
            box-shadow: none !important;
        }

        textarea::placeholder {
            color: var(--text-secondary);
        }

        .icon-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            transition: all 0.2s ease;
        }

        .icon-btn {
            color: var(--text-secondary);
        }

        .icon-btn:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-primary);
        }

        .icon-btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }

        .send-btn {
            background: transparent;
            color: var(--accent);
        }

        .send-btn:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.08);
            color: var(--accent);
        }

        .file-preview {
            font-size: 13px;
            color: var(--text-secondary);
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            margin-bottom: 8px;
            display: inline-block;
        }

        .progress-container {
            width: 100%;
            height: 4px;
            background: var(--bg-input);
            border-radius: 2px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #ffffff, #e8e8e8);
            width: 0%;
            transition: width 0.3s ease;
        }



        .loading {
            text-align: center;
            color: var(--text-secondary);
            padding: 40px;
            font-size: 14px;
        }

        @media (max-width: 768px) {
            .container {
                height: 100vh;
                max-height: none;
                border-radius: 0;
            }

            body {
                padding: 0;
            }

            #messages-container {
                padding: 20px 16px;
            }

            #form-container {
                padding: 16px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div id="messages-container">
            <div class="loading">Загрузка сообщений...</div>
        </div>

        <div id="form-container">
            <div id="file-preview"></div>
            <div id="progress-wrapper" style="display: none;">
                <div class="progress-container">
                    <div class="progress-bar" id="progress-bar"></div>
                </div>
            </div>
            <form id="messageForm">
                <div class="form-wrapper">
                    <label for="file" class="icon-btn" title="Прикрепить файл">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.49"></path>
                        </svg>
                    </label>
                    <input type="file" id="file" name="file" style="display: none;">
                    <textarea name="message" placeholder="Введите сообщение..." rows="1"></textarea>
                    <button type="submit" class="icon-btn send-btn" title="Отправить (Ctrl+Enter)" disabled>
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
            </form>
        </div>
    </div>

    <div id="toast" class="toast" style="display: none;"></div>

    <script>
        const messagesContainer = document.getElementById('messages-container');
        const messageForm = document.getElementById('messageForm');
        const textarea = document.querySelector('textarea[name="message"]');
        const fileInput = document.getElementById('file');
        const submitBtn = document.querySelector('.send-btn');
        const filePreview = document.getElementById('file-preview');
        const progressWrapper = document.getElementById('progress-wrapper');
        const progressBar = document.getElementById('progress-bar');
        const toast = document.getElementById('toast');

        let pollInterval;

        const escapeHTML = (str) => {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        };

        const linkify = (text) => {
            const urlRegex = /(https?:\/\/[^\s<]+|http:\/\/[^\s<]+)/g;
            return text.replace(urlRegex, url => {
                return `<a href="${url}" target="_blank" rel="noopener">${escapeHTML(url)}</a>`;
            });
        };

        const updateSubmitButton = () => {
            const hasContent = textarea.value.trim().length > 0 || fileInput.files.length > 0;
            submitBtn.disabled = !hasContent;
        };

        const createMessageElement = (msg) => {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';
            messageDiv.dataset.id = msg.id;

            let content = '';

            if (msg.text) {
                const text = msg.text.trim();
                if (text.startsWith('/') && text.endsWith('/') && text.length > 2 && !text.startsWith('//')) {
                    const code = text.slice(1, -1);
                    content += `<div class="code-block">${escapeHTML(code)}</div>`;
                } else {
                    const escapedText = escapeHTML(text);
                    const linkedText = linkify(escapedText);
                    content += `<div class="message-text">${linkedText}</div>`;
                }
            }

            if (msg.file) {
                const isImage = /\.(jpe?g|png|gif|webp|svg)$/i.test(msg.originalFilename || '');
                if (isImage) {
                    const imgSrc = msg.thumbnail ? `uploads/${msg.thumbnail}` : `uploads/${msg.file}`;
                    content += `<a href="uploads/${msg.file}" target="_blank">
                        <img src="${imgSrc}" class="message-image" alt="Image" loading="lazy">
                    </a>`;
                } else {
                    content += `<a href="uploads/${msg.file}" class="file-link" download="${escapeHTML(msg.originalFilename || 'file')}">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                            <polyline points="13 2 13 9 20 9"></polyline>
                        </svg>
                        ${escapeHTML(msg.originalFilename || 'file')}
                    </a>`;
                }
            }

            const time = new Date(msg.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

            messageDiv.innerHTML = content;
            return messageDiv;
        };

        const renderMessages = (messages) => {
            messagesContainer.innerHTML = '';
            if (messages.length === 0) {
                messagesContainer.innerHTML = '<div class="loading">Сообщений пока нет</div>';
                return;
            }
            messages.forEach(msg => messagesContainer.appendChild(createMessageElement(msg)));
            requestAnimationFrame(() => messagesContainer.scrollTop = messagesContainer.scrollHeight);
        };

        const loadMessages = async () => {
            try {
                const response = await fetch('messages.php?t=' + Date.now());
                if (!response.ok) throw new Error('Network error');
                const messages = await response.json();
                renderMessages(messages);
            } catch (error) {
                console.error('Load error:', error);
                messagesContainer.innerHTML = '<div class="loading">Ошибка загрузки</div>';
            }
        };

        messagesContainer.addEventListener('click', async (e) => {
            const codeBlock = e.target.closest('.code-block');
            if (codeBlock) {
                const selection = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(codeBlock);
                selection.removeAllRanges();
                selection.addRange(range);
                try {
                    document.execCommand('copy');
                    selection.removeAllRanges();
                } catch (err) {
                    console.error('Copy failed');
                }
                return;
            }
        });

        messageForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(messageForm);

            if (textarea.value.trim() === '!delete') {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', 'upload.php');
                xhr.onload = () => {
                    if (xhr.status === 200) {
                        loadMessages();
                        messageForm.reset();
                        filePreview.innerHTML = '';
                        textarea.style.height = 'auto';
                        updateSubmitButton();
                    }
                };
                xhr.send(formData);
                return;
            }

            const xhr = new XMLHttpRequest();
            xhr.open('POST', 'upload.php');

            if (fileInput.files.length > 0) {
                progressWrapper.style.display = 'block';
                xhr.upload.addEventListener('progress', (evt) => {
                    if (evt.lengthComputable) {
                        const percent = Math.round((evt.loaded / evt.total) * 100);
                        progressBar.style.width = percent + '%';
                    }
                });
            }

            xhr.onload = () => {
                progressWrapper.style.display = 'none';
                progressBar.style.width = '0%';
                if (xhr.status === 201) {
                    loadMessages();
                    messageForm.reset();
                    filePreview.innerHTML = '';
                    textarea.style.height = 'auto';
                    updateSubmitButton();
                } else {
                    console.error('Upload failed');
                }
            };

            xhr.onerror = () => {
                progressWrapper.style.display = 'none';
                console.error('Network error');
            };

            xhr.send(formData);
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                filePreview.innerHTML = `<span class="file-preview">📎 ${escapeHTML(fileInput.files[0].name)}</span>`;
            } else {
                filePreview.innerHTML = '';
            }
            updateSubmitButton();
        });

        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
            updateSubmitButton();
        });

        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                if (!submitBtn.disabled) {
                    messageForm.requestSubmit();
                }
            }
        });

        pollInterval = setInterval(loadMessages, 3000);
        loadMessages();
        updateSubmitButton();
    </script>
</body>
</html>'''

with open(os.path.join(target_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(index_html)

print(f"✅ Структура успешно создана в {target_dir}")
print("\nСозданные файлы:")
print("  • messages.json")
print("  • messages.php")
print("  • upload.php")
print("  • delete.php")
print("  • index.html")
print("  • uploads/ (папка)")
print("\n🎨 Что изменено:")
print("  ✓ Современный дизайн с градиентами и анимациями")
print("  ✓ Убрана поддержка Markdown")
print("  ✓ Исправлено копирование для //текст//")
print("  ✓ Улучшенная адаптивность")
print("  ✓ Плавные анимации и переходы")
print("  ✓ Исправлены все баги")