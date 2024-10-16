import os
import pandas as pd
from flask import Flask, request, render_template
from tabula import read_pdf
from tabulate import tabulate
import PyPDF2

# Initialize Flask app
app = Flask(__name__)

# Set the upload folder path
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'Backend', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to extract lines from a PDF
def extract_lines_from_pdf(pdf_path):
    lines = []
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                lines.extend([line.strip() for line in text.split('\n') if line.strip()])
    return lines

# Function to compare two PDFs line by line and return mismatches
def compare_pdf_lines(pdf1_path, pdf2_path):
    lines1 = extract_lines_from_pdf(pdf1_path)
    lines2 = extract_lines_from_pdf(pdf2_path)

    max_lines = max(len(lines1), len(lines2))
    lines1 += [''] * (max_lines - len(lines1))
    lines2 += [''] * (max_lines - len(lines2))

    mismatches = []
    for i in range(max_lines):
        if lines1[i].strip() != lines2[i].strip():
            mismatches.append([i + 1, lines1[i], lines2[i]])
    
    return mismatches

# Function to clean column names and ensure valid headers
def clean_and_correct_column_names(df):
    # Try to take the first row as the header if not already set
    df.columns = [str(col).strip() for col in df.columns]
    if not df.columns.any() or isinstance(df.columns[0], int):
        # If the columns are still numerical, treat the first row as headers
        df.columns = df.iloc[0]
        df = df.drop(0).reset_index(drop=True)

    return df

# Improved function to detect and extract the table from Excel or PDF converted to Excel
def identify_table(df, min_non_empty_cells=3):
    non_empty_rows = df.dropna(thresh=min_non_empty_cells).reset_index(drop=True)

    if non_empty_rows.empty:
        print("No valid rows found.")
        return pd.DataFrame(columns=df.columns)

    # Clean the column names to ensure valid headers are identified
    non_empty_rows = clean_and_correct_column_names(non_empty_rows)

    return non_empty_rows

# Function to load and identify tables in Excel or PDFs converted to Excel
def load_and_identify_table(file_path, min_non_empty_cells=3):
    if file_path.lower().endswith(".pdf"):
        pdf_tables = read_pdf(file_path, pages="all", multiple_tables=True)

        if not pdf_tables or len(pdf_tables) == 0:
            print(f"No tables found in PDF: {file_path}")
            return pd.DataFrame()

        # Identify the largest table for comparison purposes
        largest_table = max(pdf_tables, key=lambda t: len(t)) if pdf_tables else pdf_tables[0]
        df = pd.DataFrame(largest_table)
    else:
        df = pd.read_excel(file_path)

    return identify_table(df, min_non_empty_cells)

# Function to compare two Excel tables and return mismatches
def compare_excel_tables(table1, table2):
    # Ensure both tables have the same columns before comparison
    common_columns = list(set(table1.columns).intersection(set(table2.columns)))

    if not common_columns:
        print("No common columns found for comparison.")
        return []

    mismatches = []
    max_rows = max(len(table1), len(table2))  # Max number of rows between both tables

    for i in range(max_rows):
        for col in common_columns:
            try:
                value1 = str(table1[col].iloc[i]).strip().replace("\n", " ").replace("\r", "")
            except IndexError:
                value1 = ""  # If index is out of bounds, treat value1 as empty

            try:
                value2 = str(table2[col].iloc[i]).strip().replace("\n", " ").replace("\r", "")
            except IndexError:
                value2 = ""  # If index is out of bounds, treat value2 as empty

            # If values are different, add to mismatches
            if value1 != value2:
                mismatches.append([i + 1, col, value1, value2])  # Include the correct column name in the mismatch

    return mismatches

# Route for file uploads and comparison
@app.route("/", methods=["GET", "POST"])
def upload_files():
    if request.method == "POST":
        file1 = request.files.get("file1")
        file2 = request.files.get("file2")

        if file1 and file2:
            file1_path = os.path.join(app.config['UPLOAD_FOLDER'], file1.filename)
            file2_path = os.path.join(app.config['UPLOAD_FOLDER'], file2.filename)
            file1.save(file1_path)
            file2.save(file2_path)

            if file1.filename.lower().endswith(".pdf") and file2.filename.lower().endswith(".pdf"):
                mismatches = compare_pdf_lines(file1_path, file2_path)
                if mismatches:
                    headers = ["Line No.", "File 1 Content", "File 2 Content"]
                    result = tabulate(mismatches, headers, tablefmt="html")
                    return render_template("result.html", result=result)
                else:
                    return render_template("result.html", result="No mismatches found. Both PDF files match perfectly!")

            # Excel or PDF-to-Excel comparison
            else:
                table1 = load_and_identify_table(file1_path)
                table2 = load_and_identify_table(file2_path)

                if table1.empty or table2.empty:
                    print("No valid data found in one or both files.")
                    return render_template("result.html", result="No valid data found in one or both files.")

                mismatches = compare_excel_tables(table1, table2)
                if mismatches:
                    headers = ["Row", "Column Name", "File1", "File2"]
                    result = tabulate(mismatches, headers, tablefmt="html")
                    return render_template("result.html", result=result)
                else:
                    return render_template("result.html", result="No mismatches found. Both tables match perfectly!")
    
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
