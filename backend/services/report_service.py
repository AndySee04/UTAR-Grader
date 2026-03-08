from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from io import BytesIO
from typing import List, Dict, Any
from datetime import datetime


class ReportService:
    """Service for generating Excel and PDF reports."""
    
    def generate_excel_summary(
        self,
        exam_name: str,
        students: List[Dict[str, Any]],
        questions: List[Dict[str, Any]]
    ) -> bytes:
        """
        Generate Excel summary report for all students.
        
        Args:
            exam_name: Name of the exam
            students: List of student grade summaries
            questions: List of questions with max marks
            
        Returns:
            Excel file as bytes
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Grade Summary"
        
        # Styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Title
        ws.merge_cells('A1:F1')
        ws['A1'] = f"Grade Report: {exam_name}"
        ws['A1'].font = Font(bold=True, size=14)
        ws['A2'] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Headers
        headers = ["Student Name"] + [q.get("question_number", f"Q{i+1}") for i, q in enumerate(questions)] + ["Total", "Percentage"]
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal='center')
        
        # Max marks row
        ws.cell(row=5, column=1, value="Max Marks").font = Font(italic=True)
        total_max = 0
        for col, q in enumerate(questions, 2):
            max_marks = q.get("max_marks", 0)
            ws.cell(row=5, column=col, value=max_marks).border = border
            total_max += max_marks
        ws.cell(row=5, column=len(questions) + 2, value=total_max).border = border
        ws.cell(row=5, column=len(questions) + 3, value="100%").border = border
        
        # Student data
        for row, student in enumerate(students, 6):
            ws.cell(row=row, column=1, value=student.get("student_name", "Unknown")).border = border
            
            grades = student.get("grades", [])
            grade_by_q = {g.get("question_number"): g for g in grades}
            
            for col, q in enumerate(questions, 2):
                q_num = q.get("question_number")
                grade = grade_by_q.get(q_num, {})
                score = grade.get("score", 0)
                ws.cell(row=row, column=col, value=score).border = border
            
            ws.cell(row=row, column=len(questions) + 2, value=student.get("total_score", 0)).border = border
            ws.cell(row=row, column=len(questions) + 3, value=f"{student.get('percentage', 0):.1f}%").border = border
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 20
        for col in range(2, len(headers) + 1):
            ws.column_dimensions[chr(64 + col)].width = 10
        
        # Save to bytes
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()
    
    def generate_student_pdf(
        self,
        exam_name: str,
        student_name: str,
        grades: List[Dict[str, Any]],
        total_score: float,
        total_max: float,
        percentage: float
    ) -> bytes:
        """
        Generate PDF report for a single student.
        
        Args:
            exam_name: Name of the exam
            student_name: Student's name
            grades: List of grade details
            total_score: Total score achieved
            total_max: Maximum possible score
            percentage: Percentage score
            
        Returns:
            PDF file as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1  # Center
        )
        
        elements = []
        
        # Title
        elements.append(Paragraph(f"Grade Report: {exam_name}", title_style))
        elements.append(Paragraph(f"<b>Student:</b> {student_name}", styles['Normal']))
        elements.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Summary
        elements.append(Paragraph(f"<b>Total Score:</b> {total_score:.1f} / {total_max:.1f}", styles['Normal']))
        elements.append(Paragraph(f"<b>Percentage:</b> {percentage:.1f}%", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Grades table
        table_data = [["Question", "Score", "Max", "Feedback"]]
        
        for grade in grades:
            table_data.append([
                grade.get("question_number", ""),
                f"{grade.get('score', 0):.1f}",
                f"{grade.get('max_marks', 0):.1f}",
                grade.get("feedback", "")[:100]  # Truncate long feedback
            ])
        
        table = Table(table_data, colWidths=[1*inch, 0.8*inch, 0.8*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),  # Feedback left-aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E8E8E8')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()


# Singleton instance
report_service = ReportService()
