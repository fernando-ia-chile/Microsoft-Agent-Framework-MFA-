"""
UTILIDADES COMPARTIDAS — Invoice Builder Workflows (Part-3)
================================================================================

Librería común de las 6 demos (`new_16` … `new_21`). Es I/O + cálculo puro:
**NO depende de `agent_framework`** ni de ningún SDK de Azure, y por tanto no le
afecta la migración a core 1.11.0.

DIVISIÓN DE RESPONSABILIDADES
-----------------------------
    invoice_utils.py  →  QUÉ se hace (lógica de negocio: leer, calcular, renderizar)
    new_1N_*.py       →  CÓMO se orquesta (topología del grafo de workflow)

Las demos solo cambian la forma del grafo; el trabajo real vive aquí. Al añadir
lógica de negocio nueva, va en este archivo, no en los ejecutores.

⚠️ CONTRATO ESTABLE: las 6 demos consumen estas firmas. En particular,
`calculate_invoice_totals` devuelve un `dict[str, float]` con claves fijas; se
mantiene deliberadamente como dict (y no como dataclass) para no romper las demos
que aún no se han migrado.
"""

import csv
import os
import shutil
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass


@dataclass
class InvoiceData:
    """Representa un registro de factura leído del CSV."""
    invoice_id: str
    client_name: str
    client_email: str
    is_preferred: bool
    item_description: str
    quantity: int
    unit_price: float
    date: str

    @property
    def subtotal(self) -> float:
        """Subtotal = cantidad * precio unitario (antes de descuentos e impuestos)."""
        return self.quantity * self.unit_price


class InvoiceConfig:
    """Configuración de negocio, leída de variables de entorno.

    Todas las variables tienen valor por defecto, así que las demos funcionan sin
    ningún archivo .env. Se leen en el constructor (no a nivel de módulo) para que
    un cambio de entorno se refleje al crear una instancia nueva.
    """

    def __init__(self):
        self.tax_rate = float(os.getenv("INVOICE_TAX_RATE", "0.10"))
        self.high_value_threshold = float(os.getenv("INVOICE_HIGH_VALUE_THRESHOLD", "5000.00"))
        self.high_value_discount = float(os.getenv("INVOICE_HIGH_VALUE_DISCOUNT", "0.05"))
        self.preferred_client_discount = float(os.getenv("INVOICE_PREFERRED_DISCOUNT", "0.03"))
        self.company_name = os.getenv("INVOICE_COMPANY_NAME", "TechServices Inc.")
        self.company_address = os.getenv("INVOICE_COMPANY_ADDRESS", "123 Business St, Tech City, TC 12345")

    def __repr__(self):
        return (f"InvoiceConfig(tax={self.tax_rate*100}%, "
                f"high_value_threshold=${self.high_value_threshold}, "
                f"high_value_discount={self.high_value_discount*100}%, "
                f"preferred_discount={self.preferred_client_discount*100}%)")


def _pct(rate: float) -> str:
    """Formatea una tasa (0.10) como porcentaje legible ('10%').

    Evita decimales inútiles: 0.10 -> '10%', 0.075 -> '7.5%'.
    """
    valor = rate * 100
    return f"{valor:g}%"


def read_invoices_csv(csv_path: str | Path) -> list[InvoiceData]:
    """Lee las facturas desde un archivo CSV.

    Se aplica .strip() a los campos para tolerar espacios accidentales en el CSV,
    que de otro modo romperían el parseo de int/float o el flag is_preferred.
    """
    invoices: list[InvoiceData] = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            invoice = InvoiceData(
                invoice_id=row['invoice_id'].strip(),
                client_name=row['client_name'].strip(),
                client_email=row['client_email'].strip(),
                is_preferred=row['is_preferred'].strip().lower() == 'true',
                item_description=row['item_description'].strip(),
                quantity=int(row['quantity']),
                unit_price=float(row['unit_price']),
                date=row['date'].strip()
            )
            invoices.append(invoice)

    return invoices


def calculate_invoice_totals(invoice: InvoiceData, config: InvoiceConfig) -> dict[str, float]:
    """Calcula todos los importes de la factura: descuentos, impuesto y total.

    Orden de aplicación (importa): los descuentos se restan del subtotal y el
    impuesto se calcula sobre el importe YA descontado, no sobre el subtotal.

    Los dos descuentos son ACUMULABLES: una factura de alto valor de un cliente
    preferente recibe ambos.

    Devuelve un dict con claves fijas — contrato consumido por las 6 demos.
    """
    subtotal = invoice.subtotal

    # Descuento por alto valor: se aplica si el subtotal alcanza el umbral
    high_value_discount = 0.0
    if subtotal >= config.high_value_threshold:
        high_value_discount = subtotal * config.high_value_discount

    # Descuento por cliente preferente: independiente del monto
    preferred_discount = 0.0
    if invoice.is_preferred:
        preferred_discount = subtotal * config.preferred_client_discount

    total_discount = high_value_discount + preferred_discount
    amount_after_discount = subtotal - total_discount

    # El impuesto grava el importe ya descontado
    tax = amount_after_discount * config.tax_rate
    total = amount_after_discount + tax

    return {
        'subtotal': subtotal,
        'high_value_discount': high_value_discount,
        'preferred_discount': preferred_discount,
        'total_discount': total_discount,
        'amount_after_discount': amount_after_discount,
        'tax': tax,
        'total': total
    }


