from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/test_args", methods=["POST"])
def test_args():
    """
    Endpoint that takes three arguments: prompt, model, and key.
    Returns them in a dictionary without any further processing.

    Expects JSON payload with:
    - prompt: a very long and possibly non-ascii string
    - model: string
    - key: string
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify(error="No JSON data provided"), 400

        prompt = data.get("prompt")
        model = data.get("model")
        key = data.get("key")

        # Return the arguments as a dictionary
        return jsonify({"prompt": prompt, "model": model, "key": key})

    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/test")
def test():
    return jsonify(message="Test endpoint is working!")


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=8085)

    # Use the following to enable binding to IPv6 interfaces and disable user reloading
    app.run(host="::", port=8085, debug=True, use_reloader=False)

    # To test the api with curl:
    # curl -X POST http://localhost:8085/test_args -H "Content-Type: application/json" -d '{"prompt":"Hello world with unicode: 你好世界","model":"gpt-4","key":"secret123"}'
    # curl http://localhost:8085/test
