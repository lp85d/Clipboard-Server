from flask import Flask, request
import os
import subprocess
import pathlib
import sys
import traceback

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def upload_image():
    try:
        if request.method == 'POST':
            if not request.data:
                return "No image data received", 400

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
                return f"Failed to copy to clipboard:\\n{result.stderr}", 500

            return "Image uploaded and copied to clipboard!", 200

        # HTML ??? ??????? ???????????
        return '''
        <!doctype html>
        <html>
        <body>
            <h1>Paste image from Clipboard</h1>
            <p>Click here and press Ctrl+V to send the image to server clipboard:</p>
            <div id="paste_area" contenteditable="true" style="width:300px; height:200px; border:1px solid #000;"></div>
            <script>
            const pasteArea = document.getElementById('paste_area');
            pasteArea.focus();
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
        '''
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return f"Server error:\\n{tb}", 500

if __name__ == '__main__':
    port = 5000
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    app.run(host='0.0.0.0', port=port, debug=True)
