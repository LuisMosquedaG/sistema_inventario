# -*- coding: utf-8 -*-
"""
Script generador del documento Word (.docx) y Markdown (.md)
para el Manual Integral de Funciones: Reloj Checador y Control de Asistencias.
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Rutas de destino
BRAIN_DIR = r"C:\Users\luism\.gemini\antigravity\brain\48938170-957f-4afe-9242-a9e967d9a78b"
MD_PATH = os.path.join(BRAIN_DIR, "documento_funciones_reloj_checador_asistencias.md")
DOCX_PATH = os.path.join(BRAIN_DIR, "documento_funciones_reloj_checador_asistencias.docx")

# Paleta de Colores Corporativa
HEX_BRAND = "00B8B9"        # Turquesa Corporativo
HEX_DARK = "1A252F"         # Azul Marino Oscuro / Antracita
HEX_CHARCOAL = "2C3E50"     # Gris Carbón Texto
HEX_MUTED = "64748B"        # Slate Gris Secundario
HEX_LIGHT_BG = "F8FAFC"     # Fondo Gris Muy Claro
HEX_BORDER = "CBD5E1"       # Borde Suave
HEX_WARNING_BG = "FFFBEB"   # Fondo Ámbar / Alerta
HEX_WARNING_BORDER = "D97706"
HEX_SUCCESS_BG = "F0FDF4"   # Fondo Verde Éxito
HEX_SUCCESS_BORDER = "16A34A"
HEX_INFO_BG = "F0FDFA"      # Fondo Turquesa Claro

COLOR_BRAND = RGBColor(0, 184, 185)
COLOR_DARK = RGBColor(26, 37, 47)
COLOR_CHARCOAL = RGBColor(44, 62, 80)
COLOR_MUTED = RGBColor(100, 116, 139)
COLOR_WHITE = RGBColor(255, 255, 255)
COLOR_WARNING = RGBColor(217, 119, 6)
COLOR_SUCCESS = RGBColor(22, 163, 74)

def set_cell_background(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=160, right=160):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), val)
        border.set(qn('w:sz'), sz)
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), color)
        tblBorders.append(border)
    border_insideV = OxmlElement('w:insideV')
    border_insideV.set(qn('w:val'), 'none')
    tblBorders.append(border_insideV)
    tblPr.append(tblBorders)

def add_header_footer(doc):
    for s_idx, section in enumerate(doc.sections):
        # Header
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("MANUAL INTEGRAL: RELOJ CHECADOR Y ASISTENCIAS | CROSSOVERSUITE")
        hrun.font.name = "Calibri"
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = COLOR_MUTED
        
        # Footer
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        frun = fp.add_run("Confidencial y de uso interno - Recursos Humanos y Control de Asistencia Laboral")
        frun.font.name = "Calibri"
        frun.font.size = Pt(8.5)
        frun.font.color.rgb = COLOR_MUTED

def add_callout(doc, text_title, text_body, callout_type="info"):
    bg_color = HEX_INFO_BG
    border_color = HEX_BRAND
    title_color = COLOR_BRAND
    
    if callout_type == "warning":
        bg_color = HEX_WARNING_BG
        border_color = HEX_WARNING_BORDER
        title_color = COLOR_WARNING
    elif callout_type == "success":
        bg_color = HEX_SUCCESS_BG
        border_color = HEX_SUCCESS_BORDER
        title_color = COLOR_SUCCESS
    elif callout_type == "dark":
        bg_color = HEX_LIGHT_BG
        border_color = HEX_DARK
        title_color = COLOR_DARK
        
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.9)
    
    cell = table.cell(0, 0)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
    
    # Left border thick
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'single')
    left.set(qn('w:sz'), '24') # 3pt
    left.set(qn('w:color'), border_color)
    tcBorders.append(left)
    
    for b_name in ['top', 'bottom', 'right']:
        b = OxmlElement(f'w:{b_name}')
        b.set(qn('w:val'), 'none')
        tcBorders.append(b)
    tcPr.append(tcBorders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    run_t = p.add_run(f"📌 {text_title.upper()}: ")
    run_t.font.name = "Calibri"
    run_t.font.size = Pt(10)
    run_t.font.bold = True
    run_t.font.color.rgb = title_color
    
    run_b = p.add_run(text_body)
    run_b.font.name = "Calibri"
    run_b.font.size = Pt(9.5)
    run_b.font.color.rgb = COLOR_CHARCOAL
    
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

print("Base setup completada...")
