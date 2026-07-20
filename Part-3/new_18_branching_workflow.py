"""
DEMO 18 — WORKFLOW CON RAMIFICACIÓN CONDICIONAL (Microsoft Agent Framework 1.11.0)
================================================================================

OBJETIVO PEDAGÓGICO
-------------------
Tercer patrón fundamental: el grafo ya no es fijo. Según los DATOS, la factura
recorre un camino u otro. Es el equivalente a un `switch`/`case` dentro del grafo.

                     ┌─► ArchiveHandler ──┐ (vuelve a decidir)
                     │                    │
    InvoiceLoader ───┼─► HighValueHandler ─┐
     (decide)        ├─► PreferredHandler ─┼─► InvoiceFinalizer
                     └─► StandardHandler ──┘
                        (Default: si nada coincide)

CONCEPTOS CLAVE
---------------
1. `add_switch_case_edge_group(origen, [Case(...), ..., Default(...)])`
   Las condiciones se evalúan EN ORDEN y gana LA PRIMERA que devuelve True.
   `Default` recoge lo que no encaja en ningún `Case` — actúa de red de seguridad.

2. LA CONDICIÓN ES UNA FUNCIÓN NORMAL: recibe el mensaje y devuelve bool. No hay
   DSL ni sintaxis especial; se pueden probar por separado (ver las funciones
   `es_*` más abajo).

3. RE-ENRUTADO EN CADENA: el ArchiveHandler NO termina el trabajo, vuelve a
   decidir. Por eso hay DOS grupos switch-case: uno en el loader y otro en el
   handler de archivado. Así se encadenan decisiones sin duplicar ramas.

4. CONVERGENCIA: las tres ramas de negocio terminan en el mismo finalizador,
   mediante `add_edge` normales. Ramificar no obliga a duplicar el final.

⚠️ DETALLE IMPORTANTE PARA SEGUIR LA DEMO
-----------------------------------------
La rama de ARCHIVADO solo se activa si YA EXISTE el archivo de esa factura en
output/. Es decir: la primera vez que procesa una factura NO verá esa rama; hay
que procesar **la misma factura dos veces** para verla en acción.

NOTA: esta demo NO usa ningún LLM — es cálculo local puro.

Ejecutar (desde el directorio Part-3, con el venv activo):
    python new_18_branching_workflow.py
"""

import asyncio
from dataclasses import dataclass, replace
from pathlib import Path
from dotenv import load_dotenv
from typing_extensions import Never

# MIGRACIÓN 1.11.0: `WorkflowOutputEvent` fue ELIMINADO. Ahora existe un único
# `WorkflowEvent` que se discrimina por su atributo `.type` (ver run_workflow()).
# `Case` y `Default` sobreviven SIN cambios respecto de la API antigua.
from agent_framework import (
    WorkflowBuilder, WorkflowContext, WorkflowEvent,
    Executor, handler, Case, Default
)

# Import our utilities
import sys
sys.path.append(str(Path(__file__).parent))
from invoice_utils import (
    InvoiceConfig, InvoiceData, read_invoices_csv, calculate_invoice_totals,
    render_invoice_text, save_invoice_file, archive_old_invoice, log_action,
    ensure_directories, print_step
)

# Load environment
load_dotenv('.env03')

# Directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
ARCHIVE_DIR = BASE_DIR / "archive"
LOGS_DIR = BASE_DIR / "logs"

# Global selection
selected_invoice_id = None


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def show_menu(invoices: list[InvoiceData]) -> str:
    """Muestra el menú de facturas y devuelve el ID de la elegida."""
    print("\n" + "="*80)
    print("FACTURAS DISPONIBLES")
    print("="*80)

    for idx, inv in enumerate(invoices, 1):
        preferred_badge = "PREFERENTE" if inv.is_preferred else "ESTANDAR  "
        # Marca las facturas ya procesadas: son las que activarán la rama de archivado
        ya_existe = " [YA EXISTE -> se archivará]" if (OUTPUT_DIR / f"{inv.invoice_id}.txt").exists() else ""
        print(f"{idx}. {preferred_badge} {inv.invoice_id} - {inv.client_name}{ya_existe}")
        print(f"   Importe: ${inv.subtotal:.2f} | Fecha: {inv.date}")
        print()

    while True:
        try:
            choice = input(f"Seleccione una factura (1-{len(invoices)}): ").strip()
            idx = int(choice)
            if 1 <= idx <= len(invoices):
                return invoices[idx - 1].invoice_id
            else:
                print(f"Introduzca un número entre 1 y {len(invoices)}")
        except ValueError:
            print("Introduzca un número válido")


