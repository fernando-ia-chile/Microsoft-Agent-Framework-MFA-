"""
DEMO 16 — WORKFLOW SECUENCIAL (Microsoft Agent Framework, core 1.11.0)
================================================================================

OBJETIVO PEDAGÓGICO
-------------------
Mostrar el patrón de workflow más simple: una CADENA LINEAL de ejecutores donde
la salida de cada paso alimenta al siguiente. Es la base de las demos 17-21.

    load_config → read_invoices → calculate_totals → render_invoice → save_invoice

CONCEPTOS CLAVE
---------------
1. EJECUTOR: unidad de trabajo del grafo. Aquí se usa el decorador `@executor(id=...)`
   sobre funciones async (la forma más ligera). Las demos 17-21 usan la variante
   con clases `Executor` + `@handler`, necesaria cuando el paso guarda estado.

2. WorkflowContext[T] — el TIPO ES EL CONTRATO DE LA ARISTA:
       WorkflowContext[T]         → este paso ENVÍA un T con `ctx.send_message(...)`
       WorkflowContext[Never, T]  → paso TERMINAL: no envía nada y PRODUCE un T
                                    con `ctx.yield_output(...)`
   El framework valida en `build()` que los tipos de pasos conectados encajen.

3. SUPERSTEPS: el motor es tipo Pregel. Los mensajes entre ejecutores se entregan
   al final de cada superstep y NO son visibles en el stream de eventos; solo se
   observan los eventos de workflow (output, status, executor_*).

NOTA: esta demo NO usa ningún LLM — es cálculo local puro. El `load_dotenv` está
solo por coherencia con el resto de la serie y para leer las variables INVOICE_*.

Ejecutar (desde el directorio Part-3, con el venv activo):
    python new_16_sequential_workflow.py
"""

import asyncio
from pathlib import Path
from dotenv import load_dotenv
from typing_extensions import Never

# MIGRACIÓN 1.11.0: `WorkflowOutputEvent` fue ELIMINADO. Ahora existe un único
# `WorkflowEvent` que se discrimina por su atributo `.type` (ver run_workflow()).
from agent_framework import WorkflowBuilder, WorkflowContext, WorkflowEvent, executor

# Import our utilities
import sys
sys.path.append(str(Path(__file__).parent))
from invoice_utils import (
    InvoiceConfig, InvoiceData, read_invoices_csv, calculate_invoice_totals,
    render_invoice_text, save_invoice_file, log_action, ensure_directories,
    print_step, print_invoice_summary
)

# Load environment
load_dotenv('.env03')

# Directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Global state for interactive processing
selected_invoice_id = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def show_menu(invoices: list[InvoiceData]) -> str:
    """Muestra el menú de facturas y devuelve el ID de la elegida.

    Repite hasta recibir un número válido: la demo no debe caerse por un typo.
    """
    print("\n" + "="*80)
    print("📋 FACTURAS DISPONIBLES")
    print("="*80)

    for idx, inv in enumerate(invoices, 1):
        preferred_badge = "⭐" if inv.is_preferred else "  "
        print(f"{idx}. {preferred_badge} {inv.invoice_id} - {inv.client_name}")
        print(f"   Importe: ${inv.subtotal:.2f} | Fecha: {inv.date}")
        print()

    while True:
        try:
            choice = input(f"Seleccione una factura (1-{len(invoices)}): ").strip()
            idx = int(choice)
            if 1 <= idx <= len(invoices):
                return invoices[idx - 1].invoice_id
            else:
                print(f"❌ Introduzca un número entre 1 y {len(invoices)}")
        except ValueError:
            print("❌ Introduzca un número válido")


def wait_for_user(step_name: str):
    """Pausa la ejecución hasta que el usuario pulse ENTER.

    Es lo que hace visible el avance PASO A PASO del workflow: sin esta pausa
    los cinco ejecutores correrían de golpe y no se vería la secuencia.
    """
    print(f"\n{'─'*80}")
    input(f"⏸️  Pulse ENTER para continuar a: {step_name} ▶️  ")
    print(f"{'─'*80}\n")


# ============================================================================
# SEQUENTIAL WORKFLOW EXECUTORS
# ============================================================================

