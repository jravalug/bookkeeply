#!/usr/bin/env fish


cd /home/jravalug/devcode/salemanager && conda run -n webdev python -c "
import sqlite3
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

conn = sqlite3.connect('instance/bookkeeply.db')
cur = conn.cursor()
cur.execute('SELECT name FROM business WHERE id=1')
business_name = cur.fetchone()[0]
cur.execute('SELECT name, price FROM product WHERE business_id=1 ORDER BY category, name')
products = cur.fetchall()
conn.close()

wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Productos'

# Estilo encabezado
header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
header_align = Alignment(horizontal='center', vertical='center')

thin = Side(style='thin', color='BFBFBF')
border = Border(left=thin, right=thin, top=thin, bottom=thin)

# Fila de encabezado
ws.append(['NOMBRE', 'PRECIO'])
for cell in ws[1]:
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = header_align
    cell.border = border

ws.row_dimensions[1].height = 22

# Filas de datos
alt_fill = PatternFill(start_color='DEEAF1', end_color='DEEAF1', fill_type='solid')
data_font = Font(name='Calibri', size=10)

for i, (name, price) in enumerate(products, start=2):
    ws.cell(row=i, column=1, value=name)
    ws.cell(row=i, column=2, value=price)
    for col in [1, 2]:
        cell = ws.cell(row=i, column=col)
        cell.font = data_font
        cell.border = border
        if i % 2 == 0:
            cell.fill = alt_fill
    ws.cell(row=i, column=2).number_format = '#,##0.00'
    ws.cell(row=i, column=2).alignment = Alignment(horizontal='right')

# Ajustar anchos
ws.column_dimensions['A'].width = 50
ws.column_dimensions['B'].width = 14

output = 'data/productos_negocio_1_el_solar.xlsx'
wb.save(output)
print(f'Exportado: {output} ({len(products)} productos de {business_name})')
"