def wait_for_user(message: str):
    """Pausa hasta que el usuario pulse ENTER (hace visible el camino elegido)."""
    print(f"\n{'-'*80}")
    input(f"Pulse ENTER para {message} -> ")
    print(f"{'-'*80}\n")


def analyze_invoice_routing(invoice: InvoiceData, config: InvoiceConfig) -> tuple[str, str]:
    """Decide POR QUÉ RAMA debe ir la factura y explica el motivo.

    Es el "cerebro" de la ramificación: devuelve una etiqueta de decisión que
    luego las funciones `es_*` traducen a un Case concreto.

    ⚠️ El ORDEN de las comprobaciones importa — se devuelve la PRIMERA que se
    cumple, igual que hará el switch-case del grafo.
    """
    totals = calculate_invoice_totals(invoice, config)

    # 1º) ¿Ya existe una factura previa con este ID? Hay que archivarla antes
    output_file = OUTPUT_DIR / f"{invoice.invoice_id}.txt"
    if output_file.exists():
        return "archive_needed", "Ya existe un archivo previo: hay que archivarlo"

    # 2º) ¿Supera el umbral de alto valor?
    elif totals['subtotal'] >= config.high_value_threshold:
        return "high_value", f"Alto valor (${totals['subtotal']:.2f}): se aplica descuento por volumen"

    # 3º) ¿Es cliente preferente?
    elif invoice.is_preferred:
        return "preferred", "Cliente preferente: se aplica descuento por fidelidad"

    # 4º) Si no encaja en nada, procesamiento normal (rama Default)
    else:
        return "standard", "Procesamiento normal"


# ============================================================================
# ESTRUCTURAS DE DATOS
# ============================================================================

@dataclass
class InvoiceDecision:
    """Factura + su decisión de enrutado: es el mensaje que viaja por el grafo.

    Lleva TODO lo necesario en un solo objeto (factura, config, totales y el
    motivo), de forma que cualquier rama pueda trabajar sin volver a calcular.
    """
    invoice: InvoiceData
    config: InvoiceConfig
    totals: dict
    decision_type: str  # 'high_value', 'preferred', 'standard', 'archive_needed'
    reason: str


# ============================================================================
# EJECUTORES DEL WORKFLOW
# ============================================================================

# PUNTO DE DECISIÓN INICIAL del grafo. Carga la factura, la analiza y emite un
# InvoiceDecision; el switch-case posterior mira ese objeto para elegir la rama.
class InvoiceLoader(Executor):
    """Carga la factura elegida y determina por qué rama debe ir."""

    @handler
    async def load_and_analyze(self, start_signal: str, ctx: WorkflowContext[InvoiceDecision]):
        """Lee el CSV, deja elegir una factura y calcula su decisión de enrutado."""
        print_step(1, "CARGAR Y SELECCIONAR FACTURA")

        # Los directorios se crean AQUÍ: este mismo paso ya escribe en logs/ con
        # log_action(). Antes se creaban en el finalizador, así que en una carpeta
        # limpia la demo moría con FileNotFoundError.
        ensure_directories(str(OUTPUT_DIR), str(LOGS_DIR), str(ARCHIVE_DIR))

        config = InvoiceConfig()
        csv_path = DATA_DIR / "invoices.csv"
        all_invoices = read_invoices_csv(str(csv_path))

        print(f"Se cargaron {len(all_invoices)} facturas")

        # Menú interactivo: el usuario elige qué factura procesar
        global selected_invoice_id
        selected_invoice_id = show_menu(all_invoices)
        selected_invoice = next(inv for inv in all_invoices if inv.invoice_id == selected_invoice_id)

        print(f"\nSeleccionada: {selected_invoice.invoice_id} - {selected_invoice.client_name}")
        print(f"   Importe: ${selected_invoice.subtotal:.2f}")
        print(f"   Preferente: {'SI' if selected_invoice.is_preferred else 'NO'}")

        # Aquí se decide la rama; el grafo solo ejecuta lo que diga esta función
        decision_type, reason = analyze_invoice_routing(selected_invoice, config)
        totals = calculate_invoice_totals(selected_invoice, config)

        print(f"\nRESULTADO DEL ANALISIS:")
        print(f"   Tipo de decisión: {decision_type.upper()}")
        print(f"   Motivo: {reason}")

        if decision_type == "high_value":
            print(f"   Umbral de alto valor: ${config.high_value_threshold:.2f}")
            print(f"   Descuento por alto valor: ${totals['high_value_discount']:.2f}")
        elif decision_type == "preferred":
            print(f"   Descuento por fidelidad: ${totals['preferred_discount']:.2f}")

        decision = InvoiceDecision(
            invoice=selected_invoice,
            config=config,
            totals=totals,
            decision_type=decision_type,
            reason=reason
        )

        log_action(f"Factura {selected_invoice_id} seleccionada y analizada: {decision_type}", str(LOGS_DIR))

        wait_for_user("iniciar el workflow con RAMIFICACION")

        await ctx.send_message(decision)