# PASO 1 del grafo — ENTRADA del workflow.
# Recibe la señal de arranque ("start") y produce el InvoiceConfig que alimenta
# al resto de la cadena. `WorkflowContext[InvoiceConfig]` declara justo eso:
# "este paso ENVÍA un InvoiceConfig al siguiente".
@executor(id="load_config")
async def load_configuration(start_signal: str, ctx: WorkflowContext[InvoiceConfig]) -> None:
    """Paso 1: carga la configuración de negocio desde las variables de entorno."""
    print_step(1, "CARGAR CONFIGURACION")
    print("🔧 Cargando configuración...")

    # Los directorios se crean AQUÍ (paso 1) y no en el paso 5: este mismo paso
    # ya escribe en logs/ con log_action(). Antes se creaban solo al guardar, así
    # que en una carpeta limpia la demo moría con FileNotFoundError.
    ensure_directories(str(OUTPUT_DIR), str(LOGS_DIR))

    # Lee las variables INVOICE_* (todas con valor por defecto)
    config = InvoiceConfig()

    print(f"\n✅ ¡Configuración cargada correctamente!")
    print(f"   📊 Tasa de impuesto: {config.tax_rate * 100:g}%")
    print(f"   💰 Umbral de alto valor: ${config.high_value_threshold:.2f}")
    print(f"   🎁 Descuento por alto valor: {config.high_value_discount * 100:g}%")
    print(f"   ⭐ Descuento cliente preferente: {config.preferred_client_discount * 100:g}%")

    log_action(f"Configuración cargada: {config}", str(LOGS_DIR))

    wait_for_user("PASO 2 - Leer datos de facturas")

    # send_message() entrega el mensaje al siguiente ejecutor de la cadena
    await ctx.send_message(config)


# PASO 2 del grafo — lee el CSV y deja que el usuario elija UNA factura.
# A partir de aquí los datos viajan como TUPLA: cada paso recibe lo que necesita
# y reenvía una tupla algo más grande. Es el estilo del ejemplo original.
@executor(id="read_invoices")
async def read_invoice_data(config: InvoiceConfig, ctx: WorkflowContext[tuple[InvoiceConfig, InvoiceData]]) -> None:
    """Paso 2: lee las facturas del CSV y selecciona una."""
    print_step(2, "LEER DATOS Y SELECCIONAR FACTURA")
    print("📂 Leyendo facturas desde el archivo CSV...")

    csv_path = DATA_DIR / "invoices.csv"
    all_invoices = read_invoices_csv(str(csv_path))

    print(f"\n✅ Se cargaron {len(all_invoices)} facturas desde {csv_path.name}")

    # Menú interactivo: el usuario elige qué factura procesar
    global selected_invoice_id
    selected_invoice_id = show_menu(all_invoices)

    # Localiza el objeto correspondiente al ID elegido
    selected_invoice = next(inv for inv in all_invoices if inv.invoice_id == selected_invoice_id)

    print(f"\n✅ Factura seleccionada: {selected_invoice.invoice_id}")
    print(f"   Cliente: {selected_invoice.client_name}")
    print(f"   Email: {selected_invoice.client_email}")
    print(f"   Concepto: {selected_invoice.item_description}")
    print(f"   Cantidad: {selected_invoice.quantity}")
    print(f"   Precio unitario: ${selected_invoice.unit_price:.2f}")
    print(f"   Subtotal: ${selected_invoice.subtotal:.2f}")
    print(f"   Cliente preferente: {'⭐ SI' if selected_invoice.is_preferred else '❌ NO'}")

    log_action(f"Factura {selected_invoice_id} seleccionada para procesar", str(LOGS_DIR))

    wait_for_user("PASO 3 - Calcular totales")

    # Se envía la config JUNTO a la factura elegida: el paso 3 necesita ambas
    await ctx.send_message((config, selected_invoice))


