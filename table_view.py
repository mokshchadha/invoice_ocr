import streamlit as st
import sqlite3
import json
import pandas as pd
from pathlib import Path
import fitz  # PyMuPDF
import tempfile
import base64
from PIL import Image
import io
import os

def load_invoice_data():
    """Load invoice data from SQLite database"""
    conn = sqlite3.connect('invoices.db')
    
    # Get all records
    query = '''
        SELECT 
            id,
            file_name,
            analysis_json,
            processed_at
        FROM invoice_data
        ORDER BY processed_at DESC
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df

def format_json_view(json_str):
    """Format JSON string for pretty display"""
    try:
        data = json.loads(json_str)
        return json.dumps(data, indent=2)
    except:
        return json_str

def get_pdf_preview(file_path, max_pages=3):
    """Generate preview images for PDF pages"""
    try:
        pdf_document = fitz.open(file_path)
        images = []
        
        for page_num in range(min(len(pdf_document), max_pages)):
            page = pdf_document[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            img_data = pix.tobytes("png")
            images.append(Image.open(io.BytesIO(img_data)))
        
        return images
    except Exception as e:
        st.error(f"Error generating PDF preview: {str(e)}")
        return None

def create_key_value_table(json_data):
    """Create a formatted table from JSON data"""
    try:
        data = json.loads(json_data)
        
        # Skip if data is just raw analysis
        if isinstance(data, dict) and 'raw_analysis' in data:
            return None
            
        # Create table rows
        rows = []
        for key, value in data.items():
            # Format key
            formatted_key = key.replace('_', ' ').title()
            
            # Handle different value types
            if isinstance(value, dict):
                formatted_value = '\n'.join([f"{k}: {v}" for k, v in value.items()])
            elif isinstance(value, list):
                formatted_value = '\n'.join([str(item) for item in value])
            else:
                formatted_value = str(value)
                
            rows.append([formatted_key, formatted_value])
            
        return rows
    except:
        return None

def main():
    st.set_page_config(
        page_title="Invoice Analysis Viewer",
        page_icon="📄",
        layout="wide"
    )
    
    # Add custom CSS for layout improvements
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #f0f2f6;
            border-radius: 4px;
            padding: 10px 16px;
            font-size: 14px;
        }
        .invoice-preview {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("📄 Invoice Analysis System")
    
    # Check if database exists
    if not Path('invoices.db').exists():
        st.error("Database file 'invoices.db' not found! Please run the migration script first.")
        return
    
    # Load data
    try:
        df = load_invoice_data()
        
        if len(df) == 0:
            st.warning("No invoice data found in the database.")
            return
        
        # Display summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Invoices", len(df))
        with col2:
            st.metric("Last Updated", df['processed_at'].max())
        with col3:
            st.metric("Unique Vendors", len(set([
                json.loads(analysis).get('vendor_details', {}).get('name', 'Unknown')
                for analysis in df['analysis_json']
                if 'vendor_details' in json.loads(analysis)
            ])))
        
        # Add search/filter section
        st.markdown("### 🔍 Search Invoices")
        search_col1, search_col2 = st.columns([2, 1])
        with search_col1:
            search_term = st.text_input("Search by filename", "")
        with search_col2:
            sort_option = st.selectbox(
                "Sort by",
                ["Most Recent", "Filename", "Invoice Amount"],
                index=0
            )
        
        # Apply search filter
        if search_term:
            df = df[df['file_name'].str.contains(search_term, case=False)]
        
        # Apply sorting
        if sort_option == "Most Recent":
            df = df.sort_values('processed_at', ascending=False)
        elif sort_option == "Filename":
            df = df.sort_values('file_name')
        elif sort_option == "Invoice Amount":
            # Extract amount from JSON and sort
            df['amount'] = df['analysis_json'].apply(lambda x: 
                float(json.loads(x).get('total_amount', '0').replace('$', '').replace(',', ''))
                if isinstance(json.loads(x).get('total_amount', '0'), str)
                else 0
            )
            df = df.sort_values('amount', ascending=False)
        
        # Main content section
        st.markdown("### 📋 Invoice Details")
        
        # Create two columns for layout
        list_col, content_col = st.columns([1, 3])
        
        with list_col:
            # Display filenames in a selectbox
            selected_file = st.selectbox(
                "Select Invoice",
                df['file_name'].tolist(),
                index=0
            )
        
        # Get selected invoice data
        selected_data = df[df['file_name'] == selected_file].iloc[0]
        
        # Content area with tabs
        with content_col:
            tab1, tab2 = st.tabs(["📄 Analysis", "👁️ Preview"])
            
            with tab1:
                # Try to create structured table view
                table_data = create_key_value_table(selected_data['analysis_json'])
                
                if table_data:
                    # Display structured table
                    st.table(pd.DataFrame(table_data, columns=['Field', 'Value']))
                else:
                    # Fallback to JSON view
                    st.code(format_json_view(selected_data['analysis_json']), language='json')
            
            with tab2:
                # Get PDF path
                pdf_path = os.path.join('invoices', selected_file)
                
                if os.path.exists(pdf_path):
                    images = get_pdf_preview(pdf_path)
                    if images:
                        st.markdown("#### Invoice Preview")
                        for i, image in enumerate(images, 1):
                            st.image(image, caption=f"Page {i}", use_column_width=True)
                else:
                    st.error("Invoice file not found in the invoices directory")
        
        # Export functionality
        st.markdown("### 📤 Export Options")
        export_col1, export_col2 = st.columns(2)
        
        with export_col1:
            if st.button("Export Analysis as JSON"):
                json_data = format_json_view(selected_data['analysis_json'])
                b64 = base64.b64encode(json_data.encode()).decode()
                href = f'<a href="data:application/json;base64,{b64}" download="{selected_file}_analysis.json">Download JSON</a>'
                st.markdown(href, unsafe_allow_html=True)
        
        with export_col2:
            if st.button("Export as CSV"):
                analysis_dict = json.loads(selected_data['analysis_json'])
                if isinstance(analysis_dict, dict):
                    df_export = pd.DataFrame([analysis_dict])
                    csv = df_export.to_csv(index=False)
                    b64 = base64.b64encode(csv.encode()).decode()
                    href = f'<a href="data:text/csv;base64,{b64}" download="{selected_file}_analysis.csv">Download CSV</a>'
                    st.markdown(href, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")

if __name__ == "__main__":
    main()