# ============================================================================
# CONDICIONES DE ENRUTADO
# ============================================================================
# Son funciones Python normales: reciben el mensaje y devuelven True/False.
# El grafo las evalúa EN ORDEN y usa la primera que dé True. Al ser funciones
# corrientes se pueden probar de forma aislada, sin levantar el workflow.

def es_necesario_archivar(decision: InvoiceDecision) -> bool:
    """¿Existe ya una factura previa que haya que archivar?"""
    return decision.decision_type == "archive_needed"


def es_alto_valor(decision: InvoiceDecision) -> bool:
    """¿La factura supera el umbral de alto valor?"""
    return decision.decision_type == "high_value"


def es_preferente(decision: InvoiceDecision) -> bool:
    """¿La factura es de un cliente preferente?"""
    return decision.decision_type == "preferred"


# ============================================================================
# RAMAS (una por camino posible)
# ============================================================================

# RAMA DE ARCHIVADO — es especial: NO va al finalizador, sino que vuelve a
# decidir. Por eso tiene su propio switch-case en el grafo (ver run_workflow).
class ArchiveHandler(Executor):
    """Archiva la factura anterior y vuelve a enrutar la actual."""

    @handler
    async def archive_old(self, decision: InvoiceDecision, ctx: WorkflowContext[InvoiceDecision]):
        """Mueve la factura previa a archive/ y recalcula la siguiente decisión."""
        print(f"\n[RAMA ARCHIVADO] {decision.invoice.invoice_id}")
        print(f"   Motivo: {decision.reason}")

        archived = archive_old_invoice(
            decision.invoice.invoice_id,
            str(OUTPUT_DIR),
            str(ARCHIVE_DIR)
        )

        if archived:
            print(f"   Factura anterior archivada en {ARCHIVE_DIR}")
            log_action(f"Factura anterior {decision.invoice.invoice_id} archivada", str(LOGS_DIR))

        print(f"   Continuando al siguiente punto de decisión...")

        # CLAVE: se vuelve a analizar. Como el archivo ya se movió, esta vez
        # analyze_invoice_routing() NO devolverá "archive_needed" y la factura
        # seguirá por su rama de negocio (alto valor / preferente / estándar).
        # Se usa `replace()` en vez de mutar el objeto: evita efectos colaterales
        # si alguien conservara una referencia al mensaje original.
        decision_type, reason = analyze_invoice_routing(decision.invoice, decision.config)
        decision = replace(decision, decision_type=decision_type, reason=reason)

        print(f"   Siguiente decisión: {decision_type.upper()}")
        print(f"   Motivo: {reason}")

        wait_for_user("continuar a la SIGUIENTE RAMA")

        await ctx.send_message(decision)


# RAMA 1 de negocio — factura que supera el umbral de alto valor.
class HighValueHandler(Executor):
    """Procesa facturas de alto valor (descuento por volumen)."""

    @handler
    async def process_high_value(self, decision: InvoiceDecision, ctx: WorkflowContext[InvoiceDecision]):
        """Aplica el tratamiento especial de alto valor."""
        print(f"\n[RAMA ALTO VALOR] {decision.invoice.invoice_id}")
        print(f"   Motivo: {decision.reason}")
        print(f"   Total original: ${decision.totals['total']:.2f}")
        print(f"   Descuento por alto valor: ${decision.totals['high_value_discount']:.2f}")
        print(f"   Procesamiento especial aplicado")

        log_action(f"Descuento por alto valor aplicado a {decision.invoice.invoice_id}", str(LOGS_DIR))

        wait_for_user("continuar a la FINALIZACION")

        await ctx.send_message(decision)


