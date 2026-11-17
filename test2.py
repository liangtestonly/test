for test
#hoa_processor.py
import pypdf
import re
import os
import glob

def extract_ending_balance(file_path):
    try:
        reader = pypdf.PdfReader(file_path)
        first_page_text = reader.pages[0].extract_text()
        
        pattern = re.compile(r"Ending\s+balance\s+on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s+\$?([-?]?\d{1,3}(?:,\d{3})*\.\d{2})")
        match = pattern.search(first_page_text)
        if match:
            date_str = match.group(1).strip()
            balance_str = match.group(2).strip()
            balance_val = float(balance_str.replace(",", ""))
            return date_str, balance_val
    except Exception:
        pass
    return None, None

def parse_statement_pdf(file_path):
    reader = pypdf.PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
        
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    transactions = []
    current_section = None
    
    check_pattern = re.compile(r"(\d{2}/\d{2}/\d{2})\s+(\d+)\s+([-?]?\d{1,3}(?:,\d{3})*\.\d{2})")
    
    i = 0
    while i < len(lines):
        line = lines[i]
        if "deposits and other credits" in line.lower():
            current_section = "deposits"
            i += 1
            continue
        elif "withdrawals and other debits" in line.lower():
            current_section = "withdrawals"
            i += 1
            continue
        elif "checks" in line.lower() and i+1 < len(lines) and "check #" in lines[i+1].lower():
            current_section = "checks"
            i += 2
            continue
        elif "service fees" in line.lower():
            current_section = "fees"
            i += 1
            continue
        elif line.lower().startswith("total deposits") or line.lower().startswith("total withdrawals") or line.lower().startswith("total checks") or line.lower().startswith("total service"):
            current_section = None
            i += 1
            continue
            
        if current_section is not None:
            if current_section == "checks":
                matches = check_pattern.findall(line)
                if matches:
                    for date, check_num, amount_str in matches:
                        amount = float(amount_str.replace(",", ""))
                        if amount > 0:
                            amount = -amount
                        transactions.append({
                            "date": date,
                            "description": f"Check #{check_num}",
                            "amount": amount,
                            "type": "checks"
                        })
            else:
                match = re.match(r"^(\d{2}/\d{2}/\d{2})\s+(.*)$", line)
                if match:
                    date = match.group(1)
                    rest = match.group(2)
                    amount = None
                    description = rest
                    amount_match = re.search(r"\s+([-?]?\d{1,3}(?:,\d{3})*\.\d{2})$", rest)
                    if amount_match:
                        amount_str = amount_match.group(1)
                        amount = float(amount_str.replace(",", ""))
                        description = rest[:amount_match.start()].strip()
                    else:
                        j = i + 1
                        desc_lines = []
                        while j < len(lines):
                            next_line = lines[j]
                            if re.match(r"^\d{2}/\d{2}/\d{2}\s+", next_line):
                                break
                            if next_line.lower().startswith("total "):
                                break
                            num_match = re.match(r"^([-?]?\d{1,3}(?:,\d{3})*\.\d{2})$", next_line)
                            if num_match:
                                amount = float(num_match.group(1).replace(",", ""))
                                i = j
                                break
                            else:
                                desc_lines.append(next_line)
                            j += 1
                        description = (description + " " + " ".join(desc_lines)).strip()
                    if amount is not None:
                        if current_section in ["withdrawals", "fees"]:
                            if amount > 0:
                                amount = -amount
                        transactions.append({
                            "date": date,
                            "description": description,
                            "amount": amount,
                            "type": current_section
                        })
        i += 1
    return transactions

