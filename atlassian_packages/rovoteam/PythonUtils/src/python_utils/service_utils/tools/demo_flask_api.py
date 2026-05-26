from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/test")
def test():
    return jsonify(message="Test endpoint is working!")


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=8085)

    # Use the following to enable binding to IPv6 interfaces and disable user reloading
    app.run(host="::", port=8085, debug=True, use_reloader=False)

    # To test the api, simply run `curl http://localhost:8085/test`, `curl http://devvm20179.nha0.facebook.com:8085/test`, etc.