# PASO 3 del grafo — aplica las reglas de negocio (descuentos + impuesto).
# El cálculo real vive en invoice_utils.calculate_invoice_totals(); este ejecutor
# solo orquesta y muestra el desglose.
@executor(id="calculate_totals")
async def calculate_totals_step(data: tuple[InvoiceConfig, InvoiceData],
                                ctx: WorkflowContext[tuple[InvoiceData, dict]]) -> None:
    """Paso 3: calcula descuentos, impuesto y total de la factura elegida."""
    print_step(3, "CALCULAR TOTALES")

    # Se desempaqueta la tupla que envió el paso 2
    config, invoice = data

    print(f"🧮 Calculando importes de {invoice.invoice_id}...")
    print(f"   Subtotal de partida: ${invoice.subtotal:.2f}")

    totals = calculate_invoice_totals(invoice, config)

    print(f"\n✅ ¡Cálculo completado!")
    print(f"\n   {'Concepto':<30} {'Importe':>15}")
    print(f"   {'-'*30} {'-'*15}")
    print(f"   {'Subtotal':<30} ${totals['subtotal']:>14,.2f}")

    # Los porcentajes se leen de la config: escritos a mano mentirían si se
    # cambiara una variable INVOICE_* (mismo criterio que en invoice_utils).
    if totals['high_value_discount'] > 0:
        etiqueta = f"Desc. alto valor ({config.high_value_discount*100:g}%)"
        print(f"   {etiqueta:<30} -${totals['high_value_discount']:>13,.2f}")

    if totals['preferred_discount'] > 0:
        etiqueta = f"Desc. preferente ({config.preferred_client_discount*100:g}%)"
        print(f"   {etiqueta:<30} -${totals['preferred_discount']:>13,.2f}")

    if totals['total_discount'] > 0:
        print(f"   {'-'*30} {'-'*15}")
        print(f"   {'Importe tras descuentos':<30} ${totals['amount_after_discount']:>14,.2f}")

    etiqueta_impuesto = f"Impuesto ({config.tax_rate*100:g}%)"
    print(f"   {etiqueta_impuesto:<30} ${totals['tax']:>14,.2f}")
    print(f"   {'='*30} {'='*15}")
    print(f"   {'💰 TOTAL A PAGAR':<30} ${totals['total']:>14,.2f}")
    print(f"   {'='*30} {'='*15}")
    
    log_action(f"Totales calculados para {invoice.invoice_id}: ${totals['total']:.2f}", str(LOGS_DIR))

    wait_for_user("PASO 4 - Renderizar factura")

    await ctx.send_message((invoice, totals))


# PASO 4 del grafo — convierte los datos en el documento de texto final.
# No escribe nada en disco todavía: solo genera la cadena y la reenvía.
@executor(id="render_invoice")
async def render_invoice_step(data: tuple[InvoiceData, dict],
                              ctx: WorkflowContext[tuple[InvoiceData, dict, str]]) -> None:
    """Paso 4: renderiza la factura como texto formateado."""
    print_step(4, "RENDERIZAR FACTURA")

    invoice, totals = data
    config = InvoiceConfig()

    print(f"🖨️  Renderizando la factura {invoice.invoice_id} como texto...")

    invoice_text = render_invoice_text(invoice, totals, config)

    print(f"\n✅ ¡Factura renderizada! ({len(invoice_text)} caracteres)")

    # Vista previa por consola antes de guardar
    print(f"\n{'─'*80}")
    print("📄 VISTA PREVIA DE LA FACTURA:")
    print(f"{'─'*80}")
    print(invoice_text)
    print(f"{'─'*80}")

    log_action(f"Factura {invoice.invoice_id} renderizada", str(LOGS_DIR))

    wait_for_user("PASO 5 - Guardar factura")

    await ctx.send_message((invoice, totals, invoice_text))


# PASO 5 del grafo — TERMINAL. Guarda el archivo y cierra el workflow.
# `WorkflowContext[Never, str]` significa: no envía nada a nadie (Never) y
# PRODUCE un str como salida del workflow mediante ctx.yield_output().
@executor(id="save_invoice")
async def save_invoice_step(data: tuple[InvoiceData, dict, str],
                            ctx: WorkflowContext[Never, str]) -> None:
    """Paso 5: guarda la factura en el directorio de salida."""
    print_step(5, "GUARDAR FACTURA")

    invoice, totals, invoice_text = data

    print(f"💾 Guardando la factura {invoice.invoice_id} en disco...")

    filepath = save_invoice_file(invoice.invoice_id, invoice_text, str(OUTPUT_DIR))

    print(f"\n✅ ¡Factura guardada correctamente!")
    print(f"   📁 Ubicación: {filepath}")
    print(f"   📊 Cliente: {invoice.client_name}")
    print(f"   💵 Importe: ${totals['total']:.2f}")

    log_action(f"Factura {invoice.invoice_id} guardada en {filepath}", str(LOGS_DIR))

    # yield_output() marca el fin del workflow y devuelve el resultado al llamador
    summary = f"✅ ¡Workflow secuencial completado! Factura {invoice.invoice_id} procesada con éxito."
    await ctx.yield_output(summary)


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

