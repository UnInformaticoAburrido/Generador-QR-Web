"""API sin almacenamiento: el texto se convierte en un único QR en memoria."""

import base64
from io import BytesIO

from flask import Flask, jsonify, request
import segno
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

app = Flask(__name__)
# Incluso 7089 dígitos enviados como escapes JSON caben en este límite HTTP.
app.config["MAX_CONTENT_LENGTH"] = 128 * 1024


@app.after_request
def prevent_caching(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify(error="La petición supera 128 KiB. Reduce el texto: un único QR admite como máximo 7089 dígitos."), 413


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.post("/api/qr")
def generate_qr():
    if not request.is_json:
        return jsonify(error="Envía un objeto JSON con el campo text."), 415
    try:
        data = request.get_json()
    except BadRequest:
        return jsonify(error="El JSON no es válido."), 400
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        return jsonify(error="El campo text debe ser una cadena de texto."), 400

    text = data["text"]
    if text == "":
        return jsonify(error="Introduce el texto que quieres convertir en QR."), 400
    # No se recortan espacios, saltos de línea ni ceros iniciales.
    try:
        byte_count = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        return jsonify(error="El texto contiene caracteres Unicode no válidos."), 400

    try:
        qr = segno.make_qr(
            text,
            error="L",
            boost_error=False,
            encoding="iso-8859-1" if text.isascii() else "utf-8",
            eci=True,
        )
    except segno.DataOverflowError:
        return jsonify(error="El texto no cabe en un único QR. Reduce su longitud. El máximo depende de los caracteres: 7089 dígitos, 4296 caracteres alfanuméricos QR o 2953 bytes ASCII; Unicode ocupa más espacio."), 422

    def image_data(kind):
        buffer = BytesIO()
        qr.save(buffer, kind=kind, scale=8, border=4, dark="#000000", light="#ffffff")
        mime = "image/svg+xml" if kind == "svg" else "image/png"
        return f"data:{mime};base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"

    return jsonify(
        png=image_data("png"),
        svg=image_data("svg"),
        version=qr.version,
        mode=qr.mode,
        error_correction=qr.error,
        characters=len(text),
        bytes=byte_count,
        modules=len(qr.matrix),
    )
