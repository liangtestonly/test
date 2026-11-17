test only
#hoa_app.py
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import re
import glob
import sys

# Import our custom statement processor
sys.path.append(os.path.dirname(__file__))
import hoa_processor

class HOAStatementApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pine Garden HOA — Statement Processing System")
        self.root.geometry("820x680")
        self.root.configure(bg="#1a1c23")
            # Automatically load custom icon if 'app_icon.ico' or 'app_icon.png' is dropped in this folder!
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(script_dir, "app_icon.ico")
        png_path = os.path.join(script_dir, "app_icon.png")
        
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass
        elif os.path.exists(png_path):
            try:
                from PIL import ImageTk
                img_ico = ImageTk.PhotoImage(file=png_path)
                self.root.wm_iconphoto(True, img_ico)
            except Exception:
                pass    
        # Corporate Header
        header_frm = tk.Frame(self.root, bg="#2c3e50", pady=15)
        header_frm.pack(fill="x")
        
        tk.Label(
            header_frm, 
            text="PINE GARDEN HOMEOWNERS ASSOCIATION", 
            font=("Segoe UI", 14, "bold"), 
            fg="#ffffff", 
            bg="#2c3e50"
        ).pack(anchor="center")
        
        # tk.Label(
        #     header_frm, 
        #     text="", 
        #     font=("Segoe UI", 9, "italic"), 
        #     fg="#bdc3c7", 
        #     bg="#2c3e50"
        # ).pack(anchor="center", pady=(2, 0))
        
        # Control Panel Frame
        # Control Panel Frame (Contains both select-year and select-file rows)
        control_frm = tk.LabelFrame(
            self.root, 
            text=" Operating Parameters ", 
            fg="#3498db", 
            bg="#1a1c23", 
            font=("Segoe UI", 10, "bold"), 
            bd=1, 
            relief="solid",
            padx=15,
            pady=12
        )
        control_frm.pack(fill="x", padx=20, pady=(15, 10))
        
        # Row 1: Select Year Row
        row1 = tk.Frame(control_frm, bg="#1a1c23")
        row1.pack(fill="x", pady=(0, 10))
        
        tk.Label(
            row1, 
            text="Select Year (YYYY):", 
            font=("Segoe UI", 10, "bold"), 
            fg="#ffffff", 
            bg="#1a1c23"
        ).pack(side="left", padx=(10, 8))
        
        self.year_var = tk.StringVar(value="2023")
        self.year_entry = tk.Entry(
            row1, 
            textvariable=self.year_var, 
            width=8, 
            bg="#0d1117", 
            fg="#ffffff", 
            insertbackground="#ffffff", 
            justify="center", 
            font=("Segoe UI", 10, "bold"),
            bd=1,
            relief="solid"
        )
        self.year_entry.pack(side="left", padx=(0, 20))
        
        # Process Year Button
        self.proc_year_btn = tk.Button(
            row1, 
            text="Proc Year", 
            command=self.process_year, 
            bg="#3498db", 
            activebackground="#2980b9", 
            fg="white", 
            activeforeground="white", 
            bd=0, 
            width=12, 
            pady=6, 
            font=("Segoe UI", 9, "bold")
        )
        self.proc_year_btn.pack(side="left", padx=(0, 12))
        
        # Process All Button
        self.proc_all_btn = tk.Button(
            row1, 
            text="Proc All", 
            command=self.process_all, 
            bg="#9b59b6", 
            activebackground="#8e44ad", 
            fg="white", 
            activeforeground="white", 
            bd=0, 
            width=12, 
            pady=6, 
            font=("Segoe UI", 9, "bold")
        )
        self.proc_all_btn.pack(side="left")
        
        # Folder Path Display Label
        stmt_dir = os.path.join(os.path.dirname(__file__), "statement")
        tk.Label(
            row1, 
            text=f"Target: eStmts folder", 
            font=("Segoe UI", 8, "italic"), 
            fg="#95a5a6", 
            bg="#1a1c23"
        ).pack(side="right", padx=10)
        
        # Row 2: File selection & Document Summary Row
        row2 = tk.Frame(control_frm, bg="#1a1c23")
        row2.pack(fill="x", pady=(0, 10))
        
        # Add Folder Mode Checkbox
        self.folder_mode_var = tk.BooleanVar(value=False)
        self.folder_chk = tk.Checkbutton(
            row2, 
            text="Folder", 
            variable=self.folder_mode_var, 
            command=self.on_folder_mode_changed, 
            bg="#1a1c23", 
            fg="#ffffff", 
            selectcolor="#1a1c23",
            activebackground="#1a1c23",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold")
        )
        self.folder_chk.pack(side="left", padx=(10, 8))
        
        # Add Header Mode Checkbox (Saves with/without metadata and banner lines)
        self.header_mode_var = tk.BooleanVar(value=True)
        self.header_chk = tk.Checkbutton(
            row2, 
            text="Header", 
            variable=self.header_mode_var, 
            bg="#1a1c23", 
            fg="#ffffff", 
            selectcolor="#1a1c23",
            activebackground="#1a1c23",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold")
        )
        self.header_chk.pack(side="left", padx=(0, 10))
        
        self.input_lbl = tk.Label(
            row2, 
            text="Input File:", 
            font=("Segoe UI", 10, "bold"), 
            fg="#ffffff", 
            bg="#1a1c23"
        )
        self.input_lbl.pack(side="left", padx=(0, 8))
        
        self.file_path_var = tk.StringVar()
        self.file_entry = tk.Entry(
            row2, 
            textvariable=self.file_path_var, 
            width=50, 
            bg="#0d1117", 
            fg="#ffffff", 
            insertbackground="#ffffff", 
            font=("Segoe UI", 9),
            bd=1,
            relief="solid"
        )
        self.file_entry.pack(side="left", padx=(0, 12))
        
        # Select File Button
        self.select_file_btn = tk.Button(
            row2, 
            text="Select", 
            command=self.select_file, 
            bg="#7f8c8d", 
            activebackground="#95a5a6", 
            fg="white", 
            activeforeground="white", 
            bd=0, 
            width=12, 
            pady=5, 
            font=("Segoe UI", 9, "bold")
        )
        self.select_file_btn.pack(side="left", padx=(0, 12))
        
        # Summary Button
        self.summary_btn = tk.Button(
            row2, 
            text="Summary", 
            command=self.generate_document_summary, 
            bg="#2ecc71", 
            activebackground="#27ae60", 
            fg="white", 
            activeforeground="white", 
            bd=0, 
            width=12, 
            pady=5, 
            font=("Segoe UI", 9, "bold")
        )
        self.summary_btn.pack(side="left")
        
        # Extract Txt Button
        self.extract_btn = tk.Button(
            row2, 
            text="Extract Txt", 
            command=self.extract_file_context, 
            bg="#e67e22", 
            activebackground="#d35400", 
            fg="white", 
            activeforeground="white", 
            bd=0, 
            width=12, 
            pady=5, 
            font=("Segoe UI", 9, "bold")
        )
        self.extract_btn.pack(side="left", padx=(12, 0))

        # Row 3: Output File selection & Output Type Row
        row3 = tk.Frame(control_frm, bg="#1a1c23")
        row3.pack(fill="x")
        
        self.output_lbl = tk.Label(
            row3, 
            text="Output File:", 
            font=("Segoe UI", 10, "bold"), 
            fg="#ffffff", 
            bg="#1a1c23"
        )
        self.output_lbl.pack(side="left", padx=(10, 8))
        
        self.output_file_var = tk.StringVar()
        self.output_entry = tk.Entry(
            row3, 
            textvariable=self.output_file_var, 
            width=50, 
            bg="#0d1117", 
            fg="#ffffff", 
            insertbackground="#ffffff", 
            font=("Segoe UI", 9),
            bd=1,
            relief="solid"
        )
        self.output_entry.pack(side="left", padx=(0, 12))
        
        # Select Output File Button
        self.select_output_btn = tk.Button(
            row3, 
            text="Select", 
            command=self.select_output_file, 
            bg="#7f8c8d", 
            activebackground="#95a5a6", 
            fg="white", 
            activeforeground="white", 
            bd=0, 
            width=12, 
            pady=5, 
            font=("Segoe UI", 9, "bold")
        )
        self.select_output_btn.pack(side="left", padx=(0, 12))
        
        # OptionMenu for Output File Type
        self.output_type_var = tk.StringVar(value=".txt")
        self.type_menu = tk.OptionMenu(
            row3, 
            self.output_type_var, 
            ".txt", 
            ".rtf", 
            ".pdf",
            command=self.on_output_type_changed
        )
        self.type_menu.config(
            bg="#34495e", 
            fg="white", 
            activebackground="#2c3e50", 
            activeforeground="white", 
            bd=0, 
            highlightthickness=0,
            padx=10,
            font=("Segoe UI", 8, "bold")
        )
        self.type_menu["menu"].config(
            bg="#1a1c23", 
            fg="white", 
            activebackground="#3498db"
        )
        self.type_menu.pack(side="left")
        
        # Report Viewer Section
        viewer_frm = tk.LabelFrame(
            self.root, 
            text=" Report Document Viewer ", 
            fg="#2ecc71", 
            bg="#1a1c23", 
            font=("Segoe UI", 10, "bold"), 
            bd=1, 
            relief="solid"
        )
        viewer_frm.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(viewer_frm)
        scrollbar.pack(side="right", fill="y")
        
        self.text_box = tk.Text(
            viewer_frm, 
            wrap="word", 
            yscrollcommand=scrollbar.set, 
            bg="#0d1117", 
            fg="#c9d1d9", 
            insertbackground="#ffffff", 
            font=("Consolas", 10),
            padx=12,
            pady=12,
            bd=0
        )
        self.text_box.pack(fill="both", expand=True, side="left")
        scrollbar.config(command=self.text_box.yview)
        
        # Initial Welcome Info
        self.display_message("Welcome to the Pine Garden HOA.\n\n"
                             "• Enter a target year and click 'Proc Year' to compile and view that year's report.\n"
                             "• Click 'Proc All' to build separate yearly reports for all available statements,\n"
                             "  along with a consolidated Multi-Year Master Summary & Board Ledger.")
        
        # Status Bar
        self.status_var = tk.StringVar(value="System Ready. Standing by...")
        self.status_lbl = tk.Label(
            self.root, 
            textvariable=self.status_var, 
            font=("Segoe UI", 8, "bold"), 
            fg="#2ecc71", 
            bg="#1a1c23", 
            anchor="w", 
            bd=1, 
            relief="sunken", 
            padx=10, 
            pady=4
        )
        self.status_lbl.pack(side="bottom", fill="x")

        # Load previously saved operational settings on startup
        self.load_gui_settings()
        
        # Intercept window close to automatically save all current GUI options!
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

    def display_message(self, msg):
        self.text_box.config(state="normal")
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert("1.0", msg)
        self.text_box.config(state="disabled")

    def process_year(self):
        year = self.year_var.get().strip()
        if not re.match(r"^\d{4}$", year):
            messagebox.showerror("Error", "Please enter a valid 4-digit year (e.g. 2023).", parent=self.root)
            return
            
        try:
            stmt_dir = os.path.join(os.path.dirname(__file__), "statement")
            files = sorted(glob.glob(os.path.join(stmt_dir, f"eStmt_{year}-*.pdf")))
            
            if not files:
                messagebox.showinfo("No Statements", f"No bank statements found for the year {year} in folder 'statement'.", parent=self.root)
                return
                
            self.status_var.set(f"Parsing {len(files)} statements for year {year}...")
            self.root.update_idletasks()
            
            all_txs = []
            for f in files:
                all_txs.extend(hoa_processor.parse_statement_pdf(f))
                
            # Extract ending balance from the last statement of the year
            balance_date, balance_val = hoa_processor.extract_ending_balance(files[-1])
            
            report_md = hoa_processor.generate_report_markdown(year, all_txs, balance_date, balance_val)
            
            # Save Report Documents (Both .md and .pdf!)
            report_path_md = os.path.join(os.path.dirname(__file__), f"HOA_Report_{year}.md")
            with open(report_path_md, "w", encoding="utf-8") as rf:
                rf.write(report_md)
                
            report_path_pdf = os.path.join(os.path.dirname(__file__), f"HOA_Report_{year}.pdf")
            hoa_processor.generate_report_pdf(year, all_txs, report_path_pdf, balance_date, balance_val)
            
            self.display_message(report_md)
            self.status_var.set(f"Success! Compiled and saved: HOA_Report_{year}.md and HOA_Report_{year}.pdf")
            self.status_lbl.config(fg="#2ecc71")
            
        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred during statement processing:\n{str(e)}", parent=self.root)
            self.status_var.set("Error occurred. See popup.")
            self.status_lbl.config(fg="#e74c3c")

    def process_all(self):
        try:
            stmt_dir = os.path.join(os.path.dirname(__file__), "statement")
            files = sorted(glob.glob(os.path.join(stmt_dir, "*.pdf")))
            
            if not files:
                messagebox.showinfo("No Statements", "No bank statements found in folder 'statement'.", parent=self.root)
                return
                
            self.status_var.set(f"Grouping and parsing all {len(files)} statements...")
            self.root.update_idletasks()
            
            # Group statements by year
            grouped_years = {}
            for f in files:
                fn = os.path.basename(f)
                year_match = re.search(r"eStmt_(\d{4})-\d{2}-\d{2}\.pdf", fn)
                if year_match:
                    yr = year_match.group(1)
                    if yr not in grouped_years:
                        grouped_years[yr] = []
                    grouped_years[yr].append(f)
                    
            if not grouped_years:
                messagebox.showinfo("No Data", "No valid yearly statements identified in the folder.", parent=self.root)
                return
                
            # Process each year and build Master Summary
            master_md = "# PINE GARDEN HOMEOWNERS ASSOCIATION\n"
            master_md += "## Master Multi-Year Financial Summary & HOA Board Ledger\n"
            master_md += "*A consolidation of all processed yearly bank statements*\n\n---\n\n"
            master_md += "### I. HISTORICAL OPERATING OVERVIEW\n"
            master_md += "| Year | Number of Transactions | Total Annual Income | Total Annual Expenses | Net Operating Balance |\n"
            master_md += "| :--- | :--- | :--- | :--- | :--- |\n"
            
            # Detailed year summaries list
            year_details = ""
            
            for yr in sorted(grouped_years.keys()):
                all_txs = []
                for f in grouped_years[yr]:
                    all_txs.extend(hoa_processor.parse_statement_pdf(f))
                    
                total_income = sum(t["amount"] for t in all_txs if t["amount"] > 0)
                total_expenses = sum(abs(t["amount"]) for t in all_txs if t["amount"] < 0)
                net_surplus = total_income - total_expenses
                
                # Extract ending balance from the last statement of this year
                balance_date, balance_val = hoa_processor.extract_ending_balance(grouped_years[yr][-1])
                
                # Add row to historical table
                master_md += f"| **{yr}** | {len(all_txs)} txs | ${total_income:,.2f} | -${total_expenses:,.2f} | ${net_surplus:,.2f} |\n"
                
                # Generate and save separate yearly report (Both .md and .pdf!)
                report_md = hoa_processor.generate_report_markdown(yr, all_txs, balance_date, balance_val)
                report_path = os.path.join(os.path.dirname(__file__), f"HOA_Report_{yr}.md")
                with open(report_path, "w", encoding="utf-8") as rf:
                    rf.write(report_md)
                    
                report_path_pdf = os.path.join(os.path.dirname(__file__), f"HOA_Report_{yr}.pdf")
                hoa_processor.generate_report_pdf(yr, all_txs, report_path_pdf, balance_date, balance_val)
                
                balance_status = "N/A"
                if balance_date is not None and balance_val is not None:
                    balance_status = f"${balance_val:,.2f} (on {balance_date})"
                    
                year_details += f"### II. YEAR {yr} OPERATING HIGHLIGHTS\n"
                year_details += f"- **Total Income:** ${total_income:,.2f}\n"
                year_details += f"- **Total Operating Expenses:** -${total_expenses:,.2f}\n"
                year_details += f"- **Net Operating Balance:** ${net_surplus:,.2f}\n"
                year_details += f"- **Ending Balance:** {balance_status}\n"
                year_details += f"- **Status:** Compiled and saved to: `HOA_Report_{yr}.md` and `HOA_Report_{yr}.pdf`\n\n"
                
            master_md += "\n---\n\n" + year_details
            
            # Save Master Summary Document
            master_path = os.path.join(os.path.dirname(__file__), "HOA_Master_Summary.md")
            with open(master_path, "w", encoding="utf-8") as mf:
                mf.write(master_md)
                
            self.display_message(master_md)
            self.status_var.set("Success! Compiled separate yearly reports & HOA_Master_Summary.md successfully.")
            self.status_lbl.config(fg="#2ecc71")
            
        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred during multi-year processing:\n{str(e)}", parent=self.root)
            self.status_var.set("Error occurred. See popup.")
            self.status_lbl.config(fg="#e74c3c")

    def on_folder_mode_changed(self):
        if self.folder_mode_var.get():
            self.input_lbl.config(text="Input Folder:")
            self.output_lbl.config(text="Output Folder:")
            self.status_var.set("Switched to Folder Batch Mode. Select Input & Output directories.")
        else:
            self.input_lbl.config(text="Input File:")
            self.output_lbl.config(text="Output File:")
            self.status_var.set("Switched to Single File Mode.")

    def select_file(self):
        if self.folder_mode_var.get():
            folder_path = filedialog.askdirectory(
                parent=self.root,
                title="Select Input Folder Containing Images"
            )
            if folder_path:
                self.file_path_var.set(os.path.normpath(folder_path))
                self.status_var.set(f"Selected Input Folder: {os.path.basename(folder_path)}")
                self.status_lbl.config(fg="#2ecc71")
        else:
            file_path = filedialog.askopenfilename(
                parent=self.root,
                title="Select Input Document to Summarize",
                filetypes=[
                    ("All Supported Formats", "*.pptx *.docx *.rtf *.txt *.csv *.pdf *.jpg *.jpeg *.png *.gif *.html *.htm"),
                    ("PowerPoint Presentations (*.pptx)", "*.pptx"),
                    ("Word Documents (*.docx)", "*.docx"),
                    ("Rich Text Documents (*.rtf)", "*.rtf"),
                    ("PDF Documents (*.pdf)", "*.pdf"),
                    ("HTML Documents (*.html)", "*.html *.htm"),
                    ("Image Files (*.jpg, *.png)", "*.jpg *.jpeg *.png *.gif"),
                    ("Text Files (*.txt)", "*.txt"),
                    ("CSV Spreadsheet Files (*.csv)", "*.csv"),
                    ("All Files (*.*)", "*.*")
                ]
            )
            if file_path:
                self.file_path_var.set(file_path)
                self.status_var.set(f"Selected: {os.path.basename(file_path)}")
                self.status_lbl.config(fg="#2ecc71")
            self.status_lbl.config(fg="#2ecc71")

    def generate_document_summary(self):
        file_path = self.file_path_var.get().strip()
        if not file_path:
            messagebox.showerror("Error", "Please select or type a valid file path first.", parent=self.root)
            return
        if not os.path.exists(file_path):
            messagebox.showerror("Error", f"The specified file path does not exist:\n{file_path}", parent=self.root)
            return
            
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1].lower()
        
        self.status_var.set(f"Generating comprehensive summary for {file_name}...")
        self.root.update_idletasks()
        
        try:
            file_size_kb = os.path.getsize(file_path) / 1024.0
            summary_text = f"==================================================\n"
            summary_text += f"              DOCUMENT SUMMARY REPORT              \n"
            summary_text += f"==================================================\n"
            summary_text += f"File Name: {file_name}\n"
            summary_text += f"File Type: {ext.upper()[1:]} Document\n"
            summary_text += f"File Size: {file_size_kb:.2f} KB\n"
            summary_text += f"Location:  {file_path}\n"
            summary_text += f"==================================================\n\n"
            
            stats_info = ""
            
            if ext == ".pptx":
                import pptx
                prs = pptx.Presentation(file_path)
                slides_count = len(prs.slides)
                stats_info = f"Total Slides: {slides_count}\n"
                
                headers = []
                slide_details = []
                for idx, slide in enumerate(prs.slides):
                    title = f"Slide {idx+1}"
                    if slide.shapes.title and slide.shapes.title.text.strip():
                        title = slide.shapes.title.text.strip()
                    headers.append(f"- {title}")
                    
                    bullets = []
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            for p in shape.text_frame.paragraphs:
                                txt = p.text.strip()
                                if txt and txt != title and len(bullets) < 3:
                                    bullets.append(f"  • {txt}")
                    if bullets:
                        slide_details.append(f"[{title}]\n" + "\n".join(bullets))
                        
                summary_text += f"### I. STRUCTURE & TABLE OF CONTENTS\n"
                summary_text += "\n".join(headers[:15])
                if len(headers) > 15:
                    summary_text += f"\n- ... and {len(headers) - 15} more slides.\n"
                summary_text += "\n\n### II. REVEALED CONTENT SUMMARY (FIRST FEW SLIDES)\n"
                summary_text += "\n\n".join(slide_details[:5])
                
            elif ext == ".docx":
                import docx
                doc = docx.Document(file_path)
                paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                stats_info = f"Total Paragraphs: {len(paras)}\n"
                total_words = sum(len(p.split()) for p in paras)
                stats_info += f"Total Words: {total_words}\n"
                
                headers = [p for p in paras if len(p) < 80][:10]
                
                summary_text += f"### I. KEY HEADERS & IMPORTANT LINES\n"
                for h in headers:
                    summary_text += f"- {h}\n"
                summary_text += "\n### II. EXECUTIVE SUMMARY / ABSTRACT (FIRST 10 PARAGRAPHS)\n"
                summary_text += "\n\n".join(paras[:10])
                
            elif ext == ".rtf":
                from striprtf.striprtf import rtf_to_text
                with open(file_path, "r", errors="ignore") as f:
                    rtf_content = f.read()
                plain_text = rtf_to_text(rtf_content)
                paras = [p.strip() for p in plain_text.split("\n") if p.strip()]
                stats_info = f"Total Paragraphs: {len(paras)}\n"
                total_words = sum(len(p.split()) for p in paras)
                stats_info += f"Total Words: {total_words}\n"
                
                summary_text += f"### I. DOCUMENT EXCERPTS & SUMMARY (FIRST 15 PARAGRAPHS)\n"
                summary_text += "\n\n".join(paras[:15])
                
            elif ext == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(file_path)
                pages_count = len(reader.pages)
                stats_info = f"Total Pages: {pages_count}\n"
                
                # Extract text from first 5 pages for preview
                extracted_txt = []
                total_words = 0
                for idx, page in enumerate(reader.pages):
                    txt = page.extract_text()
                    if txt:
                        total_words += len(txt.split())
                        if idx < 5:
                            extracted_txt.append(f"[Page {idx+1}]\n{txt[:400].strip()}...")
                stats_info += f"Total Words: {total_words}\n"
                
                summary_text += f"### I. PDF DOCUMENT EXCERPTS & SUMMARY (FIRST 5 PAGES)\n"
                summary_text += "\n\n".join(extracted_txt)
                
            elif ext in [".jpg", ".jpeg", ".png", ".gif"]:
                from PIL import Image
                from PIL.ExifTags import TAGS
                img = Image.open(file_path)
                w, h = img.size
                stats_info = f"Image Resolution: {w} x {h} pixels (Aspect Ratio: {w/h:.2f})\n"
                stats_info += f"Color Mode: {img.mode}\n"
                
                summary_text += f"### I. IMAGE METADATA & SPECS\n"
                summary_text += f"- Resolution: {w} x {h} px\n"
                summary_text += f"- Color Space: {img.mode}\n"
                
                # Extract EXIF metadata if present
                exif_data = {}
                try:
                    info = img.getexif()
                    if info:
                        for tag, value in info.items():
                            decoded = TAGS.get(tag, tag)
                            exif_data[decoded] = value
                except Exception:
                    pass
                    
                if exif_data:
                    summary_text += f"\n### II. EMBEDDED EXIF METADATA\n"
                    # Filter out binary or extremely long values
                    for tag, val in exif_data.items():
                        if isinstance(val, (str, int, float)) and len(str(val)) < 150:
                            summary_text += f"- {tag}: {val}\n"
                else:
                    summary_text += f"\n### II. EMBEDDED EXIF METADATA\n- No EXIF metadata detected in this image."
                
                # Extract and display the first few words of the visual text using high-speed Windows OCR!
                ocr_text = ""
                try:
                    import asyncio
                    import threading
                    import queue
                    from winrt.windows.media.ocr import OcrEngine
                    from winrt.windows.graphics.imaging import BitmapDecoder
                    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
                    from winrt.system import Array, UInt8

                    async def run_windows_ocr(path):
                        # Load and upscale image using high-quality cubic interpolation if it has a low resolution!
                        # This brings tiny/microscopic text into the optimal OCR readability range (DPI boost).
                        import cv2
                        img = cv2.imread(path)
                        if img is None:
                            return ""
                            
                        h, w, _ = img.shape
                        if w < 1200:
                            img = cv2.resize(img, (0, 0), fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
                            
                        # Encode the upscaled image back to PNG in memory
                        success, encoded_img = cv2.imencode(".png", img)
                        if not success:
                            return ""
                        file_bytes = encoded_img.tobytes()
                        
                        stream = InMemoryRandomAccessStream()
                        writer = DataWriter(stream.get_output_stream_at(0))
                        writer.write_bytes(Array(UInt8, file_bytes))
                        await writer.store_async()
                        
                        decoder = await BitmapDecoder.create_async(stream)
                        software_bitmap = await decoder.get_software_bitmap_async()
                        
                        engine = OcrEngine.try_create_from_user_profile_languages()
                        if not engine:
                            return ""
                        result = await engine.recognize_async(software_bitmap)
                        
                        # High-Performance 2D Grid Reconstruction OCR!
                        # Reconstructs the exact horizontal layouts, side-by-side fields, 
                        # and tabular columns of the form.
                        if not result.lines:
                            return ""
                            
                        # 1. First, find global min_x (left margin) and estimate average character width
                        min_x = float('inf')
                        char_widths = []
                        
                        for line in result.lines:
                            for word in line.words:
                                rx = word.bounding_rect.x
                                rw = word.bounding_rect.width
                                min_x = min(min_x, rx)
                                char_len = len(word.text.strip())
                                if char_len > 0:
                                    char_widths.append(rw / char_len)
                                    
                        avg_char_width = sum(char_widths) / len(char_widths) if char_widths else 12.0
                        
                        # 2. Process each line directly as segmented by Windows OCR to prevent vertical collision!
                        formatted_lines = []
                        for line in result.lines:
                            # Sort words in the line by their horizontal X coordinates
                            sorted_words = sorted(line.words, key=lambda w: w.bounding_rect.x)
                            
                            row_str = ""
                            prev_end_x = min_x
                            
                            for word in sorted_words:
                                gap_px = word.bounding_rect.x - prev_end_x
                                num_spaces = max(0, int(round(gap_px / avg_char_width)))
                                row_str += (" " * num_spaces) + word.text.strip()
                                prev_end_x = word.bounding_rect.x + word.bounding_rect.width
                                
                            formatted_lines.append(row_str)
                            
                        return "\n".join(formatted_lines)

                    # Execute inside a clean background thread to avoid Tkinter STA COM apartment deadlocks!
                    q = queue.Queue()
                    def run_in_thread():
                        try:
                            res = asyncio.run(run_windows_ocr(file_path))
                            q.put((True, res))
                        except Exception as err:
                            q.put((False, err))
                    
                    t = threading.Thread(target=run_in_thread, daemon=True)
                    t.start()
                    t.join(timeout=10.0) # Wait up to 10 seconds for completion
                    
                    success, ocr_res = q.get(timeout=1.0)
                    if success:
                        ocr_text = ocr_res
                except Exception:
                    pass
                
                if ocr_text:
                    summary_text += f"\n\n### III. EXTRACTED VISUAL TEXT PREVIEW\n"
                    summary_text += ocr_text[:1200].strip() + ("..." if len(ocr_text) > 1200 else "")
                else:
                    summary_text += f"\n\n### III. EXTRACTED VISUAL TEXT PREVIEW\n- [No visual text detected in this image]"
                    
            elif ext in [".html", ".htm"]:
                from html.parser import HTMLParser
                class MLStripper(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.reset()
                        self.convert_charrefs = True
                        self.text = []
                    def handle_data(self, d):
                        self.text.append(d)
                    def get_data(self):
                        return "".join(self.text)
                        
                try:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            html_content = f.read()
                    except UnicodeDecodeError:
                        with open(file_path, "r", encoding="cp1252") as f:
                            html_content = f.read()
                            
                    # Strip tags to get plain text
                    stripper = MLStripper()
                    stripper.feed(html_content)
                    plain_text = stripper.get_data()
                    
                    lines = [l.strip() for l in plain_text.split("\n") if l.strip()]
                    stats_info = f"Total Lines of Text: {len(lines)}\n"
                    total_words = sum(len(l.split()) for l in lines)
                    stats_info += f"Total Words: {total_words}\n"
                    
                    summary_text += f"### I. HTML PLAIN-TEXT EXCERPTS (FIRST 20 LINES)\n"
                    summary_text += "\n".join(lines[:20])
                    
                except Exception as e:
                    return f"Error parsing HTML file: {str(e)}"
                    
            elif ext in [".txt", ".csv"]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, "r", encoding="cp1252") as f:
                        content = f.read()
                lines = [l.strip() for l in content.split("\n") if l.strip()]
                stats_info = f"Total Lines: {len(lines)}\n"
                total_words = sum(len(l.split()) for l in lines)
                stats_info += f"Total Words: {total_words}\n"
                
                if ext == ".csv":
                    summary_text += f"### I. SPREADSHEET HEADERS & COLUMN LAYOUT\n"
                    summary_text += f"Headers: {lines[0]}\n\n"
                    summary_text += f"### II. SPREADSHEET RECORD HIGHLIGHTS (FIRST 15 ROWS)\n"
                    summary_text += "\n".join(lines[:15])
                else:
                    summary_text += f"### I. TEXT EXCERPTS (FIRST 20 LINES)\n"
                    summary_text += "\n".join(lines[:20])
            else:
                messagebox.showerror("Error", f"Unsupported file format: {ext}\nPlease choose a supported document or image file.", parent=self.root)
                self.status_var.set("Unsupported format selected.")
                return
                
            summary_text = summary_text.replace("==================================================\n\n", f"==================================================\n{stats_info}==================================================\n\n")
            
            # If an output file path is specified, save the summary text!
            out_path = self.output_file_var.get().strip()
            save_msg = ""
            if out_path:
                out_type = self.output_type_var.get()
                # Ensure path extension matches output_type_var
                if not out_path.lower().endswith(out_type):
                    base, _ = os.path.splitext(out_path)
                    out_path = base + out_type
                    self.output_file_var.set(out_path)
                    
                if out_type == ".txt":
                    with open(out_path, "w", encoding="utf-8") as out_f:
                        out_f.write(summary_text)
                elif out_type == ".rtf":
                    # Simple standard RTF envelope with Consolas font
                    rtf_wrapped = "{\\rtf1\\ansi\\deff0 {\\fonttbl{\\f0\\fnil\\fcharset0 Consolas;}}\n\\viewkind4\\uc1\n\\pard\\f0\\fs20 " + summary_text.replace("\n", "\\par\n") + "}"
                    with open(out_path, "w", encoding="ascii", errors="ignore") as out_f:
                        out_f.write(rtf_wrapped)
                elif out_type == ".pdf":
                    # Generate a beautiful monospaced PDF summary using our custom engine
                    hoa_processor.generate_text_pdf(f"Document Summary - {file_name}", summary_text, out_path)
                save_msg = f" & Saved: {os.path.basename(out_path)}"
                
            self.display_message(summary_text)
            self.status_var.set(f"Success! Generated complete summary for {file_name}{save_msg}")
            self.status_lbl.config(fg="#2ecc71")
            
        except Exception as e:
            messagebox.showerror("Summary Error", f"An error occurred while generating document summary:\n{str(e)}", parent=self.root)
            self.status_var.set("Error during summary generation.")
            self.status_lbl.config(fg="#e74c3c")

    def extract_file_context(self):
        input_path = self.file_path_var.get().strip()
        if not input_path:
            messagebox.showerror("Error", "Please select or type a valid input path first.", parent=self.root)
            return
        if not os.path.exists(input_path):
            messagebox.showerror("Error", f"The specified input path does not exist:\n{input_path}", parent=self.root)
            return
            
        out_path = self.output_file_var.get().strip()
        if not out_path:
            messagebox.showerror("Error", "Please select or specify a valid output path first.", parent=self.root)
            return
            
        # --- folder batch processing mode ---
        if self.folder_mode_var.get():
            import threading
            self.status_var.set("Scanning directory recursively...")
            self.root.update_idletasks()
            
            def run_batch():
                try:
                    img_exts = ["*.png", "*.jpg", "*.jpeg", "*.gif"]
                    img_files = []
                    for ext in img_exts:
                        img_files.extend(glob.glob(os.path.join(input_path, "**", ext), recursive=True))
                        
                    if not img_files:
                        self.root.after(0, lambda: messagebox.showwarning("No Images", f"No image files found recursively inside:\n{input_path}", parent=self.root))
                        self.root.after(0, lambda: self.status_var.set("Folder Batch Scan: 0 images found."))
                        return
                        
                    self.root.after(0, lambda: self.status_var.set(f"Found {len(img_files)} images. Starting batch..."))
                    
                    out_type = self.output_type_var.get() # .txt, .rtf, or .pdf
                    import asyncio
                    from winrt.windows.media.ocr import OcrEngine
                    from winrt.windows.graphics.imaging import BitmapDecoder
                    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
                    from winrt.system import Array, UInt8

                    async def run_windows_ocr(path):
                        # Load and upscale image using high-quality cubic interpolation if it has a low resolution!
                        # This brings tiny/microscopic text into the optimal OCR readability range (DPI boost).
                        import cv2
                        img = cv2.imread(path)
                        if img is None:
                            return ""
                            
                        h, w, _ = img.shape
                        if w < 1200:
                            img = cv2.resize(img, (0, 0), fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
                            
                        # Encode the upscaled image back to PNG in memory
                        success, encoded_img = cv2.imencode(".png", img)
                        if not success:
                            return ""
                        file_bytes = encoded_img.tobytes()
                        
                        stream = InMemoryRandomAccessStream()
                        writer = DataWriter(stream.get_output_stream_at(0))
                        writer.write_bytes(Array(UInt8, file_bytes))
                        await writer.store_async()
                        
                        decoder = await BitmapDecoder.create_async(stream)
                        software_bitmap = await decoder.get_software_bitmap_async()
                        
                        engine = OcrEngine.try_create_from_user_profile_languages()
                        if not engine:
                            return ""
                        result = await engine.recognize_async(software_bitmap)
                        
                        # High-Performance 2D Grid Reconstruction OCR!
                        # Reconstructs the exact horizontal layouts, side-by-side fields, 
                        # and tabular columns of the form.
                        if not result.lines:
                            return ""
                            
                        # 1. First, find global min_x (left margin) and estimate average character width
                        min_x = float('inf')
                        char_widths = []
                        
                        for line in result.lines:
                            for word in line.words:
                                rx = word.bounding_rect.x
                                rw = word.bounding_rect.width
                                min_x = min(min_x, rx)
                                char_len = len(word.text.strip())
                                if char_len > 0:
                                    char_widths.append(rw / char_len)
                                    
                        avg_char_width = sum(char_widths) / len(char_widths) if char_widths else 12.0
                        
                        # 2. Process each line directly as segmented by Windows OCR to prevent vertical collision!
                        formatted_lines = []
                        for line in result.lines:
                            # Sort words in the line by their horizontal X coordinates
                            sorted_words = sorted(line.words, key=lambda w: w.bounding_rect.x)
                            
                            row_str = ""
                            prev_end_x = min_x
                            
                            for word in sorted_words:
                                gap_px = word.bounding_rect.x - prev_end_x
                                num_spaces = max(0, int(round(gap_px / avg_char_width)))
                                row_str += (" " * num_spaces) + word.text.strip()
                                prev_end_x = word.bounding_rect.x + word.bounding_rect.width
                                
                            formatted_lines.append(row_str)
                            
                        return "\n".join(formatted_lines)

                    for idx, img_path in enumerate(img_files):
                        progress_text = f"Status: [Batch Progress] Processing image {idx+1} of {len(img_files)}: {os.path.basename(img_path)}..."
                        self.root.after(0, lambda p=progress_text: self.status_var.set(p))
                        
                        # Run OCR natively on background MTA thread
                        ocr_text = ""
                        try:
                            ocr_text = asyncio.run(run_windows_ocr(img_path))
                        except Exception as ocr_err:
                            ocr_text = f"[Local OCR Scan Failed: {ocr_err}]"
                            
                        # Format output text with or without the metadata headers and banners!
                        if self.header_mode_var.get():
                            # Process image specs & metadata
                            from PIL import Image
                            from PIL.ExifTags import TAGS
                            img_obj = Image.open(img_path)
                            w, h = img_obj.size
                            img_text = f"Image Resolution: {w} x {h} pixels (Aspect Ratio: {w/h:.2f})\n"
                            img_text += f"Color Mode: {img_obj.mode}\n"
                            img_text += "EXIF METADATA RECORDS:\n"
                            exif_data = {}
                            try:
                                info = img_obj.getexif()
                                if info:
                                    for tag, value in info.items():
                                        decoded = TAGS.get(tag, tag)
                                        exif_data[decoded] = value
                            except Exception:
                                pass
                            if exif_data:
                                for tag, val in exif_data.items():
                                    img_text += f"- {tag}: {val}\n"
                            else:
                                img_text += "- No EXIF metadata detected.\n"
                                
                            img_text += f"\n==================================================\n"
                            img_text += f"       EXTRACTED VISUAL TEXT (WINDOWS OCR)        \n"
                            img_text += f"==================================================\n"
                            img_text += ocr_text if ocr_text else "[No visual text detected in this image]\n"
                        else:
                            img_text = ocr_text if ocr_text else ""
                        
                        # Calculate relative output path to preserve folder hierarchy!
                        rel_path = os.path.relpath(img_path, input_path)
                        rel_base, _ = os.path.splitext(rel_path)
                        rel_out = rel_base + out_type
                        
                        full_out = os.path.join(out_path, rel_out)
                        os.makedirs(os.path.dirname(full_out), exist_ok=True)
                        
                        if out_type == ".txt":
                            with open(full_out, "w", encoding="utf-8") as out_f:
                                out_f.write(img_text)
                        elif out_type == ".rtf":
                            rtf_wrapped = "{\\rtf1\\ansi\\deff0 {\\fonttbl{\\f0\\fnil\\fcharset0 Consolas;}}\n\\viewkind4\\uc1\n\\pard\\f0\\fs20 " + img_text.replace("\n", "\\par\n") + "}"
                            with open(full_out, "w", encoding="ascii", errors="ignore") as out_f:
                                out_f.write(rtf_wrapped)
                        elif out_type == ".pdf":
                            hoa_processor.generate_text_pdf(f"Text Extraction - {os.path.basename(img_path)}", img_text, full_out)
                            
                    # Preview the last processed file in the text box
                    self.root.after(0, lambda: self.display_message(img_text))
                    self.root.after(0, lambda: messagebox.showinfo("Batch Complete", f"Successfully processed all {len(img_files)} images recursively!\n\nFolder tree hierarchy preserved inside output directory.", parent=self.root))
                    self.root.after(0, lambda: self.status_var.set(f"Success! Finished folder batch. Processed {len(img_files)} images."))
                except Exception as err:
                    self.root.after(0, lambda: messagebox.showerror("Batch Error", f"An error occurred during batch processing:\n{err}", parent=self.root))
                    
            threading.Thread(target=run_batch, daemon=True).start()
            return

        # --- single file processing mode (original) ---
        file_path = input_path
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1].lower()
        
        self.status_var.set(f"Extracting full text context from {file_name}...")
        self.root.update_idletasks()
        
        try:
            full_text = ""
            
            # Extract full text context based on file format
            if ext == ".pptx":
                import pptx
                prs = pptx.Presentation(file_path)
                slide_texts = []
                for idx, slide in enumerate(prs.slides):
                    slide_texts.append(f"=== Slide {idx+1} ===")
                    title = ""
                    if slide.shapes.title and slide.shapes.title.text.strip():
                        title = slide.shapes.title.text.strip()
                        slide_texts.append(title)
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            for p in shape.text_frame.paragraphs:
                                txt = p.text.strip()
                                if txt and txt != title:
                                    slide_texts.append(txt)
                    slide_texts.append("")
                full_text = "\n".join(slide_texts)
                
            elif ext == ".docx":
                import docx
                doc = docx.Document(file_path)
                paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                full_text = "\n\n".join(paras)
                # Parse tables if any
                table_texts = []
                for t_idx, table in enumerate(doc.tables):
                    table_texts.append(f"\n--- Table {t_idx+1} ---")
                    for row in table.rows:
                        row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_cells:
                            table_texts.append(" | ".join(row_cells))
                if table_texts:
                    full_text += "\n" + "\n".join(table_texts)
                    
            elif ext == ".rtf":
                from striprtf.striprtf import rtf_to_text
                with open(file_path, "r", errors="ignore") as f:
                    rtf_content = f.read()
                full_text = rtf_to_text(rtf_content)
                
            elif ext == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(file_path)
                page_texts = []
                for idx, page in enumerate(reader.pages):
                    txt = page.extract_text()
                    if txt:
                        page_texts.append(f"=== Page {idx+1} ===\n{txt.strip()}\n")
                full_text = "\n".join(page_texts)
                
            elif ext in [".html", ".htm"]:
                from html.parser import HTMLParser
                class MLStripper(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.reset()
                        self.convert_charrefs = True
                        self.text = []
                    def handle_data(self, d):
                        self.text.append(d)
                    def get_data(self):
                        return "".join(self.text)
                        
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        html_content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, "r", encoding="cp1252", errors="ignore") as f:
                        html_content = f.read()
                        
                stripper = MLStripper()
                stripper.feed(html_content)
                full_text = stripper.get_data()
                
            elif ext in [".txt", ".csv"]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        full_text = f.read()
                except UnicodeDecodeError:
                    with open(file_path, "r", encoding="cp1252") as f:
                        full_text = f.read()
                        
            elif ext in [".jpg", ".jpeg", ".png", ".gif"]:
                # 1. Extract image metadata specs
                from PIL import Image
                from PIL.ExifTags import TAGS
                img = Image.open(file_path)
                w, h = img.size
                img_text = f"Image Resolution: {w} x {h} pixels (Aspect Ratio: {w/h:.2f})\n"
                img_text += f"Color Mode: {img.mode}\n"
                img_text += "EXIF METADATA RECORDS:\n"
                exif_data = {}
                try:
                    info = img.getexif()
                    if info:
                        for tag, value in info.items():
                            decoded = TAGS.get(tag, tag)
                            exif_data[decoded] = value
                except Exception:
                    pass
                if exif_data:
                    for tag, val in exif_data.items():
                        img_text += f"- {tag}: {val}\n"
                else:
                    img_text += "- No EXIF metadata detected.\n"
                
                # 2. Extract visual text from image natively using high-speed Windows OCR!
                ocr_text = ""
                try:
                    import asyncio
                    import threading
                    import queue
                    from winrt.windows.media.ocr import OcrEngine
                    from winrt.windows.graphics.imaging import BitmapDecoder
                    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
                    from winrt.system import Array, UInt8

                    async def run_windows_ocr(path):
                        # Load and upscale image using high-quality cubic interpolation if it has a low resolution!
                        # This brings tiny/microscopic text into the optimal OCR readability range (DPI boost).
                        import cv2
                        img = cv2.imread(path)
                        if img is None:
                            return ""
                            
                        h, w, _ = img.shape
                        if w < 1200:
                            img = cv2.resize(img, (0, 0), fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
                            
                        # Encode the upscaled image back to PNG in memory
                        success, encoded_img = cv2.imencode(".png", img)
                        if not success:
                            return ""
                        file_bytes = encoded_img.tobytes()
                        
                        stream = InMemoryRandomAccessStream()
                        writer = DataWriter(stream.get_output_stream_at(0))
                        writer.write_bytes(Array(UInt8, file_bytes))
                        await writer.store_async()
                        
                        decoder = await BitmapDecoder.create_async(stream)
                        software_bitmap = await decoder.get_software_bitmap_async()
                        
                        engine = OcrEngine.try_create_from_user_profile_languages()
                        if not engine:
                            return "[Windows OCR Error: Engine could not be initialized]"
                            
                        result = await engine.recognize_async(software_bitmap)
                        
                        # High-Performance 2D Grid Reconstruction OCR!
                        # Reconstructs the exact horizontal layouts, side-by-side fields, 
                        # and tabular columns of the form.
                        if not result.lines:
                            return ""
                            
                        # 1. First, find global min_x (left margin) and estimate average character width
                        min_x = float('inf')
                        char_widths = []
                        
                        for line in result.lines:
                            for word in line.words:
                                rx = word.bounding_rect.x
                                rw = word.bounding_rect.width
                                min_x = min(min_x, rx)
                                char_len = len(word.text.strip())
                                if char_len > 0:
                                    char_widths.append(rw / char_len)
                                    
                        avg_char_width = sum(char_widths) / len(char_widths) if char_widths else 12.0
                        
                        # 2. Process each line directly as segmented by Windows OCR to prevent vertical collision!
                        formatted_lines = []
                        for line in result.lines:
                            # Sort words in the line by their horizontal X coordinates
                            sorted_words = sorted(line.words, key=lambda w: w.bounding_rect.x)
                            
                            row_str = ""
                            prev_end_x = min_x
                            
                            for word in sorted_words:
                                gap_px = word.bounding_rect.x - prev_end_x
                                num_spaces = max(0, int(round(gap_px / avg_char_width)))
                                row_str += (" " * num_spaces) + word.text.strip()
                                prev_end_x = word.bounding_rect.x + word.bounding_rect.width
                                
                            formatted_lines.append(row_str)
                            
                        return "\n".join(formatted_lines)

                    # Execute inside a clean background thread to avoid Tkinter STA COM apartment deadlocks!
                    q = queue.Queue()
                    def run_in_thread():
                        try:
                            res = asyncio.run(run_windows_ocr(file_path))
                            q.put((True, res))
                        except Exception as err:
                            q.put((False, err))
                    
                    t = threading.Thread(target=run_in_thread, daemon=True)
                    t.start()
                    t.join(timeout=10.0) # Wait up to 10 seconds for completion
                    
                    success, ocr_res = q.get(timeout=1.0)
                    if success:
                        ocr_text = ocr_res
                    else:
                        ocr_text = f"[Local OCR Scan Failed: {ocr_res}]"
                except Exception as ocr_err:
                    ocr_text = f"[Local OCR Scan Failed: {ocr_err}]"
                
                # Format output text with or without the metadata headers and banners!
                if self.header_mode_var.get():
                    img_text += f"\n==================================================\n"
                    img_text += f"       EXTRACTED VISUAL TEXT (WINDOWS OCR)        \n"
                    img_text += f"==================================================\n"
                    img_text += ocr_text if ocr_text else "[No visual text detected in this image]\n"
                    full_text = img_text
                else:
                    full_text = ocr_text if ocr_text else ""
                
            else:
                messagebox.showerror("Error", f"Unsupported file format: {ext}\nPlease choose a supported document or image file.", parent=self.root)
                self.status_var.set("Unsupported format selected.")
                return

            # Save the full extracted text to the specified output file!
            out_type = self.output_type_var.get()
            if not out_path.lower().endswith(out_type):
                base, _ = os.path.splitext(out_path)
                out_path = base + out_type
                self.output_file_var.set(out_path)
                
            if out_type == ".txt":
                with open(out_path, "w", encoding="utf-8") as out_f:
                    out_f.write(full_text)
            elif out_type == ".rtf":
                # Standard RTF wrapper with Consolas monospaced font
                rtf_wrapped = "{\\rtf1\\ansi\\deff0 {\\fonttbl{\\f0\\fnil\\fcharset0 Consolas;}}\n\\viewkind4\\uc1\n\\pard\\f0\\fs20 " + full_text.replace("\n", "\\par\n") + "}"
                with open(out_path, "w", encoding="ascii", errors="ignore") as out_f:
                    out_f.write(rtf_wrapped)
            elif out_type == ".pdf":
                # Generate a beautiful, complete PDF using our monospaced PDF compiler
                hoa_processor.generate_text_pdf(f"Text Extraction - {file_name}", full_text, out_path)
                
            # Display a nice preview (first 2500 characters) inside the text box
            preview_len = 2500
            preview_text = full_text[:preview_len]
            if len(full_text) > preview_len:
                preview_text += f"\n\n... [Truncated: {len(full_text) - preview_len} more characters extracted and saved to file] ..."
                
            self.display_message(preview_text)
            self.status_var.set(f"Success! Extracted & saved full text to: {os.path.basename(out_path)}")
            self.status_lbl.config(fg="#2ecc71")
            
        except Exception as e:
            messagebox.showerror("Extraction Error", f"An error occurred while extracting document text:\n{str(e)}", parent=self.root)
            self.status_var.set("Error during text extraction.")
            self.status_lbl.config(fg="#e74c3c")

    def select_output_file(self):
        if self.folder_mode_var.get():
            folder_path = filedialog.askdirectory(
                parent=self.root,
                title="Select Output Folder to Save Results"
            )
            if folder_path:
                self.output_file_var.set(os.path.normpath(folder_path))
                self.status_var.set(f"Selected Output Folder: {os.path.basename(folder_path)}")
                self.status_lbl.config(fg="#2ecc71")
        else:
            out_type = self.output_type_var.get()
            if out_type == ".txt":
                ft = ("Text Files (*.txt)", "*.txt")
            elif out_type == ".rtf":
                ft = ("Rich Text Documents (*.rtf)", "*.rtf")
            else:
                ft = ("PDF Documents (*.pdf)", "*.pdf")
                
            file_path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Specify Output Document Path",
                defaultextension=out_type,
                filetypes=[ft, ("All Files (*.*)", "*.*")]
            )
            if file_path:
                self.output_file_var.set(file_path)
                self.status_var.set(f"Target Save: {os.path.basename(file_path)}")
                self.status_lbl.config(fg="#2ecc71")

    def on_output_type_changed(self, selected_type):
        path = self.output_file_var.get().strip()
        if path and not self.folder_mode_var.get():
            base, _ = os.path.splitext(path)
            self.output_file_var.set(base + selected_type)

    def load_gui_settings(self):
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hoa_app_settings.json")
        if os.path.exists(settings_path):
            try:
                import json
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.file_path_var.set(data.get("input_path", ""))
                self.output_file_var.set(data.get("output_path", ""))
                self.year_var.set(data.get("year", "2023"))
                self.folder_mode_var.set(data.get("folder_mode", False))
                self.output_type_var.set(data.get("output_type", ".txt"))
                
                # Restore window size and position (geometry) if present
                geom = data.get("geometry", "")
                if geom:
                    # Validate that it is not a minimized/invalid state
                    parts = geom.split("+")
                    if len(parts) == 3:
                        size_part = parts[0].split("x")
                        if len(size_part) == 2:
                            w, h = int(size_part[0]), int(size_part[1])
                            x, y = int(parts[1]), int(parts[2])
                            # Check boundaries to ensure it's on-screen (supporting left/right multi-monitors)
                            if w > 100 and h > 100 and x > -15000 and y > -15000:
                                self.root.geometry(geom)
                                
                # Dynamic UI update based on loaded folder state
                self.on_folder_mode_changed()
            except Exception:
                pass

    def save_gui_settings(self):
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hoa_app_settings.json")
        data = {
            "input_path": self.file_path_var.get(),
            "output_path": self.output_file_var.get(),
            "year": self.year_var.get(),
            "folder_mode": self.folder_mode_var.get(),
            "output_type": self.output_type_var.get(),
            "geometry": self.root.geometry() # Capture exact window position and dimensions!
        }
        try:
            import json
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def on_close_window(self):
        # Cleanly auto-save all active operational parameters on window destroy!
        self.save_gui_settings()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HOAStatementApp(root)
    root.mainloop()