def categorize_transaction(description, tx_type, amount):
    desc_lower = description.lower()
    
    # 1. Income (Deposits)
    if tx_type == "deposits":
        if "refund" in desc_lower:
            return "HOA Dues Refunds / Credits"
        elif "return" in desc_lower and "check" in desc_lower:
            return "Returned Check Adjustment"
        else:
            return "HOA Dues & Assessments"
            
    # 2. Expenses (Withdrawals, Fees, Checks)
    if "edison" in desc_lower:
        return "Utilities - Electricity (SoCal Edison)"
    elif "waste" in desc_lower or "588 management" in desc_lower:
        return "Utilities - Trash (Waste Management)"
    elif "city of arcadia" in desc_lower or "city of arcadi" in desc_lower:
        return "Utilities - Water & Sewer (City of Arcadia)"
    elif "mercury" in desc_lower:
        return "Insurance (Mercury Insurance)"
    elif "home depot" in desc_lower:
        if amount > 0:
            return "Refunds (Home Depot)"
        return "Maintenance & Repairs (Home Depot)"
    elif "rc worst" in desc_lower:
        return "Maintenance & Repairs (RC Worst)"
    elif "chase" in desc_lower:
        return "General & Administrative (Chase Card)"
    elif "sams" in desc_lower or "sam's" in desc_lower:
        return "General & Administrative (Sam's Club)"
    elif "amazon" in desc_lower:
        return "Office Supplies & General Expenses (Amazon)"
    elif "monthly fee" in desc_lower or "service fee" in desc_lower:
        return "Bank Service Fees (Monthly Maintenance)"
    elif "overdraft" in desc_lower or "wire transfer" in desc_lower or "fee" in desc_lower:
        return "Bank Service Fees (Other Charges)"
    elif "check #" in desc_lower:
        return "Maintenance & Repairs (Contractor Check)"
    else:
        if amount > 0:
            return "Other Income"
        return "Other Operating Expenses"

def generate_report_markdown(year, txs, balance_date=None, balance_val=None):
    total_income = sum(t["amount"] for t in txs if t["amount"] > 0)
    total_expenses = sum(abs(t["amount"]) for t in txs if t["amount"] < 0)
    net_surplus = total_income - total_expenses
    
    # Group income and expenses by category
    income_categories = {}
    expense_categories = {}
    
    for t in txs:
        cat = categorize_transaction(t["description"], t["type"], t["amount"])
        amt = t["amount"]
        if amt > 0:
            income_categories[cat] = income_categories.get(cat, 0.0) + amt
        else:
            expense_categories[cat] = expense_categories.get(cat, 0.0) + abs(amt)
            
    # Sort categories
    sorted_income_cats = sorted(income_categories.items(), key=lambda x: x[1], reverse=True)
    sorted_expense_cats = sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)
    
    # Format ending balance with colors
    ending_balance_line = ""
    if balance_date is not None and balance_val is not None:
        color_code = "#27ae60" if balance_val >= 0 else "#c0392b"
        balance_sign = f"${balance_val:,.2f}" if balance_val >= 0 else f"-${abs(balance_val):,.2f}"
        ending_balance_line = f"- **Ending balance on {balance_date}:** <span style='color: {color_code}; font-weight: bold;'>{balance_sign}</span>\n"
        
    md = f"""# PINE GARDEN HOMEOWNERS ASSOCIATION
## Annual Financial & Operating Report — Year {year}
*Prepared for the Owners of Pine Garden HOA*

---

### I. EXECUTIVE SUMMARY
- **Total Income (Dues & Assessments):** ${total_income:,.2f}
- **Total Operating Expenses:** ${total_expenses:,.2f}
- **Net Operating Surplus / (Deficit):** ${net_surplus:,.2f}
{ending_balance_line}
---

### II. CATEGORIZED INCOME BREAKDOWN
| Category | Total Amount | % of Total |
| :--- | :--- | :--- |
"""
    for cat, amt in sorted_income_cats:
        pct = (amt / total_income * 100.0) if total_income > 0 else 0.0
        md += f"| {cat} | ${amt:,.2f} | {pct:.1f}% |\n"
    md += f"| **TOTAL INCOME** | **${total_income:,.2f}** | **100.0%** |\n\n"
    
    md += """---

### III. CATEGORIZED EXPENSE BREAKDOWN
| Category | Total Amount | % of Total |
| :--- | :--- | :--- |
"""
    for cat, amt in sorted_expense_cats:
        pct = (amt / total_expenses * 100.0) if total_expenses > 0 else 0.0
        md += f"| {cat} | ${amt:,.2f} | {pct:.1f}% |\n"
    md += f"| **TOTAL EXPENSES** | **${total_expenses:,.2f}** | **100.0%** |\n\n"
    
    md += """---

### IV. DETAILED ANNUAL TRANSACTION LEDGER
| Date | Description | Type | Category | Amount |
| :--- | :--- | :--- | :--- | :--- |
"""
    # Sort transactions chronologically
    def parse_date_key(t):
        try:
            m, d, y = map(int, t["date"].split("/"))
            # assuming 2000+
            return (y + 2000, m, d)
        except Exception:
            return (0, 0, 0)
            
    sorted_txs = sorted(txs, key=parse_date_key)
    for t in sorted_txs:
        cat = categorize_transaction(t["description"], t["type"], t["amount"])
        amt_str = f"${t['amount']:,.2f}" if t["amount"] > 0 else f"-${abs(t['amount']):,.2f}"
        md += f"| {t['date']} | {t['description']} | {t['type'].capitalize()} | {cat} | {amt_str} |\n"
        
    return md

