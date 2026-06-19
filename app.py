import os, io, base64, json
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import fitz  # PyMuPDF
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import docx
import pandas as pd

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Serve service worker at root scope (required by PWA spec)
@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

def pdf_to_images(pdf_path):
    doc = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(doc):
        mat = fitz.Matrix(1.5, 1.5)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        images.append({"page": i + 1, "data": b64})
    return images, doc.page_count

def docx_to_pdf(input_path, output_path):
    doc = docx.Document(input_path)
    c = canvas.Canvas(output_path, pagesize=A4)
    w, h = A4
    y = h - 50
    for para in doc.paragraphs:
        text = para.text
        if not text.strip():
            y -= 12; continue
        if para.style.name.startswith("Heading"):
            c.setFont("Helvetica-Bold", 14)
        else:
            c.setFont("Helvetica", 11)
        lines = [text[i:i+90] for i in range(0, len(text), 90)]
        for line in lines:
            if y < 50:
                c.showPage(); y = h - 50
            c.drawString(50, y, line)
            y -= 16
    c.save()

def csv_to_pdf(input_path, output_path):
    df = pd.read_csv(input_path)
    c = canvas.Canvas(output_path, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, h - 40, f"CSV: {os.path.basename(input_path)}")
    c.setFont("Helvetica", 9)
    y = h - 70
    headers = list(df.columns)
    col_w = min((w - 100) / max(len(headers), 1), 120)
    for ci, col in enumerate(headers):
        c.drawString(50 + ci * col_w, y, str(col)[:14])
    y -= 16
    for _, row in df.iterrows():
        if y < 50:
            c.showPage(); y = h - 50
        for ci, val in enumerate(row):
            c.drawString(50 + ci * col_w, y, str(val)[:14])
        y -= 14
    c.save()

def txt_to_pdf(input_path, output_path):
    with open(input_path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    c = canvas.Canvas(output_path, pagesize=A4)
    w, h = A4
    c.setFont("Courier", 10)
    y = h - 40
    for line in lines:
        line = line.rstrip()
        chunks = [line[i:i+95] for i in range(0, max(len(line), 1), 95)]
        for chunk in chunks:
            if y < 40:
                c.showPage(); y = h - 40
            c.drawString(40, y, chunk)
            y -= 13
    c.save()

def image_to_pdf(input_path, output_path):
    img = Image.open(input_path).convert("RGB")
    img.save(output_path, "PDF", resolution=100.0)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/view_pdf", methods=["POST"])
def view_pdf():
    file = request.files["file"]
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    images, total = pdf_to_images(path)
    return jsonify({"images": images, "total_pages": total, "filename": file.filename})

@app.route("/convert_to_pdf", methods=["POST"])
def convert_to_pdf():
    file = request.files["file"]
    ext = os.path.splitext(file.filename)[1].lower()
    in_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(in_path)
    out_name = os.path.splitext(file.filename)[0] + "_converted.pdf"
    out_path = os.path.join(OUTPUT_FOLDER, out_name)
    try:
        if ext == ".docx": docx_to_pdf(in_path, out_path)
        elif ext == ".csv": csv_to_pdf(in_path, out_path)
        elif ext in [".txt", ".md", ".log"]: txt_to_pdf(in_path, out_path)
        elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]: image_to_pdf(in_path, out_path)
        else: return jsonify({"error": f"Unsupported format: {ext}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"output": out_name})

@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT_FOLDER, filename)
    return send_file(path, as_attachment=True)

@app.route("/edit_pdf", methods=["POST"])
def edit_pdf():
    data = request.json
    filename = data["filename"]
    annotations = data.get("annotations", [])
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    doc = fitz.open(pdf_path)
    for ann in annotations:
        page = doc[ann["page"] - 1]
        if ann["type"] == "text":
            page.insert_text((ann["x"], ann["y"]), ann["text"],
                             fontsize=ann.get("size", 12), color=(1, 0, 0))
        elif ann["type"] == "highlight":
            rect = fitz.Rect(ann["x1"], ann["y1"], ann["x2"], ann["y2"])
            page.add_highlight_annot(rect)
        elif ann["type"] == "rect":
            rect = fitz.Rect(ann["x1"], ann["y1"], ann["x2"], ann["y2"])
            page.draw_rect(rect, color=(1, 0, 0), width=2)
    out_name = os.path.splitext(filename)[0] + "_edited.pdf"
    out_path = os.path.join(OUTPUT_FOLDER, out_name)
    doc.save(out_path)
    return jsonify({"output": out_name})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
