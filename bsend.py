from flask import Flask, render_template_string, request, jsonify
import pyperclip
import os
import pathlib
import subprocess
import sys
import traceback

app = Flask(__name__)

# Используем raw string (r""") чтобы Python не интерпретировал \r и \n в JavaScript коде
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Clipboard Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f4f4f4; }
        h1 { text-align: center; }
        .container { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
        .section {
            flex: 1;
            min-width: 320px;
            max-width: 500px;
            padding: 20px;
            background: #fff;
            border: 1px solid #ccc;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        .section h2 { margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        textarea { width: 100%; height: 150px; font-size: 16px; padding: 10px; box-sizing: border-box; }
        button { font-size: 18px; padding: 6px 16px; margin-top: 10px; cursor: pointer; border-radius: 5px; border: 1px solid #aaa; background: #eee; }
        button:hover { background: #ddd; }
        #paste_area { width: 100%; height: 120px; border: 2px dashed #555; padding: 5px; margin-top: 10px; box-sizing: border-box; }
        #clipboard_content { white-space: pre-wrap; background: #f8f8f8; padding: 10px; border-radius: 5px; height: 200px; overflow-y: auto; border: 1px solid #eee; }
        #copy_clipboard { margin-top: 10px; }

        /* --- Send to files block --- */
        .path-row { display: flex; gap: 8px; align-items: center; margin-top: 10px; }
        .path-row input {
            flex: 1;
            padding: 8px 10px;
            font-size: 14px;
            border: 1px solid #aaa;
            border-radius: 5px;
            font-family: monospace;
            box-sizing: border-box;
        }
        .path-row button { margin-top: 0; font-size: 14px; padding: 6px 10px; white-space: nowrap; }

        #drop-zone {
            border: 3px dashed #34a853;
            border-radius: 12px;
            padding: 30px 10px;
            text-align: center;
            color: #34a853;
            background-color: #f6fbf7;
            transition: all 0.25s;
            cursor: pointer;
            margin-top: 14px;
            user-select: none;
        }
        #drop-zone.hover {
            background-color: #e6f4ea;
            border-color: #2e7d32;
            transform: scale(1.02);
        }
        #drop-zone .icon { font-size: 38px; }
        #drop-zone .label { font-size: 15px; margin-top: 6px; }
        #drop-zone .sub { font-size: 12px; color: #888; margin-top: 4px; }

        #file-input { display: none; }

        #send-status {
            margin-top: 12px;
            padding: 8px 10px;
            font-family: monospace;
            font-size: 13px;
            background: #1e1e1e;
            color: #34a853;
            border-radius: 5px;
            min-height: 40px;
            max-height: 160px;
            overflow-y: auto;
            white-space: pre-wrap;
            border: 1px solid #333;
        }

        /* --- Unix convert toggle --- */
        .unix-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
            padding: 7px 12px;
            background: #f0f7ff;
            border: 1px solid #b3d1f7;
            border-radius: 8px;
            font-size: 13px;
            color: #1a4a7a;
        }
        .unix-row input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; accent-color: #1a73e8; }
        .unix-row label { cursor: pointer; user-select: none; }
        .unix-badge {
            display: inline-block;
            background: #1a73e8;
            color: #fff;
            font-size: 10px;
            font-weight: bold;
            padding: 1px 6px;
            border-radius: 4px;
            letter-spacing: 0.5px;
        }
    </style>
