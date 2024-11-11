import os
import json
from pathlib import Path
import sqlite3
import google.generativeai as genai
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image
import io
import tempfile


load_dotenv()


genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def init_database():
    """Initialize SQLite database and create table if it doesn't exist"""
    conn = sqlite3.connect('invoices.db')
    cursor = conn.cursor()
    

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL UNIQUE,
            analysis_json TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn

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

def analyze_invoice(pdf_path):
    """Analyze invoice using Gemini AI"""
    try:
        pdf_document = fitz.open(pdf_path)
        

        text = extract_text_from_pdf(pdf_document)
        image = convert_pdf_page_to_image(pdf_document[0])
        
        input_prompt = """
        You are an expert in analyzing invoices. Please extract and structure the following information:
        1. Invoice Number
        2. Date
        3. Vendor Details (Name, Address, Contact)
        4. Bill To Information
        5. Line Items (Product/Service, Quantity, Price)
        6. Subtotal
        7. Taxes
        8. Total Amount
        9. Payment Terms
        10. Additional Notes or Terms

        Return the information in a JSON format.
        """
        
        response = gemini_model.generate_content([
            input_prompt,
            f"PDF Text Content:\n{text}\n",
            image
        ])
        
        try:
            json_data = json.loads(response.text)
        except json.JSONDecodeError:
            json_data = {"raw_analysis": response.text}
        
        return json.dumps(json_data)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

def process_invoices(invoices_dir):
    """Process all PDF invoices in the specified directory"""
    conn = init_database()
    cursor = conn.cursor()
    invoice_files = list(Path(invoices_dir).glob('*.pdf'))
    total_files = len(invoice_files)
    
    print(f"Found {total_files} PDF files to process")
    
    for i, pdf_path in enumerate(invoice_files, 1):
        file_name = pdf_path.name
        
        cursor.execute('SELECT file_name FROM invoice_data WHERE file_name = ?', (file_name,))
        if cursor.fetchone() is not None:
            print(f"[{i}/{total_files}] Skipping {file_name} (already processed)")
            continue
        
        print(f"[{i}/{total_files}] Processing {file_name}...")
        
        try:
            analysis_json = analyze_invoice(pdf_path)
            
            cursor.execute(
                'INSERT INTO invoice_data (file_name, analysis_json) VALUES (?, ?)',
                (file_name, analysis_json)
            )
            conn.commit()
            
            print(f"✓ Successfully processed {file_name}")
            
        except Exception as e:
            print(f"✗ Error processing {file_name}: {str(e)}")
            continue
    
    conn.close()
    print("\nMigration completed!")

if __name__ == "__main__":
    INVOICES_DIR = "invoices"
    
    if not os.path.exists(INVOICES_DIR):
        print(f"Error: Directory '{INVOICES_DIR}' not found!")
        exit(1)
    
    process_invoices(INVOICES_DIR)