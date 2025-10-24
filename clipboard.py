from flask import Flask, render_template_string, request
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
        body { font-family: Arial, sans-serif; margin: 40px; }
        textarea { width: 100%; max-width: 600px; height: 150px; font-size: 16px; padding: 10px; }
        button { font-size: 20px; padding: 5px 15px; margin-top: 10px; cursor: pointer; }
        #paste_area { width: 300px; height: 200px; border: 2px dashed #555; margin-top: 20px; padding: 5px; }
        .section { margin-bottom: 40px; }
    </style>
</head>
<body>
    <h1>Clipboard Server</h1>

    <div class="section">
        <h2>Send Text</h2>
        <form method="POST" enctype="multipart/form-data">
            <textarea name="text" placeholder="Enter text..." autofocus></textarea><br>
            <button type="submit" name="action" value="text">📋 Copy Text</button>
        </form>
        {% if text_message %}
        <pre>{{ text_message }}</pre>
        {% endif %}
    </div>

    <div class="section">
        <h2>Send Image</h2>
        <p>Click inside the box and paste an image (Ctrl+V):</p>
        <div id="paste_area" contenteditable="true"></div>
        {% if image_message %}
        <p>{{ image_message }}</p>
        {% endif %}
    </div>

    <script>
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
    </script>
</body>
</html>
"""

last_text = ""

@app.route("/", methods=["GET", "POST"])
def index():
    global last_text
    text_message = ""
    image_message = ""

    try:
        if request.method == "POST":
            if request.form.get("action") == "text":
                text = request.form.get("text")
                if text:
                    pyperclip.copy(text)
                    last_text = text
                    text_message = f"Text copied to clipboard:\n{text}"
            else:
                # Если данные приходят как raw image
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

                    image_message = "Image uploaded and copied to clipboard!"

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return f"Server error:\n{tb}", 500

    return render_template_string(HTML_TEMPLATE, text_message=last_text, image_message=image_message)

if __name__ == "__main__":
    port = 5555
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    app.run(host="0.0.0.0", port=port)
