from flask import Flask, request

app = Flask(__name__)


@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Flask Test Site</title>
        <style>
            body {-
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .container {
                border: 1px solid #ddd;
                padding: 20px;
                border-radius: 5px;
            }
            form {
                margin-top: 20px;
            }
            input, button {
                padding: 8px;
                margin: 5px 0;
            }
            button {
                background-color: #4CAF50;
                color: white;
                border: none;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Flask Test Site</h1>
            <p>This is a simple Flask application for testing purposes.</p>

            <form action="/submit" method="post">
                <h3>Test Form</h3>
                <input type="text" name="name" placeholder="Enter your name" required>
                <button type="submit">Submit</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name", "Unknown")
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Form Submitted</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                border: 1px solid #ddd;
                padding: 20px;
                border-radius: 5px;
            }}
            .back-link {{
                margin-top: 20px;
                display: block;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Form Submitted</h1>
            <p>Hello, {name}! Your form was successfully submitted.</p>
            <a href="/" class="back-link">Back to home</a>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    app.run(host="::", port=8085, debug=True, use_reloader=False)