# RAMA 2 de negocio — cliente preferente (fidelidad).
class PreferredClientHandler(Executor):
    """Procesa facturas de clientes preferentes (descuento por fidelidad)."""

    @handler
    async def process_preferred(self, decision: InvoiceDecision, ctx: WorkflowContext[InvoiceDecision]):
        """Aplica el descuento por fidelidad."""
        print(f"\n[RAMA CLIENTE PREFERENTE] {decision.invoice.invoice_id}")
        print(f"   Motivo: {decision.reason}")
        print(f"   Cliente: {decision.invoice.client_name}")
        print(f"   Total original: ${decision.totals['total']:.2f}")
        print(f"   Descuento por fidelidad: ${decision.totals['preferred_discount']:.2f}")
        print(f"   Recompensas de fidelidad aplicadas")

        log_action(f"Descuento de cliente preferente aplicado a {decision.invoice.invoice_id}", str(LOGS_DIR))

        wait_for_user("continuar a la FINALIZACION")

        await ctx.send_message(decision)


# RAMA 3 de negocio — la del `Default`: recoge todo lo que no encaja arriba.
class StandardHandler(Executor):
    """Procesa facturas estándar (sin descuentos especiales)."""

    @handler
    async def process_standard(self, decision: InvoiceDecision, ctx: WorkflowContext[InvoiceDecision]):
        """Aplica el procesamiento normal, sin descuentos adicionales."""
        print(f"\n[RAMA ESTANDAR] {decision.invoice.invoice_id}")
        print(f"   Motivo: {decision.reason}")
        print(f"   Cliente: {decision.invoice.client_name}")
        print(f"   Total: ${decision.totals['total']:.2f}")
        print(f"   Procesamiento estándar")

        log_action(f"Procesamiento estándar para {decision.invoice.invoice_id}", str(LOGS_DIR))

        wait_for_user("continuar a la FINALIZACION")

        await ctx.send_message(decision)


# PUNTO DE CONVERGENCIA — TERMINAL del grafo. Las tres ramas de negocio acaban
# aquí. `WorkflowContext[Never, str]`: no envía nada y PRODUCE la salida del
# workflow con ctx.yield_output().
class InvoiceFinalizer(Executor):
    """Renderiza y guarda la factura, venga de la rama que venga."""

    @handler
    async def finalize(self, decision: InvoiceDecision, ctx: WorkflowContext[Never, str]):
        """Compone el documento, deja constancia de la rama recorrida y lo guarda."""
        print_step(3, "RENDERIZAR Y GUARDAR")

        print(f"Renderizando la factura {decision.invoice.invoice_id}...")

        invoice_text = render_invoice_text(
            decision.invoice,
            decision.totals,
            decision.config
        )

        # Se deja constancia EN EL DOCUMENTO de qué rama se recorrió: es lo que
        # hace visible el resultado de la ramificación al abrir el archivo.
        branch_info = f"""
DECISION DE RAMIFICACION:
=========================
Tipo de decisión: {decision.decision_type.upper()}
Motivo: {decision.reason}
Camino recorrido: {decision.decision_type.replace('_', ' ').title()}

"""

        full_invoice_text = invoice_text + branch_info

        filepath = save_invoice_file(
            decision.invoice.invoice_id,
            full_invoice_text,
            str(OUTPUT_DIR)
        )

        # Vista previa por consola antes de cerrar el workflow
        print(f"\n{'-'*80}")
        print("VISTA PREVIA DE LA FACTURA:")
        print(f"{'-'*80}")
        print(full_invoice_text)
        print(f"{'-'*80}")

        print(f"\n¡Factura guardada correctamente!")
        print(f"   Ubicación: {filepath}")
        print(f"   Rama: {decision.decision_type.upper()}")
        print(f"   Total: ${decision.totals['total']:.2f}")

        log_action(
            f"Factura {decision.invoice.invoice_id} finalizada por la rama {decision.decision_type}",
            str(LOGS_DIR)
        )

        # yield_output() marca el fin del workflow y devuelve el resultado
        summary = (f"¡Workflow con ramificación completado! Factura {decision.invoice.invoice_id} "
                   f"procesada por la rama {decision.decision_type}.")
        await ctx.yield_output(summary)


# ============================================================================
# WORKFLOW PRINCIPAL
# ============================================================================

