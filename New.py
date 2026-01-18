from flask import Flask, render_template_string, request, jsonify
import pyperclip
import os
import pathlib
import subprocess
import sys
import traceback

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Clipboard Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { display: flex; gap: 40px; }
        .section { flex: 1; padding: 20px; border: 1px solid #ccc; border-radius: 8px; }
        textarea { width: 100%; height: 150px; font-size: 16px; padding: 10px; }
        button { font-size: 20px; padding: 5px 15px; margin-top: 10px; cursor: pointer; }
        #paste_area { width: 100%; height: 200px; border: 2px dashed #555; padding: 5px; margin-top: 10px; }
        #clipboard_content { white-space: pre-wrap; background: #f8f8f8; padding: 10px; border-radius: 5px; height: 330px; overflow-y: auto; }
        #copy_clipboard { margin-top: 10px; }
    </style>
</head>
<body>
    <h1>Clipboard Server</h1>
    <div class="container">
        <!-- Left side: send -->
        <div class="section">
            <h2>Send to Clipboard</h2>
            <form method="POST" enctype="multipart/form-data">
                <textarea name="text" placeholder="Enter text..." autofocus></textarea><br>
                <button type="submit" name="action" value="text">📋 Copy Text</button>
            </form>

            <p>Paste image here (Ctrl+V):</p>
            <div id="paste_area" contenteditable="true"></div>
        </div>

        <!-- Right side: request -->
        <div class="section">
            <h2>Server Clipboard Content</h2>
            <button id="refresh">🔄 Refresh</button>
            <div id="clipboard_content">{{ last_text }}</div>
            <button id="copy_clipboard">📋 Copy to Local Clipboard</button>
        </div>
    </div>

    <script>
        // Handle image paste
        const pasteArea = document.getElementById('paste_area');
        pasteArea.addEventListener('paste', event => {
            const items = (event.clipboardData || event.originalEvent.clipboardData).items;
            for (const item of items) {
                if (item.type.indexOf('image') !== -1) {
                    const blob = item.getAsFile();
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        fetch('/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/octet-stream' },
                            body: new Uint8Array(e.target.result)
                        }).then(r => r.text())
                        .then(t => alert(t))
                        .catch(err => alert('Failed to send image: ' + err));
                    };
                    reader.readAsArrayBuffer(blob);
                }
            }
        });

        // Refresh clipboard content
        const refreshBtn = document.getElementById('refresh');
        const clipboardDiv = document.getElementById('clipboard_content');

        refreshBtn.addEventListener('click', () => {
            fetch('/get_clipboard')
                .then(r => r.json())
                .then(data => {
                    clipboardDiv.textContent = data.text;
                })
                .catch(err => alert('Failed to fetch clipboard: ' + err));
        });

        // Copy clipboard content to local clipboard with fallback
        const copyBtn = document.getElementById('copy_clipboard');
        copyBtn.addEventListener('click', () => {
            const text = clipboardDiv.textContent;
            
            // Try modern clipboard API first
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text)
                    .then(() => alert('Copied to local clipboard!'))
                    .catch(err => {
                        console.error('Clipboard API failed:', err);
                        fallbackCopy(text);
                    });
            } else {
                // Use fallback method
                fallbackCopy(text);
            }
        });

        // Fallback copy method using temporary textarea
        function fallbackCopy(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            
            try {
                const successful = document.execCommand('copy');
                if (successful) {
                    alert('Copied to local clipboard!');
                } else {
                    alert('Failed to copy. Please copy manually.');
                }
            } catch (err) {
                console.error('Fallback copy failed:', err);
                alert('Failed to copy: ' + err);
            }
            
            document.body.removeChild(textarea);
        }
    </script>
</body>
</html>
"""

last_text = ""  # Сохраняем последний текст, скопированный в буфер

@app.route("/", methods=["GET", "POST"])
def index():
    global last_text
    try:
        if request.method == "POST":
            if request.form.get("action") == "text":
                text = request.form.get("text")
                if text:
                    pyperclip.copy(text)
                    last_text = text
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
                        return "xclip not installed", 500

                    result = subprocess.run(
                        ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', filepath],
                        env=env,
                        capture_output=True,
                        text=True
                    )

                    if result.returncode != 0:
                        return f"Failed to copy image to clipboard:\n{result.stderr}", 500

                    return "Image uploaded and copied to clipboard!", 200

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return f"Server error:\n{tb}", 500

    return render_template_string(HTML_TEMPLATE, last_text=last_text)

@app.route("/get_clipboard", methods=["GET"])
def get_clipboard():
    try:
        text = pyperclip.paste()
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"text": f"Error: {str(e)}"})

if __name__ == "__main__":
    port = 5555
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    app.run(host="0.0.0.0", port=port)
