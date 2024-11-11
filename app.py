from dotenv import load_dotenv
load_dotenv()

import os
import streamlit as st
from PIL import Image
import google.generativeai as genai
from openai import OpenAI
import base64
import fitz  # PyMuPDF for PDF processing
import tempfile
import io

# Configure AI Services
def configure_ai_services():
    # Configure Google Gemini
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Configure OpenAI
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    return gemini_model, openai_client

# Function to encode image to base64 for OpenAI
def encode_image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# Function to convert PDF page to image
def convert_pdf_page_to_image(page):
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # 300 DPI rendering
    img_data = pix.tobytes("png")
    return Image.open(io.BytesIO(img_data))

# Function to extract text from PDF
def extract_text_from_pdf(pdf_document):
    text = ""
    for page in pdf_document:
        text += page.get_text()
    return text

# Function to process uploaded file
def process_uploaded_file(uploaded_file):
    if uploaded_file.type == "application/pdf":
        # Save PDF to temporary file (PyMuPDF needs a file path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        pdf_document = fitz.open(tmp_path)
        os.unlink(tmp_path)  # Delete temporary file

        # Extract text and convert first page to image
        text = extract_text_from_pdf(pdf_document)
        image = convert_pdf_page_to_image(pdf_document[0])
        page_count = len(pdf_document)
        
        return {
            'type': 'pdf',
            'image': image,
            'text': text,
            'document': pdf_document,
            'page_count': page_count
        }
    else:
        # Handle regular image files
        image = Image.open(uploaded_file)
        return {
            'type': 'image',
            'image': image,
            'text': None,
            'document': None,
            'page_count': 1
        }

# Function to get Gemini response
def get_gemini_response(model, input_prompt, file_data, user_prompt):
    content_parts = [input_prompt]
    
    if file_data['type'] == 'pdf':
        content_parts.append(f"PDF Text Content:\n{file_data['text']}\n")
    
    content_parts.append(file_data['image'])
    content_parts.append(user_prompt)
    
    response = model.generate_content(content_parts)
    return response.text

# Function to get OpenAI response
def get_openai_response(client, file_data, user_prompt):
    base64_image = encode_image_to_base64(file_data['image'])
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Please analyze this document and answer the following question: {user_prompt}"}
            ]
        }
    ]
    
    # Add PDF text content if available
    if file_data['type'] == 'pdf':
        messages[0]["content"].append({
            "type": "text",
            "text": f"Document text content:\n{file_data['text']}"
        })
    
    # Add image
    messages[0]["content"].append({
        "type": "image_url",
        "image_url": {
            "url": f"data:image/png;base64,{base64_image}"
        }
    })

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=500
    )
    return response.choices[0].message.content

# Streamlit app
def main():
    st.set_page_config(page_title="Document Analysis System")
    st.header("Document Analysis with AI")
    
    # Initialize AI models
    try:
        gemini_model, openai_client = configure_ai_services()
    except Exception as e:
        st.error(f"Error initializing AI services: {str(e)}")
        return

    # AI Service Selection
    ai_service = st.radio(
        "Select AI Service",
        ("Google Gemini", "OpenAI GPT-4V"),
        help="Choose which AI service to use for document analysis"
    )

    input_prompt = """
    You are an expert in analyzing documents, including invoices and other business documents. 
    Please analyze the provided document and answer questions based on its contents.
    """

    user_prompt = st.text_input("Ask a question about the document:", key="input")
    uploaded_file = st.file_uploader(
        "Upload a document...", 
        type=["pdf", "jpg", "jpeg", "png"],
        help="Supported formats: PDF, JPG, JPEG, PNG"
    )

    if uploaded_file is not None:
        try:
            file_data = process_uploaded_file(uploaded_file)
            
            # Display file information
            st.write(f"File Type: {file_data['type'].upper()}")
            if file_data['type'] == 'pdf':
                st.write(f"Number of pages: {file_data['page_count']}")
            
            # Display the image (first page for PDFs)
            st.image(file_data['image'], caption="Document Preview", use_column_width=True)
            
            # For PDFs, add a text expander to show extracted text
            if file_data['type'] == 'pdf':
                with st.expander("View Extracted Text"):
                    st.text(file_data['text'])

        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            return

        submit = st.button("Analyze Document")

        if submit:
            try:
                with st.spinner("Analyzing the document..."):
                    if ai_service == "Google Gemini":
                        response = get_gemini_response(gemini_model, input_prompt, file_data, user_prompt)
                    else:  # OpenAI GPT-4V
                        response = get_openai_response(openai_client, file_data, user_prompt)
                    
                    st.subheader("Analysis Result")
                    st.write(response)
                    
            except Exception as e:
                st.error(f"Error during analysis: {str(e)}")

if __name__ == "__main__":
    main()