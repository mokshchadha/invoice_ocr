from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai
from openai import OpenAI
import base64
import fitz   
from PIL import Image
import io
import tempfile

 
load_dotenv()

 
app = Flask(__name__)


genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
gemini_model = genai.GenerativeModel('gemini-1.5-flash')
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def encode_image_to_base64(image):
    """Convert PIL Image to base64 string"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def convert_pdf_page_to_image(page):
    """Convert PDF page to PIL Image"""
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
    img_data = pix.tobytes("png")
    return Image.open(io.BytesIO(img_data))

def extract_text_from_pdf(pdf_document):
    """Extract text from PDF document"""
    text = ""
    for page in pdf_document:
        text += page.get_text()
    return text

def process_uploaded_file(file):
    """Process uploaded file (PDF or image)"""
    if file.content_type == "application/pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file.read())
            tmp_path = tmp_file.name

        pdf_document = fitz.open(tmp_path)
        os.unlink(tmp_path)

        text = extract_text_from_pdf(pdf_document)
        image = convert_pdf_page_to_image(pdf_document[0])   
        
        return {
            'type': 'pdf',
            'image': image,
            'text': text
        }
    else:
        image = Image.open(io.BytesIO(file.read()))
        return {
            'type': 'image',
            'image': image,
            'text': None
        }

@app.route('/api/analyze/gemini', methods=['POST'])
def analyze_with_gemini():
    """Analyze invoice using Google's Gemini"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

 
        file_data = process_uploaded_file(file)

 
        input_prompt = """
        You are an expert in analyzing invoices. Please extract and summarize the key information 
        from this invoice including total amount, date, vendor details, line items, and any other 
        relevant information. Present the information in a clear, structured format.
        """

     
        content_parts = [input_prompt]
        if file_data['type'] == 'pdf':
            content_parts.append(f"PDF Text Content:\n{file_data['text']}\n")
        content_parts.append(file_data['image'])

 
        response = gemini_model.generate_content(content_parts)

        return jsonify({
            'analysis': response.text
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze/openai', methods=['POST'])
def analyze_with_openai():
    """Analyze invoice using OpenAI's GPT-4 Vision"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

 
        file_data = process_uploaded_file(file)

 
        base64_image = encode_image_to_base64(file_data['image'])

 
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please analyze this invoice and extract key information including total amount, date, vendor details, line items, and any other relevant information. Present the information in a clear, structured format."
                    }
                ]
            }
        ]

 
        if file_data['type'] == 'pdf':
            messages[0]["content"].append({
                "type": "text",
                "text": f"Document text content:\n{file_data['text']}"
            })

 
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64_image}"
            }
        })

 
        response = openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=500
        )

        return jsonify({
            'analysis': response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)