from fpdf import FPDF

class HOAPDF(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 14)
        self.set_text_color(44, 62, 80) # slate blue
        self.cell(0, 8, "PINE GARDEN HOMEOWNERS ASSOCIATION", border=False, ln=True, align="C")
        self.set_font("helvetica", "I", 9)
        self.set_text_color(127, 140, 141) # grey
        self.cell(0, 5, f"Annual Financial & Operating Report", border=False, ln=True, align="C")
        self.ln(3)
        self.set_line_width(0.5)
        self.set_draw_color(44, 62, 80)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(127, 140, 141)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Pine Garden HOA Owners Confidential Report", align="C")

def generate_report_pdf(year, txs, pdf_path, balance_date=None, balance_val=None):
    total_income = sum(t["amount"] for t in txs if t["amount"] > 0)
    total_expenses = sum(abs(t["amount"]) for t in txs if t["amount"] < 0)
    net_surplus = total_income - total_expenses
    
    income_categories = {}
    expense_categories = {}
    for t in txs:
        cat = categorize_transaction(t["description"], t["type"], t["amount"])
        amt = t["amount"]
        if amt > 0:
            income_categories[cat] = income_categories.get(cat, 0.0) + amt
        else:
            expense_categories[cat] = expense_categories.get(cat, 0.0) + abs(amt)
            
    sorted_income_cats = sorted(income_categories.items(), key=lambda x: x[1], reverse=True)
    sorted_expense_cats = sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)

    pdf = HOAPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Year Subheader
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(52, 73, 94)
    pdf.cell(0, 8, f"REPORT YEAR: {year}", ln=True, align="L")
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(127, 140, 141)
    pdf.cell(0, 5, "Official balance sheet compile and operating ledger.", ln=True, align="L")
    pdf.ln(5)
    
    # Section I: Executive Summary
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 7, "I. EXECUTIVE SUMMARY", ln=True, align="L")
    pdf.ln(2)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    pdf.cell(85, 6, "Total Income (Dues & Assessments):", border=False)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(40, 6, f"${total_income:,.2f}", ln=True)
    
    pdf.set_font("helvetica", "", 10)
    pdf.cell(85, 6, "Total Operating Expenses:", border=False)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(40, 6, f"${total_expenses:,.2f}", ln=True)
    
    pdf.set_font("helvetica", "", 10)
    pdf.cell(85, 6, "Net Operating Surplus / (Deficit):", border=False)
    pdf.set_font("helvetica", "B", 10)
    if net_surplus >= 0:
        pdf.set_text_color(39, 174, 96) # green
        pdf.cell(40, 6, f"${net_surplus:,.2f}", ln=True)
    else:
        pdf.set_text_color(192, 57, 43) # red
        pdf.cell(40, 6, f"(${abs(net_surplus):,.2f})", ln=True)
        
    if balance_date is not None and balance_val is not None:
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(85, 6, f"Ending balance on {balance_date}:", border=False)
        pdf.set_font("helvetica", "B", 10)
        if balance_val >= 0:
            pdf.set_text_color(39, 174, 96) # green
            pdf.cell(40, 6, f"${balance_val:,.2f}", ln=True)
        else:
            pdf.set_text_color(192, 57, 43) # red
            pdf.cell(40, 6, f"(${abs(balance_val):,.2f})", ln=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)
    
    # Section II: Categorized Income Breakdown
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 7, "II. CATEGORIZED INCOME BREAKDOWN", ln=True, align="L")
    pdf.ln(2)
    
    # Table Header
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(235, 240, 241) # light grey
    pdf.cell(110, 6, "Category", border=1, fill=True)
    pdf.cell(40, 6, "Total Amount", border=1, fill=True, align="R")
    pdf.cell(40, 6, "% of Total", border=1, fill=True, align="R")
    pdf.ln()
    
    # Table Content
    pdf.set_font("helvetica", "", 9)
    for cat, amt in sorted_income_cats:
        pct = (amt / total_income * 100.0) if total_income > 0 else 0.0
        pdf.cell(110, 6, cat, border=1)
        pdf.cell(40, 6, f"${amt:,.2f}", border=1, align="R")
        pdf.cell(40, 6, f"{pct:.1f}%", border=1, align="R")
        pdf.ln()
    # Table Total
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(110, 6, "TOTAL INCOME", border=1)
    pdf.cell(40, 6, f"${total_income:,.2f}", border=1, align="R")
    pdf.cell(40, 6, "100.0%", border=1, align="R")
    pdf.ln(10)
    
    # Section III: Categorized Expense Breakdown
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 7, "III. CATEGORIZED EXPENSE BREAKDOWN", ln=True, align="L")
    pdf.ln(2)
    
    # Table Header
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(110, 6, "Category", border=1, fill=True)
    pdf.cell(40, 6, "Total Amount", border=1, fill=True, align="R")
    pdf.cell(40, 6, "% of Total", border=1, fill=True, align="R")
    pdf.ln()
    
    # Table Content
    pdf.set_font("helvetica", "", 9)
    for cat, amt in sorted_expense_cats:
        pct = (amt / total_expenses * 100.0) if total_expenses > 0 else 0.0
        pdf.cell(110, 6, cat, border=1)
        pdf.cell(40, 6, f"${amt:,.2f}", border=1, align="R")
        pdf.cell(40, 6, f"{pct:.1f}%", border=1, align="R")
        pdf.ln()
    # Table Total
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(110, 6, "TOTAL EXPENSES", border=1)
    pdf.cell(40, 6, f"${total_expenses:,.2f}", border=1, align="R")
    pdf.cell(40, 6, "100.0%", border=1, align="R")
    
    # Section IV: Detailed Ledger
    pdf.add_page()
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 7, "IV. DETAILED ANNUAL TRANSACTION LEDGER", ln=True, align="L")
    pdf.ln(2)
    
    # Table Header
    pdf.set_font("helvetica", "B", 8)
    pdf.cell(18, 5, "Date", border=1, fill=True)
    pdf.cell(85, 5, "Description", border=1, fill=True)
    pdf.cell(20, 5, "Type", border=1, fill=True)
    pdf.cell(47, 5, "Category", border=1, fill=True)
    pdf.cell(20, 5, "Amount", border=1, fill=True, align="R")
    pdf.ln()
    
    # Table Content
    pdf.set_font("helvetica", "", 8)
    
    # Sort chronologically
    def parse_date_key_t(t):
        try:
            m, d, y = map(int, t["date"].split("/"))
            return (y + 2000, m, d)
        except Exception:
            return (0, 0, 0)
            
    sorted_txs = sorted(txs, key=parse_date_key_t)
    for t in sorted_txs:
        cat = categorize_transaction(t["description"], t["type"], t["amount"])
        amt_str = f"${t['amount']:,.2f}" if t["amount"] > 0 else f"-${abs(t['amount']):,.2f}"
        
        desc_str = t["description"][:52]
        if len(t["description"]) > 52:
            desc_str += "..."
            
        cat_str = cat[:28]
        if len(cat) > 28:
            cat_str += "..."
            
        pdf.cell(18, 5, t["date"], border=1)
        pdf.cell(85, 5, desc_str, border=1)
        pdf.cell(20, 5, t["type"].capitalize(), border=1)
        pdf.cell(47, 5, cat_str, border=1)
        pdf.cell(20, 5, amt_str, border=1, align="R")
        pdf.ln()
        
    pdf.output(pdf_path)

def generate_text_pdf(title, text_content, pdf_path):
    pdf = HOAPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Title Subheading
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(52, 73, 94)
    pdf.cell(0, 8, title, ln=True, align="L")
    pdf.ln(3)
    
    # Text content body using clean Monospace Courier font
    pdf.set_font("courier", "", 9)
    pdf.set_text_color(0, 0, 0)
    for line in text_content.split("\n"):
        # Safe text encoding for courier font
        safe_line = line.encode("latin-1", "replace").decode("latin-1")
        # Truncate lines that exceed printable horizontal boundaries (max ~85 chars)
        if len(safe_line) > 85:
            safe_line = safe_line[:82] + "..."
        pdf.cell(0, 5, safe_line, ln=True)
        
    pdf.output(pdf_path)



