import os
import streamlit as st
from PIL import Image
import google.generativeai as genai
import openai
import base64
import fitz 
import tempfile
import io

# Updated prompts dictionary with generic analysis option
prompts = {
    'transporter': """Analyze this transporter invoice and extract key information including:
    - Invoice number
    - Date
    - Transportation charges
    - GST details
    - Vehicle details
    - Route information""",
    
    'supplier': """Analyze this supplier bill and extract key information including:
    - Bill number
    - Date
    - Item details
    - Quantities
    - Unit prices
    - Total amount
    - Tax details""",
    
    'generic': """Please analyze this document and extract all relevant information including:
    - Document type and purpose
    - Key dates
    - Important numbers and figures
    - Significant parties involved
    - Financial details if present
    - Any special terms or conditions
    - Notable observations or irregularities""",
    
    'custom': """Analyze this document according to the following instructions: in JSON format\n{} """
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
    try:
        google_api_key = get_api_key("GOOGLE_API_KEY")
        openai_api_key = get_api_key("OPENAI_API_KEY")
        
        genai.configure(api_key=google_api_key)
        openai.api_key = openai_api_key
        
        # Initialize different models
        models = {
            'Gemini 1.5 Pro': ('google', genai.GenerativeModel('gemini-1.5-pro')),
            'Gemini 2.0 Flash': ('google', genai.GenerativeModel('gemini-2.0-flash')),
            'Gemini 2.0 Flash Lite': ('google', genai.GenerativeModel('gemini-2.0-flash-lite')),
            'GPT-4o': ('openai', 'gpt-4o'),
            'GPT-4o mini': ('openai', 'gpt-4o')
        }
        
        return models
    except Exception as e:
        raise Exception(f"Failed to configure AI services: {str(e)}")

def encode_image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def convert_pdf_page_to_image(page):
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  
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

def get_model_response(model_info, input_prompt, file_data, user_prompt, document_type, custom_prompt=""):
    provider, model = model_info
    
    if document_type == "Document with Prompt":
        meta_prompt = prompts['custom'].format(custom_prompt)
    else:
        meta_prompt = prompts.get(document_type.lower().replace(" ", ""), prompts['generic'])
    
    full_prompt = f"{input_prompt}\n{meta_prompt}"
    
    if provider == 'google':
        content_parts = [full_prompt]
        
        if file_data['type'] == 'pdf':
            content_parts.append(f"PDF Text Content:\n{file_data['text']}\n")
        
        content_parts.append(file_data['image'])
        content_parts.append(user_prompt)
        
        response = model.generate_content(content_parts)
        return response.text
    
    else:  # OpenAI
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": full_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encode_image_to_base64(file_data['image'])}"
                        }
                    }
                ]
            }
        ]
        
        if file_data['type'] == 'pdf':
            messages[0]["content"].insert(1, {
                "type": "text",
                "text": f"PDF Text Content:\n{file_data['text']}\n"
            })
        
        response = openai.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096
        )
        
        return response.choices[0].message.content

def main():
    st.set_page_config(page_title="Document Analysis System")
    
    with st.sidebar:
        st.title("Document Type")
        document_type = st.radio(
            "Select Document Type",
            ("Generic Document", "Supplier Bill", "Transporter Invoice", "Document with Prompt"),
            help="Choose the type of document you're analyzing"
        )
        
        custom_prompt = ""
        if document_type == "Document with Prompt":
            custom_prompt = st.text_area(
                "Enter your custom analysis prompt",
                help="Specify what information you want to extract or analyze from the document",
                height=150
            )
    
    st.header("Document Analysis with AI")

    try:
        models = configure_ai_services()
    except Exception as e:
        st.error(f"Error initializing AI services: {str(e)}\n\n"
                 "Please ensure either:\n"
                 "1. API keys are set in Streamlit secrets, or\n"
                 "2. Environment variables GOOGLE_API_KEY and OPENAI_API_KEY are set")
        return

    ai_service = st.radio(
        "Select AI Service",
        list(models.keys()),
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
            
            st.image(file_data['image'], caption="Document Preview", use_container_width=True)
            
            if file_data['type'] == 'pdf':
                with st.expander("View Extracted Text"):
                    st.text(file_data['text'])

            submit = st.button("Analyze Document")

            if submit:
                if document_type == "Document with Prompt" and not custom_prompt.strip():
                    st.warning("Please enter a custom prompt before analyzing the document.")
                    return
                
                try:
                    with st.spinner("Analyzing the document..."):
                        response = get_model_response(
                            models[ai_service],
                            input_prompt,
                            file_data,
                            "",
                            document_type,
                            custom_prompt
                        )
                        
                        st.subheader("Analysis Result")
                        st.write(response)
                        
                except Exception as e:
                    st.error(f"Error during analysis: {str(e)}")

        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            return

if __name__ == "__main__":
    main()