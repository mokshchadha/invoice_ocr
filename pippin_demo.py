import os
import streamlit as st
from PIL import Image
import google.generativeai as genai
from openai import OpenAI
import base64
import fitz 
import tempfile
import io
from dotenv import load_dotenv
load_dotenv()

prompts = {
    'pippin_tax_assesment': """You are an expert in processing documents associated with property and real-estate from the uploded document I want you to extract
                tax assesment and tax bill and present them in a json format like 
                {
                    "tax_assesment":"",
                    "tax_bill":""
                }

         if something is missing or blurry return empty string and a warning message for that particular field being unclear or missing
    """,
    
    'generic': """Please analyze this document and extract all relevant information including:
    - Document type and purpose
    - Key dates
    - Important numbers and figures
    - Significant parties involved
    - Financial details if present
    - Any special terms or conditions
    - Notable observations or irregularities"""
}

def get_api_key(key_name):
    """
    Try to get API key from Streamlit secrets first, then fall back to environment variables
    """
    try:
        return st.secrets[key_name]
    except Exception:
        env_value = os.getenv(key_name)
        if env_value:
            return env_value
        raise ValueError(f"Could not find {key_name} in Streamlit secrets or environment variables")

def configure_ai_services():
    """Configure and return instances of AI services"""
    try:
        google_api_key = get_api_key("GOOGLE_API_KEY")
        openai_api_key = get_api_key("OPENAI_API_KEY")
        
        genai.configure(api_key=google_api_key)
        gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        openai_client = OpenAI(api_key=openai_api_key)
        
        return gemini_model, openai_client
    except Exception as e:
        raise Exception(f"Failed to configure AI services: {str(e)}")

def encode_image_to_base64(image):
    """Convert PIL Image to base64 string"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def convert_pdf_pages_to_images(pdf_document):
    """Convert all pages of a PDF to images"""
    images = []
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
        img_data = pix.tobytes("png")
        images.append(Image.open(io.BytesIO(img_data)))
    return images

def extract_text_from_pdf(pdf_document):
    """Extract text from all pages of a PDF"""
    text = ""
    for page in pdf_document:
        text += page.get_text()
    return text

def process_uploaded_file(uploaded_file):
    """Process uploaded file and return relevant data"""
    if uploaded_file.type == "application/pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        pdf_document = fitz.open(tmp_path)
        os.unlink(tmp_path)   

        text = extract_text_from_pdf(pdf_document)
        images = convert_pdf_pages_to_images(pdf_document)
        page_count = len(pdf_document)
        
        return {
            'type': 'pdf',
            'images': images,
            'first_image': images[0],  # Keep first image for AI processing
            'text': text,
            'document': pdf_document,
            'page_count': page_count
        }
    else:
        image = Image.open(uploaded_file)
        return {
            'type': 'image',
            'images': [image],
            'first_image': image,
            'text': None,
            'document': None,
            'page_count': 1
        }

def get_gemini_response(model, input_prompt, file_data, user_prompt, document_type):
    """Get response from Gemini model"""
    meta_prompt = prompts['pippin_tax_assesment'] if document_type == "Pippin Tax Assesment" else prompts['generic']
    
    content_parts = [
        f"{input_prompt}\n{meta_prompt}"
    ]
    
    if file_data['type'] == 'pdf':
        content_parts.append(f"PDF Text Content:\n{file_data['text']}\n")
    
    content_parts.append(file_data['first_image'])
    content_parts.append(user_prompt)
    
    response = model.generate_content(content_parts)
    return response.text

def get_openai_response(client, file_data, user_prompt, document_type):
    """Get response from OpenAI model"""
    base64_image = encode_image_to_base64(file_data['first_image'])
    
    meta_prompt = prompts['pippin_tax_assesment'] if document_type == "Pippin Tax Assesment" else prompts['generic']
    
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
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=500
    )
    return response.choices[0].message.content

def main():
    """Main application function"""
    st.set_page_config(page_title="Document Analysis System")
    
    with st.sidebar:
        st.title("Document Type")
        document_type = st.radio(
            "Select Document Type",
            ( "Pippin Tax Assesment", "Generic Document",),
            help="Choose the type of document you're analyzing"
        )
    
    st.header("Document Analysis with AI")

    try:
        gemini_model, openai_client = configure_ai_services()
    except Exception as e:
        st.error(f"Error initializing AI services: {str(e)}\n\n"
                 "Please ensure either:\n"
                 "1. API keys are set in Streamlit secrets, or\n"
                 "2. Environment variables GOOGLE_API_KEY and OPENAI_API_KEY are set")
        return

    ai_service = st.radio(
        "Select AI Service",
        ("Gemini Pro", "OpenAI GPT-4V"),
        help="Choose which AI service to use for document analysis"
    )

    input_prompt = """
    You are an expert in analyzing documents, including invoices and other business documents. 
    Please analyze the provided document and answer questions based on its contents.
    """
   
    uploaded_file = st.file_uploader(
        "Upload a document...", 
        type=["pdf", "jpg", "jpeg", "png"],
        help="Supported formats: PDF, JPG, JPEG, PNG"
    )

    if uploaded_file is not None:
        try:
            file_data = process_uploaded_file(uploaded_file)
            
            st.write(f"File Type: {file_data['type'].upper()}")
            if file_data['type'] == 'pdf':
                st.write(f"Number of pages: {file_data['page_count']}")
            
            st.subheader("Document Preview")
            for i, image in enumerate(file_data['images']):
                st.image(image, caption=f"Page {i+1}", use_container_width=True)
                st.markdown("---")  # Add separator between pages
            
            if file_data['type'] == 'pdf':
                with st.expander("View Extracted Text"):
                    st.text(file_data['text'])

            submit = st.button("Analyze Document")

            if submit:
                try:
                    with st.spinner("Analyzing the document..."):
                        if ai_service == "Gemini Pro":
                            response = get_gemini_response(gemini_model, input_prompt, file_data, "", document_type)
                        else:   
                            response = get_openai_response(openai_client, file_data, "", document_type)
                        
                        st.subheader("Analysis Result")
                        st.write(response)
                        
                except Exception as e:
                    st.error(f"Error during analysis: {str(e)}")

        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            return

if __name__ == "__main__":
    main()