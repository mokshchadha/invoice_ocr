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
from prompts import prompts

def configure_ai_services():
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    gemini_model = genai.GenerativeModel('gemini-1.5-pro')
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    return gemini_model, openai_client

def encode_image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def convert_pdf_page_to_image(page):
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # 300 DPI rendering
    img_data = pix.tobytes("png")
    return Image.open(io.BytesIO(img_data))

def extract_text_from_pdf(pdf_document):
    text = ""
    for page in pdf_document:
        text += page.get_text()
    return text

def process_uploaded_file(uploaded_file):
    if uploaded_file.type == "application/pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        pdf_document = fitz.open(tmp_path)
        os.unlink(tmp_path)   

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
        image = Image.open(uploaded_file)
        return {
            'type': 'image',
            'image': image,
            'text': None,
            'document': None,
            'page_count': 1
        }

def get_gemini_response(model, input_prompt, file_data, user_prompt, document_type):
    # Add meta prompt based on document type
    meta_prompt = ""
    if document_type == "Transporter Invoice":
        meta_prompt = "fetch all the fields associated with transporter"
    else:   
        meta_prompt = "fetch all the fields associated with supplier"
    
    content_parts = [
        f"{input_prompt}\n{meta_prompt}"
    ]
    
    if file_data['type'] == 'pdf':
        content_parts.append(f"PDF Text Content:\n{file_data['text']}\n")
    
    content_parts.append(file_data['image'])
    content_parts.append(user_prompt)
    
    response = model.generate_content(content_parts)
    return response.text

def get_openai_response(client, file_data, user_prompt, document_type):
    base64_image = encode_image_to_base64(file_data['image'])
    
    # Add meta prompt based on document type
    meta_prompt = ""
    if document_type == "Transporter Invoice":
        meta_prompt = prompts['transporter']
    else: 
        meta_prompt = prompts['supplier']
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": f"Please analyze this document with the following context: {meta_prompt}\nQuestion: {user_prompt}"
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

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=500
    )
    return response.choices[0].message.content

def main():
    st.set_page_config(page_title="Document Analysis System")
    
    with st.sidebar:
        st.title("Document Type")
        document_type = st.radio(
            "Select Document Type",
            ("Transporter Invoice", "Supplier Bill"),
            help="Choose the type of document you're analyzing"
        )
    
    st.header("Document Analysis with AI")

    try:
        gemini_model, openai_client = configure_ai_services()
    except Exception as e:
        st.error(f"Error initializing AI services: {str(e)}")
        return

    ai_service = st.radio(
        "Select AI Service",
        ("Gemini Pro", "OpenAI GPT-4o"),
        help="Choose which AI service to use for document analysis"
    )

    input_prompt = """
    You are an expert in analyzing documents, including invoices and other business documents. 
    Please analyze the provided document and answer questions based on its contents.
    """

    # user_prompt = st.text_input("Ask a question about the document:", key="input") 
    user_prompt = ''
   
    uploaded_file = st.file_uploader(
        "Upload a document...", 
        type=["pdf", "jpg", "jpeg", "png"],
        help="Supported formats: PDF, JPG, JPEG, PNG"
    )

    if uploaded_file is not None: 
         submit = st.button("Analyze Document")

    if uploaded_file is not None:
        try:
            file_data = process_uploaded_file(uploaded_file)
            
            st.write(f"File Type: {file_data['type'].upper()}")
            if file_data['type'] == 'pdf':
                st.write(f"Number of pages: {file_data['page_count']}")
            
            st.image(file_data['image'], caption="Document Preview", use_container_width=True)
            
            if file_data['type'] == 'pdf':
                with st.expander("View Extracted Text"):
                    st.text(file_data['text'])

        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            return


        if submit:
            try:
                with st.spinner("Analyzing the document..."):
                    if ai_service == "Google Gemini":
                        response = get_gemini_response(gemini_model, input_prompt, file_data, user_prompt, document_type)
                    else:   
                        response = get_openai_response(openai_client, file_data, user_prompt, document_type)
                    
                    st.subheader("Analysis Result")
                    st.write(response)
                    
            except Exception as e:
                st.error(f"Error during analysis: {str(e)}")

if __name__ == "__main__":
    main()