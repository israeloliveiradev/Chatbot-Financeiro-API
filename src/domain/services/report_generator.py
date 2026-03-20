import os
import logging
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any
from fpdf import FPDF
import matplotlib.pyplot as plt
from uuid import UUID

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, output_dir: str = "/tmp/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_monthly_report(
        self, 
        client_name: str, 
        year_month: date, 
        summary: List[Dict[str, Any]], 
        goals: List[Any],
        ai_insights: str
    ) -> str:
        """
        Gera um relatório PDF premium com gráficos e insights.
        Retorna o path do arquivo gerado.
        """
        file_name = f"relatorio_{client_name.replace(' ', '_')}_{year_month.strftime('%Y_%m')}.pdf"
        file_path = os.path.join(self.output_dir, file_name)

        pdf = FPDF()
        pdf.add_page()
        
        # Header Premium
        pdf.set_fill_color(31, 41, 55) # Dark gray (Premium)
        pdf.rect(0, 0, 210, 40, "F")
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 20, "RELATÓRIO MENSAL", ln=True, align="C")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, f"Referente a {year_month.strftime('%B %Y')}", ln=True, align="C")
        
        pdf.ln(20)
        pdf.set_text_color(0, 0, 0)
        
        # 1. Resumo de Gastos
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "1. Detalhamento de Gastos por Categoria", ln=True)
        pdf.ln(5)
        
        # Tabela de Gastos
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(243, 244, 246)
        pdf.cell(60, 10, "Categoria", 1, 0, "C", True)
        pdf.cell(40, 10, "Limite", 1, 0, "C", True)
        pdf.cell(40, 10, "Gasto", 1, 0, "C", True)
        pdf.cell(50, 10, "Status", 1, 1, "C", True)
        
        pdf.set_font("Helvetica", "", 10)
        for s in summary:
            perc = (float(s['total_spent']) / float(s['limit_amount'])) * 100 if s['limit_amount'] > 0 else 0
            status = "CRÍTICO" if perc >= 100 else "ATENÇÃO" if perc >= 80 else "OK"
            
            pdf.cell(60, 10, s['category'], 1)
            pdf.cell(40, 10, f"R$ {float(s['limit_amount']):,.2f}", 1)
            pdf.cell(40, 10, f"R$ {float(s['total_spent']):,.2f}", 1)
            
            # Colorir status
            if status == "CRÍTICO": pdf.set_text_color(220, 38, 38)
            elif status == "ATENÇÃO": pdf.set_text_color(217, 119, 6)
            else: pdf.set_text_color(22, 163, 74)
            
            pdf.cell(50, 10, f"{status} ({perc:.1f}%)", 1, 1, "C")
            pdf.set_text_color(0, 0, 0)

        pdf.ln(10)
        
        # 2. Evolução de Objetivos
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "2. Evolução dos Objetivos Financeiros", ln=True)
        pdf.ln(5)
        
        for g in goals:
            perc = (float(g.current_amount) / float(g.target_amount)) * 100
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 10, f"{g.title}", ln=True)
            
            # Barra de progresso visual (estilizada)
            pdf.set_fill_color(229, 231, 235)
            pdf.rect(10, pdf.get_y(), 190, 5, "F")
            pdf.set_fill_color(37, 99, 235)
            bar_width = min(190, int((perc / 100) * 190))
            pdf.rect(10, pdf.get_y(), bar_width, 5, "F")
            
            pdf.ln(7)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 10, f"Progresso: {perc:.1f}% | Atual: R$ {float(g.current_amount):,.2f} | Alvo: R$ {float(g.target_amount):,.2f}", ln=True)
            pdf.ln(5)

        pdf.ln(10)
        
        # 3. Insights da IA (Seção DeepMind Style)
        pdf.set_fill_color(249, 250, 251)
        pdf.rect(5, pdf.get_y(), 200, 60, "F")
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "🧠 Análise do Especialista (Sênior AI Insight)", ln=True)
        pdf.set_font("Helvetica", "I", 10)
        pdf.multi_cell(0, 7, ai_insights)

        pdf.output(file_path)
        return file_path
