"""Patch document_status.py to add pipeline status labels."""

pipeline_labels = '''
# Pipeline-stage status labels (written to pipeline_status field, separate from main status)
PIPELINE_STATUS_LABELS = {
    "QUEUED": "Queued - waiting for the pipeline to start.",
    "EXTRACTING": "Extracting transactions from the document file.",
    "NORMALIZING": "Normalizing entity descriptions and payment channels.",
    "CLASSIFYING": "Classifying transactions into financial categories and tax heads.",
    "SAVING_TRANSACTIONS": "Saving validated transactions to the database.",
    "DETECTING_DUPLICATES": "Running duplicate detection across saved transactions.",
    "DETECTING_ANOMALIES": "Running statistical IQR anomaly detection.",
    "ML_ANOMALY_DETECTION": "Running ML Isolation Forest anomaly detection.",
    "TAX_VALIDATION": "Validating tax rules (Section 269ST, 40A(3), 80C, TDS).",
    "RECONCILING": "Reconciling bank vs. ledger transactions.",
    "TDS_ANALYSIS": "Running advanced TDS discrepancy analysis.",
    "GENERATING_FINDINGS": "Generating unified findings portfolio.",
    "SCORING_RISK": "Calculating transaction and run-level risk scores.",
    "PIPELINE_COMPLETE": "All pipeline stages completed successfully.",
    "PIPELINE_FAILED": "Pipeline encountered a fatal error.",
    "N/A": "No pipeline processing for this file type.",
}
'''

with open("app/services/document_status.py", "r", newline="", encoding="utf-8") as f:
    content = f.read()

marker = "ALLOWED_TRANSITIONS = {"
idx = content.find(marker)
# Find end of the ALLOWED_TRANSITIONS dict
end_idx = content.find("}", idx) + 1
# Skip the closing brace of the inner sets and find the outer closing brace
depth = 0
scan_idx = idx
for i, ch in enumerate(content[idx:], start=idx):
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            end_idx = i + 1
            break

insert_at = end_idx

new_content = content[:insert_at] + "\r\n" + pipeline_labels.replace("\n", "\r\n") + content[insert_at:]

with open("app/services/document_status.py", "w", newline="", encoding="utf-8") as f:
    f.write(new_content)
print("Done")