</head>
<body>
    <h1>Clipboard Server</h1>
    <div class="container">

        <!-- Left: Send to Clipboard -->
        <div class="section">
            <h2>📋 Send to Clipboard</h2>
            <form id="clip-form" method="POST" enctype="multipart/form-data">
                <textarea id="clip-text" name="text" placeholder="Enter text..." autofocus></textarea>

                <!-- CRLF→LF toggle -->
                <div class="unix-row">
                    <input type="checkbox" id="unix-convert" checked>
                    <label for="unix-convert">
                        <span class="unix-badge">CRLF→LF</span>
                        Конвертировать переносы строк (Windows → Linux)
                    </label>
                </div>

                <button type="submit" name="action" value="text">📋 Copy Text</button>
            </form>

            <p style="margin-top:18px; margin-bottom:4px;">Paste image here (Ctrl+V):</p>
            <div id="paste_area" contenteditable="true"></div>
        </div>

        <!-- Right: Server Clipboard -->
        <div class="section">
            <h2>🖥️ Server Clipboard Content</h2>
            <button id="refresh">🔄 Refresh</button>
            <div id="clipboard_content">{{ last_text | e }}</div>
            <button id="copy_clipboard">📋 Copy to Local Clipboard</button>
        </div>

        <!-- Send to files -->
        <div class="section">
            <h2>📤 Send to Files</h2>

            <label style="font-size:13px; color:#555;">Target path on server:</label>
            <div class="path-row">
                <input type="text" id="target-path" value="/var/www/html/wordpress/files/" spellcheck="false">
                <button onclick="resetPath()">↩️</button>
            </div>

            <div id="drop-zone">
                <div class="icon">📥</div>
                <div class="label"><strong>Drop files or folder here</strong></div>
                <div class="sub">or click to select files</div>
            </div>
            <input type="file" id="file-input" multiple webkitdirectory>

            <div id="send-status">Status: Ready</div>
        </div>

    </div>

    <script>
    // ===== CRLF→LF + отправка через fetch (не перезагружая страницу) =====
    document.getElementById('clip-form').addEventListener('submit', function(e) {
        e.preventDefault();  // останавливаем стандартную отправку формы
        console.log('Form submitted');

        const ta  = document.getElementById('clip-text');
        let text  = ta.value;

        if (document.getElementById('unix-convert').checked) {
            // Используем правильные regex для замены переносов строк
            text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
            console.log('Text converted to Unix line endings');
        }

        const fd = new FormData();
        fd.append('action', 'text');
        fd.append('text', text);

        fetch('/', { method: 'POST', body: fd })
            .then(r => {
                console.log('Response received:', r.status);
                return r.text();
            })
            .then(() => {
                console.log('Text copied to clipboard');
                // Краткая визуальная обратная связь
                const btn = e.submitter || document.querySelector('#clip-form button[type=submit]');
                const orig = btn.textContent;
                btn.textContent = '✅ Скопировано!';
                btn.disabled = true;
                setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 1200);
            })
            .catch(err => {
                console.error('Error copying text:', err);
                alert('Ошибка: ' + err);
            });
    });

    // ===== Clipboard: paste image =====
    const pasteArea = document.getElementById('paste_area');
    pasteArea.addEventListener('paste', event => {
        console.log('Paste event detected');
        const items = (event.clipboardData || event.originalEvent.clipboardData).items;
        for (const item of items) {
            if (item.type.indexOf('image') !== -1) {
                console.log('Image found in clipboard');
                const blob = item.getAsFile();
                const reader = new FileReader();
                reader.onload = function(e) {
                    console.log('Sending image to server...');
                    fetch('/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/octet-stream' },
                        body: new Uint8Array(e.target.result)
                    }).then(r => r.text())
                    .then(t => {
                        console.log('Image uploaded:', t);
                        alert(t);
                    })
                    .catch(err => {
                        console.error('Failed to send image:', err);
                        alert('Failed to send image: ' + err);
                    });
                };
                reader.readAsArrayBuffer(blob);
            }
        }
    });

    // ===== Clipboard: refresh & copy =====
    document.getElementById('refresh').addEventListener('click', () => {
        console.log('Refresh button clicked');
        fetch('/get_clipboard')
            .then(r => {
                console.log('Clipboard fetch response:', r.status);
                return r.json();
            })
            .then(data => { 
                console.log('Clipboard content received:', data.text.substring(0, 50) + '...');
                document.getElementById('clipboard_content').textContent = data.text; 
            })
            .catch(err => {
                console.error('Failed to fetch clipboard:', err);
                alert('Failed to fetch clipboard: ' + err);
            });
    });

    document.getElementById('copy_clipboard').addEventListener('click', () => {
        console.log('Copy to local clipboard button clicked');
        const text = document.getElementById('clipboard_content').textContent;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => {
                    console.log('Copied to local clipboard');
                    alert('Copied to local clipboard!');
                })
                .catch(() => fallbackCopy(text));
        } else {
            fallbackCopy(text);
        }
    });

    function fallbackCopy(text) {
        console.log('Using fallback copy method');
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            if (document.execCommand('copy')) {
                console.log('Fallback copy successful');
                alert('Copied to local clipboard!');
            } else {
                alert('Failed to copy. Please copy manually.');
            }
        } catch (err) { 
            console.error('Fallback copy failed:', err);
            alert('Failed to copy: ' + err); 
        }
        document.body.removeChild(ta);
    }

    // ===== Send to Files =====
    const dropZone   = document.getElementById('drop-zone');
    const fileInput  = document.getElementById('file-input');
    const statusBox  = document.getElementById('send-status');
    const pathInput  = document.getElementById('target-path');
    const DEFAULT_PATH = '/var/www/html/wordpress/files/';

    function resetPath() { 
        pathInput.value = DEFAULT_PATH; 
        console.log('Path reset to default');
    }

    function setStatus(msg) { 
        statusBox.innerText = msg; 
        console.log('Status:', msg);
    }

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('hover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('hover'));

    dropZone.addEventListener('drop', async e => {
        e.preventDefault();
        dropZone.classList.remove('hover');
        console.log('Files dropped');
        const items = e.dataTransfer.items;
        if (!items) return;

        setStatus('⏳ Reading files...');
        const allFiles = [];

        async function traverse(entry) {
            if (entry.isFile) {
                const file = await new Promise(res => entry.file(res));
                const buf  = await new Promise(res => {
                    const r = new FileReader();
                    r.onload = ev => res(ev.target.result);
                    r.readAsDataURL(file);           // base64 — handles binary too
                });
                let p = entry.fullPath.startsWith('/') ? entry.fullPath.substring(1) : entry.fullPath;
                allFiles.push({ path: p, data: buf });
            } else if (entry.isDirectory) {
                const reader = entry.createReader();
                let batch;
                do {
                    batch = await new Promise(res => reader.readEntries(res));
                    for (const child of batch) await traverse(child);
                } while (batch.length > 0);
            }
        }

        const tasks = [];
        for (let i = 0; i < items.length; i++) {
            const entry = items[i].webkitGetAsEntry();
            if (entry) tasks.push(traverse(entry));
        }
        await Promise.all(tasks);

        console.log(`Found ${allFiles.length} files`);
        await uploadFiles(allFiles);
    });

    fileInput.addEventListener('change', async () => {
        const files = fileInput.files;
        if (!files.length) return;
        console.log(`Selected ${files.length} files`);
        setStatus('⏳ Reading files...');
        const allFiles = [];
        for (const file of files) {
            const buf = await new Promise(res => {
                const r = new FileReader();
                r.onload = ev => res(ev.target.result);
                r.readAsDataURL(file);
            });
            allFiles.push({ path: file.webkitRelativePath || file.name, data: buf });
        }
        await uploadFiles(allFiles);
        fileInput.value = '';   // reset so same folder can be dropped again
    });

    async function uploadFiles(allFiles) {
        const basePath = pathInput.value.replace(/\/?$/, '/');
        setStatus(`🚀 Uploading ${allFiles.length} file(s) to ${basePath}...\n`);
        console.log(`Uploading ${allFiles.length} files to ${basePath}`);

        let ok = 0, fail = 0;
        for (const f of allFiles) {
            try {
                const res = await fetch('/send_to_files', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ base_path: basePath, rel_path: f.path, data: f.data })
                });
                const json = await res.json();
                if (res.ok) {
                    ok++;
                    statusBox.innerText += `  ✅ ${json.saved}\n`;
                    console.log(`Uploaded: ${json.saved}`);
                } else {
                    fail++;
                    statusBox.innerText += `  ❌ ${f.path} — ${json.error}\n`;
                    console.error(`Failed to upload ${f.path}:`, json.error);
                }
            } catch (err) {
                fail++;
                statusBox.innerText += `  ❌ ${f.path} — ${err}\n`;
                console.error(`Error uploading ${f.path}:`, err);
            }
        }
        statusBox.innerText += `\n✨ Done: ${ok} saved, ${fail} failed.`;
        console.log(`Upload complete: ${ok} saved, ${fail} failed`);
    }

    console.log('Clipboard server initialized');
    </script>