async def run_workflow():
    """Construye y ejecuta el workflow con ramificación para UNA factura."""

    # Se instancian los ejecutores; el id es el nombre que aparece en los eventos
    loader = InvoiceLoader(id="loader")
    archive_handler = ArchiveHandler(id="archive_handler")
    high_value_handler = HighValueHandler(id="high_value_handler")
    preferred_handler = PreferredClientHandler(id="preferred_handler")
    standard_handler = StandardHandler(id="standard_handler")
    finalizer = InvoiceFinalizer(id="finalizer")

    # ------------------------------------------------------------------------
    # CONSTRUCCIÓN DEL GRAFO CON RAMIFICACIÓN
    # ------------------------------------------------------------------------
    # MIGRACIÓN 1.11.0: `set_start_executor(x)` fue ELIMINADO como método → ahora
    # es argumento del CONSTRUCTOR. `output_from=[...]` declara qué ejecutor
    # produce la salida final (sin él salta un DeprecationWarning).
    #
    # `Case` y `Default` NO cambiaron respecto de la API antigua.
    workflow = (
        WorkflowBuilder(
            start_executor=loader,
            output_from=[finalizer],     # único punto terminal del grafo
        )
        # SWITCH-CASE 1: decisión inicial. Se evalúa EN ORDEN y gana la primera
        # condición que devuelve True; `Default` recoge el resto.
        .add_switch_case_edge_group(
            loader,
            [
                Case(condition=es_necesario_archivar, target=archive_handler),
                Case(condition=es_alto_valor, target=high_value_handler),
                Case(condition=es_preferente, target=preferred_handler),
                Default(target=standard_handler)
            ]
        )
        # SWITCH-CASE 2: tras archivar se DECIDE OTRA VEZ. Aquí ya no puede
        # volver a salir "archive_needed" (el archivo se movió), por eso este
        # grupo no incluye esa rama: evita un bucle infinito.
        .add_switch_case_edge_group(
            archive_handler,
            [
                Case(condition=es_alto_valor, target=high_value_handler),
                Case(condition=es_preferente, target=preferred_handler),
                Default(target=standard_handler)
            ]
        )
        # CONVERGENCIA: las tres ramas de negocio terminan en el finalizador
        .add_edge(high_value_handler, finalizer)
        .add_edge(preferred_handler, finalizer)
        .add_edge(standard_handler, finalizer)
        .build()
    )

    # ------------------------------------------------------------------------
    # EJECUCIÓN EN STREAMING
    # ------------------------------------------------------------------------
    # MIGRACIÓN 1.11.0: `workflow.run_stream(x)` → `workflow.run(x, stream=True)`,
    # y `isinstance(event, WorkflowOutputEvent)` → `event.type == "output"`.
    event: WorkflowEvent
    async for event in workflow.run("start", stream=True):
        if event.type == "output":
            print("\n" + "="*80)
            print("WORKFLOW CON RAMIFICACION COMPLETADO")
            print("="*80)
            print(event.data)
            print("\nRevise los siguientes directorios:")
            print(f"   • Salida: {OUTPUT_DIR}")
            print(f"   • Archivo histórico: {ARCHIVE_DIR}")
            print(f"   • Registros: {LOGS_DIR}")
            print("\nNota: ¡la factura siguió su rama según las reglas de negocio!")
            print("="*80)


async def main():
    """Punto de entrada: permite procesar varias facturas seguidas.

    Cada vuelta construye un workflow NUEVO (en run_workflow), que es la forma
    recomendada de hacer ejecuciones independientes: una instancia de Workflow
    conserva su estado entre llamadas a run().
    """

    print("\n" + "="*80)
    print("GENERADOR DE FACTURAS - WORKFLOW CON RAMIFICACION")
    print("="*80)
    print("\nEsta demo muestra RAMIFICACION CONDICIONAL con pasos interactivos:")
    print("   • Usted elige UNA factura para procesar")
    print("   • El sistema la analiza y decide qué camino debe seguir")
    print("   • La factura recorre la rama que le corresponde:")
    print("     1. ¿Ya existe el archivo? -> Archiva primero la versión anterior")
    print("     2. ¿Factura de alto valor? -> Aplica descuento por volumen")
    print("     3. ¿Cliente preferente? -> Aplica descuento por fidelidad")
    print("     4. En cualquier otro caso -> Procesamiento estándar")
    print("   • La factura final se renderiza y se guarda")
    print("\nPatrón del workflow:")
    print("   Carga -> [¿Archivar?] -> [Alto valor / Preferente / Estandar] -> Finalizacion")
    print("           +--------- ENRUTADO CONDICIONAL ---------+")
    print("\nCONSEJO: procese DOS VECES la misma factura para ver la rama de archivado.")
    print("="*80)

    while True:
        await run_workflow()

        print("\n" + "="*80)
        choice = input("\n¿Procesar otra factura? (s/n): ").strip().lower()

        # Se aceptan 's' (español) e 'y' (por costumbre) como afirmativas
        if choice not in ('s', 'y'):
            print("\n¡Gracias por usar el Generador de Facturas!")
            print("="*80)
            break

        print("\n" + "="*80)
        print("REINICIANDO EL WORKFLOW...")
        print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
