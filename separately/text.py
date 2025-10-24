from flask import Flask, render_template_string, request
import pyperclip

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Clipboard Server</title>
</head>
<body>
    <h1>Send text to server clipboard</h1>
    <form method="POST">
        <textarea name="text" placeholder="Enter text" rows="10" cols="60" required autofocus></textarea><br>
        <button type="submit">?</button>
    </form>

    {% if message %}
    <h2>Last copied text:</h2>
    <pre>{{ message }}</pre>
    {% endif %}
</body>
</html>
"""

last_text = ""

@app.route("/", methods=["GET", "POST"])
def index():
    global last_text
    if request.method == "POST":
        text = request.form.get("text")
        if text:
            pyperclip.copy(text)
            last_text = text
    return render_template_string(HTML_TEMPLATE, message=last_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5555)