</body>
</html>
"""

last_text = ""

@app.route("/", methods=["GET", "POST"])
def index():
    global last_text
    try:
        if request.method == "POST":
            if request.form.get("action") == "text":
                text = request.form.get("text")
                if text:
                    # Конвертируем CRLF→LF на сервере (надёжнее чем в JS)
                    text = text.replace('\r\n', '\n').replace('\r', '\n')
                    pyperclip.copy(text)
                    last_text = text
                    print(f"[INFO] Text copied to clipboard: {len(text)} characters")
            else:
                if request.data:
                    filepath = '/tmp/uploaded_image.png'
                    with open(filepath, 'wb') as f:
                        f.write(request.data)

                    display = os.environ.get('DISPLAY', ':0')
                    xauth = pathlib.Path.home() / '.Xauthority'
                    env = os.environ.copy()
                    env['DISPLAY'] = display
                    env['XAUTHORITY'] = str(xauth)

                    if subprocess.run(['which', 'xclip'], capture_output=True).returncode != 0:
                        print("[ERROR] xclip not installed")
                        return "xclip not installed", 500

                    result = subprocess.run(
                        ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', filepath],
                        env=env, capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        print(f"[ERROR] Failed to copy image: {result.stderr}")
                        return f"Failed to copy image to clipboard:\n{result.stderr}", 500

                    print("[INFO] Image uploaded and copied to clipboard")
                    return "Image uploaded and copied to clipboard!", 200

    except Exception as e:
        print(f"[ERROR] Server error: {traceback.format_exc()}")
        return f"Server error:\n{traceback.format_exc()}", 500

    return render_template_string(HTML_TEMPLATE, last_text=last_text)


@app.route("/get_clipboard", methods=["GET"])
def get_clipboard():
    try:
        text = pyperclip.paste()
        print(f"[INFO] Clipboard content requested: {len(text)} characters")
        return jsonify({"text": text})
    except Exception as e:
        print(f"[ERROR] Failed to get clipboard: {str(e)}")
        return jsonify({"text": f"Error: {str(e)}"})


# ─── New endpoint: save file to disk ─────────────────────────────────────────
import base64, mimetypes

@app.route("/send_to_files", methods=["POST"])
def send_to_files():
    try:
        payload   = request.get_json(force=True)
        base_path = payload.get("base_path", "/var/www/html/wordpress/files/")
        rel_path  = payload.get("rel_path", "")
        data_uri  = payload.get("data", "")

        if not rel_path:
            print("[ERROR] rel_path is empty")
            return jsonify({"error": "rel_path is empty"}), 400
        if not data_uri:
            print("[ERROR] no data")
            return jsonify({"error": "no data"}), 400

        # Decode base64 data-URI  →  raw bytes
        # Format: "data:<mime>;base64,<payload>"
        if "," in data_uri:
            header, b64 = data_uri.split(",", 1)
        else:
            b64 = data_uri                          # fallback: raw base64

        raw_bytes = base64.b64decode(b64)

        # Build full path safely (strip leading / from rel_path)
        rel_path  = rel_path.lstrip("/")
        full_path = os.path.join(base_path, rel_path)
        full_path = os.path.normpath(full_path)

        # Security: make sure the resolved path is still inside base_path
        if not full_path.startswith(os.path.normpath(base_path)):
            print(f"[SECURITY] Path traversal blocked: {full_path}")
            return jsonify({"error": "Path traversal blocked"}), 403

        # Create directories and write
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(raw_bytes)

        print(f"[INFO] File saved: {full_path} ({len(raw_bytes)} bytes)")
        return jsonify({"saved": full_path}), 200

    except Exception as e:
        print(f"[ERROR] Failed to save file: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = 5555
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    print(f"[INFO] Starting clipboard server on port {port}")
    app.run(host="0.0.0.0", port=port)