def render_invoice_text(invoice: InvoiceData, totals: dict, config: InvoiceConfig) -> str:
    """Renderiza la factura como texto plano formateado (ancho fijo de 80 columnas)."""

    lines = []
    lines.append("=" * 80)
    lines.append(f"{config.company_name}".center(80))
    lines.append(f"{config.company_address}".center(80))
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"FACTURA: {invoice.invoice_id}")
    lines.append(f"Fecha: {invoice.date}")
    lines.append("")
    lines.append(f"Facturar a:")
    lines.append(f"  {invoice.client_name}")
    lines.append(f"  {invoice.client_email}")
    if invoice.is_preferred:
        lines.append(f"  ⭐ CLIENTE PREFERENTE")
    lines.append("")
    lines.append("-" * 80)
    lines.append(f"{'DESCRIPCION':<40} {'CANT.':<10} {'PRECIO':<15} {'IMPORTE':>15}")
    lines.append("-" * 80)
    lines.append(f"{invoice.item_description:<40} {invoice.quantity:<10} "
                f"${invoice.unit_price:<14.2f} ${totals['subtotal']:>14.2f}")
    lines.append("")
    lines.append(f"{'Subtotal:':<65} ${totals['subtotal']:>14.2f}")

    # Los porcentajes se derivan de la config, NO se escriben a mano: antes estaban
    # fijos ("5%", "3%", "10%") y mentían si se cambiaba una variable INVOICE_*.
    if totals['high_value_discount'] > 0:
        etiqueta = f"Descuento por alto valor ({_pct(config.high_value_discount)}):"
        lines.append(f"{etiqueta:<65} -${totals['high_value_discount']:>13.2f}")

    if totals['preferred_discount'] > 0:
        etiqueta = f"Descuento cliente preferente ({_pct(config.preferred_client_discount)}):"
        lines.append(f"{etiqueta:<65} -${totals['preferred_discount']:>13.2f}")

    if totals['total_discount'] > 0:
        lines.append(f"{'Importe tras descuentos:':<65} ${totals['amount_after_discount']:>14.2f}")

    etiqueta_impuesto = f"Impuesto ({_pct(config.tax_rate)}):"
    lines.append(f"{etiqueta_impuesto:<65} ${totals['tax']:>14.2f}")
    lines.append("-" * 80)
    lines.append(f"{'TOTAL A PAGAR:':<65} ${totals['total']:>14.2f}")
    lines.append("=" * 80)
    lines.append("")
    lines.append("¡Gracias por su confianza!")
    lines.append("")

    return "\n".join(lines)


def save_invoice_file(invoice_id: str, content: str, output_dir: str | Path) -> str:
    """Guarda la factura en el directorio de salida y devuelve la ruta escrita."""
    filepath = Path(output_dir) / f"{invoice_id}.txt"
    filepath.write_text(content, encoding='utf-8')

    # Se devuelve str (no Path) porque las demos lo interpolan directamente en prints
    return str(filepath)


def archive_old_invoice(invoice_id: str, output_dir: str | Path, archive_dir: str | Path) -> bool:
    """Archiva la factura existente, si la hay, añadiéndole un timestamp.

    Devuelve True si se archivó algo, False si no existía factura previa.
    """
    output_path = Path(output_dir) / f"{invoice_id}.txt"

    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = Path(archive_dir) / f"{invoice_id}_{timestamp}.txt"

        # El destino debe existir o shutil.move falla
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(output_path), str(archive_path))
        return True

    return False


def log_action(message: str, log_dir: str | Path, log_file: str = "invoice_workflow.log"):
    """Añade una línea con timestamp al log del workflow."""
    log_path = Path(log_dir) / log_file
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")


def ensure_directories(*dirs: str | Path):
    """Crea todos los directorios indicados si no existen (idempotente)."""
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)


def print_step(step_number: int, step_name: str, details: str = ""):
    """Imprime la cabecera de un paso del workflow."""
    print(f"\n{'='*80}")
    print(f"PASO {step_number}: {step_name}")
    print(f"{'='*80}")
    if details:
        print(details)


def print_invoice_summary(invoice: InvoiceData, totals: dict):
    """Imprime un resumen compacto de la factura por consola."""
    print(f"\n📄 Factura: {invoice.invoice_id}")
    print(f"   Cliente: {invoice.client_name} {'⭐' if invoice.is_preferred else ''}")
    print(f"   Concepto: {invoice.item_description}")
    print(f"   Cantidad: {invoice.quantity} x ${invoice.unit_price:.2f}")
    print(f"   Subtotal: ${totals['subtotal']:.2f}")
    if totals['total_discount'] > 0:
        print(f"   Descuento: -${totals['total_discount']:.2f}")
    print(f"   Impuesto: ${totals['tax']:.2f}")
    print(f"   💰 TOTAL: ${totals['total']:.2f}")