async def run_workflow():
    """Run the sequential invoice workflow for ONE selected invoice."""

    # ------------------------------------------------------------------------
    # CONSTRUCCIÓN DEL GRAFO
    # ------------------------------------------------------------------------
    # MIGRACIÓN 1.11.0: `set_start_executor(x)` fue ELIMINADO como método.
    # El ejecutor inicial ahora se declara como argumento del CONSTRUCTOR.
    #
    # `output_from=[...]` declara qué ejecutores producen la salida final del
    # workflow (sus `yield_output` generan eventos type="output"). Sin este
    # argumento el framework emite un DeprecationWarning: la designación
    # explícita será OBLIGATORIA en una versión futura.
    #
    # Cada `add_edge(A, B)` es una arista dirigida: lo que A envía con
    # `send_message` llega a B. Al ser una cadena lineal, esto podría escribirse
    # también como `.add_chain([...])`; se dejan las aristas explícitas porque
    # hacen visible la topología, que es justo lo que enseña la demo.
    workflow = (
        WorkflowBuilder(
            start_executor=load_configuration,
            output_from=[save_invoice_step],   # el paso terminal de la cadena
        )
        .add_edge(load_configuration, read_invoice_data)
        .add_edge(read_invoice_data, calculate_totals_step)
        .add_edge(calculate_totals_step, render_invoice_step)
        .add_edge(render_invoice_step, save_invoice_step)
        .build()
    )

    # ------------------------------------------------------------------------
    # EJECUCIÓN EN STREAMING
    # ------------------------------------------------------------------------
    # MIGRACIÓN 1.11.0: `workflow.run_stream(x)` fue ELIMINADO
    # → ahora es `workflow.run(x, stream=True)`.
    #
    # El antiguo `isinstance(event, WorkflowOutputEvent)` se reemplaza por el
    # discriminador `event.type == "output"`. Otros tipos útiles para depurar:
    # "started", "status", "executor_invoked", "executor_completed", "failed".
    event: WorkflowEvent
    async for event in workflow.run("start", stream=True):
        if event.type == "output":
            print("\n" + "="*80)
            print("🎉 WORKFLOW COMPLETADO")
            print("="*80)
            print(event.data)
            print("\n📁 Revise los siguientes directorios:")
            print(f"   • Salida: {OUTPUT_DIR}")
            print(f"   • Registros: {LOGS_DIR}")
            print("="*80)


async def main():
    """Punto de entrada: permite procesar varias facturas seguidas.

    Cada vuelta del bucle CONSTRUYE UN WORKFLOW NUEVO (en run_workflow), que es
    la forma recomendada de hacer ejecuciones independientes: una instancia de
    Workflow conserva su estado entre llamadas a run().
    """

    print("\n" + "="*80)
    print("🧾 GENERADOR DE FACTURAS - WORKFLOW SECUENCIAL INTERACTIVO")
    print("="*80)
    print("\n✨ Esta demo muestra un workflow secuencial con pasos INTERACTIVOS:")
    print("   • Usted elige UNA factura para procesar")
    print("   • Cada paso del workflow se detiene para que pueda revisarlo")
    print("   • Pulse ENTER para avanzar al siguiente paso")
    print("   • Verá los resultados intermedios en cada etapa")
    print("\n📋 Pasos del workflow:")
    print("   1. Cargar configuración → Muestra impuestos y descuentos")
    print("   2. Leer y seleccionar factura → Elija del menú")
    print("   3. Calcular totales → Vea el desglose de importes")
    print("   4. Renderizar factura → Vista previa del documento")
    print("   5. Guardar factura → Escribe el archivo de salida")
    print("="*80)

    while True:
        # Procesa una factura completa a través del workflow
        await run_workflow()

        # ¿Otra factura?
        print("\n" + "="*80)
        choice = input("\n🔄 ¿Procesar otra factura? (s/n): ").strip().lower()

        # Se aceptan 's' (español) e 'y' (por costumbre) como afirmativas
        if choice not in ('s', 'y'):
            print("\n👋 ¡Gracias por usar el Generador de Facturas!")
            print("="*80)
            break

        print("\n" + "="*80)
        print("🔄 REINICIANDO EL WORKFLOW...")
        print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
