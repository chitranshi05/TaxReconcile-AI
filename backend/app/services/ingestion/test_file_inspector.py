from app.services.ingestion.file_inspector import inspect_file


file_path = "uploads/company_relational_database.xlsx"

result = inspect_file(file_path)

for sheet in result:
    print("\n==============================")
    print(f"Sheet: {sheet['sheet_name']}")
    print(f"Rows: {sheet['rows']}")
    print(f"Columns: {sheet['columns']}")
    print("Sample:")
    
    for row in sheet["sample"]:
        print(row)