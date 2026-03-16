from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from datetime import datetime
import matplotlib.pyplot as plt
import io

class ReportGenerator:
    """Генератор PDF отчётов"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()

        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            pdfmetrics.registerFont(TTFont('DejaVu', font_path))
            self.font_name = 'DejaVu'
        except:
            self.font_name = 'Helvetica'
        
    def generate_inspection_report(self, inspection_data, output_path):
        """Создайте PDF отчёт для конкретной проверки"""
        
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        elements = []
        
        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontName=self.font_name,
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30,
            alignment=1  # center
        )

        elements.append(Paragraph("Отчёт о проверке печатной платы", title_style))
        elements.append(Spacer(1, 0.3*inch))
        
        # Информация о проверке
        info_data = [
            ['Параметр', 'Значение'],
            ['ID проверки', inspection_data['inspection_id']],
            ['Дата и время', inspection_data['timestamp']],
            ['Файл', inspection_data['image_info']['filename']],
            ['Разрешение', f"{inspection_data['image_info']['width']}x{inspection_data['image_info']['height']}"],
            ['Статус', inspection_data['results']['status'].upper()],
            ['Всего дефектов', str(inspection_data['results']['total_defects'])]
        ]
        
        info_table = Table(info_data, colWidths=[3*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Детали дефектов
        if inspection_data['results']['detections']:
            elements.append(Paragraph("Обнаруженные дефекты", title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            defects_data = [['#', 'Тип дефекта', 'Серьёзность', 'Уверенность']]
            
            for idx, defect in enumerate(inspection_data['results']['detections'], 1):
                defects_data.append([
                    str(idx),
                    defect['class_ru'],
                    defect['severity'].upper(),
                    f"{defect['confidence']*100:.1f}%"
                ])
            
            defects_table = Table(defects_data)
            defects_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(defects_table)
        
        # Сборка PDF
        doc.build(elements)
        return output_path