"""
DEMO 20 — VISUALIZACIÓN DE WORKFLOWS (Microsoft Agent Framework 1.11.0)
================================================================================

OBJETIVO PEDAGÓGICO
-------------------
Las demos 16-19 CONSTRUYEN y EJECUTAN grafos. Esta los **dibuja y los analiza**.
Sirve para documentar, revisar y explicar un workflow sin llegar a ejecutarlo.

Recopila los tres patrones vistos hasta ahora y los pone lado a lado:

    SECUENCIAL   A ─► B ─► C ─► D
    PARALELO     A ─┬─► B ─┬─► D ─► E
                    └─► C ─┘
    RAMIFICADO   A ─┬─(caso 1)─► B ─┐
                    ├─(caso 2)─► C ─┼─► E
                    └─(defecto)─► D ─┘

CONCEPTOS CLAVE
---------------
1. `WorkflowViz(workflow)` sabe dibujar el grafo YA CONSTRUIDO:
     • `.to_mermaid()`  → texto Mermaid (Markdown, GitHub, mermaid.live)
     • `.to_digraph()`  → texto DOT (Graphviz)
     • `.save_svg()` / `.save_png()` / `.save_pdf()` → imagen (requieren Graphviz)

2. INTROSPECCIÓN: el objeto `Workflow` se puede interrogar sin ejecutarlo:
     • `get_executors_list()`     → todos los ejecutores
     • `get_start_executor()`     → punto de entrada
     • `get_output_executors()`   → los que producen la salida
     • `get_intermediate_executors()`
     • `input_types` / `output_types` → tipos deducidos del grafo
   Esta demo usa esas APIs para analizar el grafo DE VERDAD, en vez de imprimir
   una descripción escrita a mano que se queda obsoleta al tocar el código.

3. AQUÍ NO SE EJECUTA NADA: se construyen los workflows solo para dibujarlos.
   Por eso los ejecutores de este archivo son mínimos, meros marcadores de
   posición: lo que importa es la FORMA del grafo, no lo que hace cada paso.

NOTA: esta demo NO usa ningún LLM y tampoco escribe facturas.

Ejecutar (desde el directorio Part-3, con el venv activo):
    python new_20_visualization_workflow.py
"""

import asyncio
from pathlib import Path
from dotenv import load_dotenv
from typing_extensions import Never

# MIGRACIÓN 1.11.0: esta demo NO importaba `WorkflowOutputEvent`, por eso era la
# única que sí llegaba a importarse. Fallaba más tarde, al construir el grafo.
from agent_framework import (
    WorkflowBuilder, WorkflowContext, Executor, handler,
    WorkflowViz, Case, Default
)

# Import our utilities
import sys
sys.path.append(str(Path(__file__).parent))
from invoice_utils import (
    InvoiceConfig, InvoiceData, read_invoices_csv, calculate_invoice_totals,
    render_invoice_text, save_invoice_file, ensure_directories
)

# Load environment
load_dotenv('.env03')

# Directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
VIZ_DIR = BASE_DIR / "visualizations"


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def show_workflow_menu() -> list[str]:
    """Muestra el menú de patrones y devuelve los elegidos.

    Acepta una opción suelta ("2"), varias separadas por comas ("1,3") o la
    opción 4 para verlas todas.
    """
    print("\n" + "="*80)
    print("OPCIONES DE VISUALIZACION DE WORKFLOWS")
    print("="*80)
    print("Seleccione qué patrones quiere visualizar:")
    print()
    print("1. Workflow SECUENCIAL")
    print("   • Procesamiento lineal (A -> B -> C -> D)")
    print("   • Ideal para operaciones paso a paso")
    print("   • Sin paralelismo ni ramificación")
    print()
    print("2. Workflow PARALELO")
    print("   • Procesamiento concurrente con fan-out/fan-in")
    print("   • Ideal para tareas independientes simultáneas")
    print("   • Varias tareas se ejecutan a la vez")
    print()
    print("3. Workflow RAMIFICADO")
    print("   • Enrutado condicional con switch-case")
    print("   • Ideal para decidir el camino según los datos")
    print("   • Caminos distintos según las condiciones")
    print()
    print("4. TODOS los workflows (demo completa)")
    print("   • Visualiza los tres patrones")
    print("   • Permite compararlos entre sí")
    print()

    while True:
        choice = input("Indique su selección (1-4, o separadas por comas como '1,3'): ").strip()

        if choice == "4":
            return ["sequential", "parallel", "branching"]

        equivalencias = {"1": "sequential", "2": "parallel", "3": "branching"}
        patterns: list[str] = []
        valido = True

        for c in (p.strip() for p in choice.split(",")):
            if c in equivalencias:
                # Se evitan duplicados si el usuario escribe "1,1"
                if equivalencias[c] not in patterns:
                    patterns.append(equivalencias[c])
            else:
                print(f"Opción no válida: '{c}'. Introduzca 1, 2, 3 o 4.")
                valido = False
                break

        if valido and patterns:
            return patterns
        if valido:
            print("Seleccione al menos un patrón.")


def wait_for_user(message: str):
    """Pausa hasta que el usuario pulse ENTER."""
    print(f"\n{'-'*80}")
    input(f"Pulse ENTER para {message} -> ")
    print(f"{'-'*80}\n")


# ============================================================================
# EJECUTORES (SOLO MARCADORES DE POSICIÓN)
# ============================================================================
# ⚠️ Estos ejecutores NUNCA se ejecutan: los workflows se construyen únicamente
# para dibujarlos. Se mantienen mínimos a propósito — lo que se visualiza es la
# TOPOLOGÍA del grafo, no la lógica de negocio (esa vive en invoice_utils.py y
# se demuestra en las demos 16-19).

# --- Patrón 1: cadena secuencial ---

class LoadInvoices(Executor):
    """Punto de ENTRADA del patrón secuencial: carga las facturas del CSV."""

    @handler
    async def load(self, start_signal: str, ctx: WorkflowContext[list[InvoiceData]]):
        invoices = read_invoices_csv(str(DATA_DIR / "invoices.csv"))
        await ctx.send_message(invoices)


class CalculateTotals(Executor):
    """Paso intermedio: calcula los totales de cada factura."""

    @handler
    async def calculate(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[tuple]]):
        config = InvoiceConfig()
        await ctx.send_message([(inv, calculate_invoice_totals(inv, config)) for inv in invoices])


class RenderInvoices(Executor):
    """Paso intermedio: convierte cada factura en texto."""

    @handler
    async def render(self, data: list[tuple], ctx: WorkflowContext[list[tuple]]):
        config = InvoiceConfig()
        await ctx.send_message([(inv, tot, render_invoice_text(inv, tot, config)) for inv, tot in data])


class SaveInvoices(Executor):
    """Paso TERMINAL: escribe los archivos y cierra el workflow."""

    @handler
    async def save(self, data: list[tuple], ctx: WorkflowContext[Never, str]):
        ensure_directories(str(OUTPUT_DIR), str(LOGS_DIR))
        for invoice, _totals, text in data:
            save_invoice_file(invoice.invoice_id, text, str(OUTPUT_DIR))
        await ctx.yield_output("¡Todas las facturas guardadas!")


# --- Patrón 2: fan-out / fan-in ---

class Dispatcher(Executor):
    """Punto de FAN-OUT: reparte el trabajo a las ramas paralelas."""

    @handler
    async def dispatch(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[InvoiceData]]):
        await ctx.send_message(invoices)


class TotalsCalculator(Executor):
    """Rama paralela 1: cálculo de importes."""

    @handler
    async def calculate(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[InvoiceData]]):
        await ctx.send_message(invoices)


class ClientPreparer(Executor):
    """Rama paralela 2: preparación de datos del cliente."""

    @handler
    async def prepare(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[InvoiceData]]):
        await ctx.send_message(invoices)


class Merger(Executor):
    """Punto de FAN-IN: reúne las ramas paralelas.

    ⚠️ FÍJESE EN EL TIPO: recibe `list[list[InvoiceData]]`, no `list[InvoiceData]`.
    `add_fan_in_edges` AGREGA los mensajes de todos los orígenes en UNA lista, así
    que el tipo del destino es "lista de lo que envía cada rama". Declararlo como
    `list[InvoiceData]` hace que `build()` falle con TypeCompatibilityError.
    """

    @handler
    async def merge(self, lotes: list[list[InvoiceData]], ctx: WorkflowContext[list[InvoiceData]]):
        # Las dos ramas envían el mismo lote; basta con quedarse con el primero
        await ctx.send_message(lotes[0] if lotes else [])


class Renderer(Executor):
    """Paso TERMINAL del patrón paralelo."""

    @handler
    async def render(self, invoices: list[InvoiceData], ctx: WorkflowContext[Never, str]):
        await ctx.yield_output("¡Renderizado completo!")


# --- Patrón 3: ramificación condicional ---

class Analyzer(Executor):
    """Punto de DECISIÓN: de aquí salen las aristas condicionales."""

    @handler
    async def analyze(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[InvoiceData]]):
        await ctx.send_message(invoices)


class HighValueHandler(Executor):
    """Rama condicional: facturas de alto valor."""

    @handler
    async def handle(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[InvoiceData]]):
        await ctx.send_message(invoices)


class PreferredHandler(Executor):
    """Rama condicional: clientes preferentes."""

    @handler
    async def handle(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[InvoiceData]]):
        await ctx.send_message(invoices)


class StandardHandler(Executor):
    """Rama por DEFECTO: todo lo que no encaja en las anteriores."""

    @handler
    async def handle(self, invoices: list[InvoiceData], ctx: WorkflowContext[list[InvoiceData]]):
        await ctx.send_message(invoices)


class Finalizer(Executor):
    """Punto de CONVERGENCIA y TERMINAL: las tres ramas acaban aquí."""

    @handler
    async def finalize(self, invoices: list[InvoiceData], ctx: WorkflowContext[Never, str]):
        await ctx.yield_output("¡Procesamiento completo!")


# ============================================================================
# CONSTRUCTORES DE LOS TRES GRAFOS
# ============================================================================
# MIGRACIÓN 1.11.0 (afecta a los tres): `set_start_executor(x)` fue ELIMINADO
# como método → ahora es argumento del CONSTRUCTOR. Además se declara
# `output_from=[...]` para evitar el DeprecationWarning.

def build_sequential_workflow():
    """Construye la CADENA LINEAL: cada paso alimenta al siguiente."""
    loader = LoadInvoices(id="loader")
    calculator = CalculateTotals(id="calculator")
    renderer = RenderInvoices(id="renderer")
    saver = SaveInvoices(id="saver")

    return (
        WorkflowBuilder(start_executor=loader, output_from=[saver], name="secuencial")
        .add_edge(loader, calculator)
        .add_edge(calculator, renderer)
        .add_edge(renderer, saver)
        .build()
    )


def build_parallel_workflow():
    """Construye el patrón FAN-OUT / FAN-IN.

    Se usan `add_fan_out_edges` y `add_fan_in_edges` (en vez de `add_edge` sueltos)
    porque expresan la intención real: difundir a varias ramas y ESPERAR a todas.
    Es además lo que refleja el diagrama generado.
    """
    dispatcher = Dispatcher(id="dispatcher")
    totals_calc = TotalsCalculator(id="totals_calculator")
    client_prep = ClientPreparer(id="client_preparer")
    merger = Merger(id="merger")
    renderer = Renderer(id="renderer")

    return (
        WorkflowBuilder(start_executor=dispatcher, output_from=[renderer], name="paralelo")
        .add_fan_out_edges(dispatcher, [totals_calc, client_prep])
        .add_fan_in_edges([totals_calc, client_prep], merger)
        .add_edge(merger, renderer)
        .build()
    )


def build_branching_workflow():
    """Construye el patrón SWITCH-CASE con convergencia."""
    analyzer = Analyzer(id="analyzer")
    high_value = HighValueHandler(id="high_value_handler")
    preferred = PreferredHandler(id="preferred_handler")
    standard = StandardHandler(id="standard_handler")
    finalizer = Finalizer(id="finalizer")

    # ⚠️ LAS CONDICIONES RECIBEN UN ÚNICO ARGUMENTO: el mensaje.
    # La firma que espera MFA es `Callable[[Any], bool]`. Estas funciones tenían
    # antes un segundo parámetro `ctx`, y eso las rompía EN SILENCIO: el
    # framework registraba "Error evaluating condition..." y mandaba TODO por la
    # rama Default, de modo que las ramas condicionales nunca se usaban.
    def es_alto_valor(invoices: list[InvoiceData]) -> bool:
        """¿Alguna factura del lote supera el umbral de alto valor?"""
        config = InvoiceConfig()
        return any(inv.subtotal >= config.high_value_threshold for inv in invoices)

    def es_preferente(invoices: list[InvoiceData]) -> bool:
        """¿Alguna factura del lote es de un cliente preferente?"""
        return any(inv.is_preferred for inv in invoices)

    return (
        WorkflowBuilder(start_executor=analyzer, output_from=[finalizer], name="ramificado")
        .add_switch_case_edge_group(
            analyzer,
            [
                Case(es_alto_valor, high_value),
                Case(es_preferente, preferred),
                Default(standard),
            ]
        )
        .add_edge(high_value, finalizer)
        .add_edge(preferred, finalizer)
        .add_edge(standard, finalizer)
        .build()
    )


# ============================================================================
# VISUALIZACIÓN
# ============================================================================

def visualize_workflow(workflow, title: str, pattern_type: str):
    """Genera y guarda los diagramas del workflow en Mermaid y DOT."""

    print(f"\n{'='*80}")
    print(f"VISUALIZACION: {title}")
    print(f"{'='*80}\n")

    viz = WorkflowViz(workflow)
    VIZ_DIR.mkdir(exist_ok=True)
    filename_base = pattern_type.lower()

    # --- Formato Mermaid: se renderiza solo en Markdown, GitHub o mermaid.live
    print("Diagrama Mermaid:")
    print("-" * 80)
    mermaid = viz.to_mermaid()
    print(mermaid)
    print("-" * 80)

    mermaid_file = VIZ_DIR / f"{filename_base}_workflow.mmd"
    mermaid_file.write_text(mermaid, encoding="utf-8")
    print(f"\nMermaid guardado en: {mermaid_file}")

    # --- Formato DOT (Graphviz)
    # CORRECCIÓN: la versión anterior de esta demo afirmaba que "DOT/Graphviz no
    # está disponible en esta versión". Es FALSO en 1.11.0: `to_digraph()` existe
    # y genera el texto DOT sin necesidad de tener Graphviz instalado (Graphviz
    # solo hace falta para RENDERIZAR imágenes con save_png/save_svg/save_pdf).
    dot = viz.to_digraph()
    dot_file = VIZ_DIR / f"{filename_base}_workflow.dot"
    dot_file.write_text(dot, encoding="utf-8")
    print(f"DOT guardado en:     {dot_file}")

    # --- Imagen SVG: esto SÍ necesita Graphviz instalado en el sistema
    try:
        svg_path = viz.save_svg(str(VIZ_DIR / f"{filename_base}_workflow.svg"))
        print(f"SVG guardado en:     {svg_path}")
    except Exception as e:
        # No es un fallo de la demo: simplemente falta la dependencia del sistema
        print(f"SVG no generado (requiere Graphviz instalado): {type(e).__name__}")

    print("\n" + "="*80)


def print_workflow_analysis(workflow, title: str):
    """Analiza el grafo INTERROGANDO al objeto Workflow, sin ejecutarlo.

    La versión anterior imprimía una descripción escrita a mano para cada patrón;
    si alguien cambiaba el grafo, el análisis seguía diciendo lo de antes. Aquí
    todo sale de la API, así que no puede desincronizarse.
    """

    print(f"\nAnálisis: {title}")
    print("-" * 80)

    ejecutores = workflow.get_executors_list()
    inicial = workflow.get_start_executor()
    ids_salida = {e.id for e in workflow.get_output_executors()}

    # NOTA: `get_intermediate_executors()` solo devuelve los DESIGNADOS de forma
    # explícita con `intermediate_output_from=`. Aquí no se usa esa opción, así
    # que el papel "intermedio" se deduce por descarte: ni entrada ni salida.
    print(f"Ejecutores en el workflow ({len(ejecutores)}):")
    for i, ex in enumerate(ejecutores, 1):
        if ex.id == inicial.id:
            papel = "punto de entrada"
        elif ex.id in ids_salida:
            papel = "punto de salida"
        else:
            papel = "intermedio"
        print(f"  {i}. {ex.id:<22} ({papel})")

    # Los tipos se DEDUCEN del grafo: entrada del ejecutor inicial, salida de los
    # terminales. Útil para saber con qué hay que invocar el workflow.
    def nombres(tipos):
        return ", ".join(getattr(t, "__name__", str(t)) for t in tipos) or "n/d"

    print(f"\nTipo de entrada:  {nombres(workflow.input_types)}")
    print(f"Tipo de salida:   {nombres(workflow.output_types)}")
    print("-" * 80)


# ============================================================================
# DEMO INTERACTIVA
# ============================================================================

# Tabla única con los tres patrones: constructor, título y para qué sirve.
# Tenerlo en un solo sitio evita que el menú, el análisis y el resumen final
# se contradigan entre sí.
PATRONES = {
    "sequential": (build_sequential_workflow, "Workflow Secuencial",
                   "Ideal para procesos paso a paso donde cada etapa depende de la anterior"),
    "parallel":   (build_parallel_workflow, "Workflow Paralelo",
                   "Ideal para tareas independientes que pueden ejecutarse a la vez"),
    "branching":  (build_branching_workflow, "Workflow Ramificado",
                   "Ideal para enrutar según los datos o las reglas de negocio"),
}


async def visualize_pattern(pattern_type: str):
    """Construye, dibuja y analiza un patrón concreto."""
    constructor, title, _uso = PATRONES[pattern_type]

    workflow = constructor()
    visualize_workflow(workflow, title, pattern_type)
    print_workflow_analysis(workflow, title)

    wait_for_user("continuar a la siguiente visualización")


async def main():
    """Ejecuta la demo interactiva de visualización."""

    print("\n" + "="*80)
    print("GENERADOR DE FACTURAS - VISUALIZACION DE WORKFLOWS")
    print("="*80)
    print("\nEsta demo dibuja los distintos patrones de workflow:")
    print("  • Secuencial  - Procesamiento lineal")
    print("  • Paralelo    - Procesamiento concurrente con fan-out/fan-in")
    print("  • Ramificado  - Enrutado condicional con switch-case")
    print("\nFormatos de salida:")
    print("  • Mermaid (.mmd) - para Markdown, GitHub y mermaid.live")
    print("  • DOT (.dot)     - para Graphviz")
    print("  • SVG (.svg)     - imagen, solo si Graphviz está instalado")
    print("\nNOTA: aquí los workflows NO se ejecutan, solo se dibujan y analizan.")
    print("="*80)

    ensure_directories(str(VIZ_DIR))

    selected_patterns = show_workflow_menu()

    titulos = ", ".join(PATRONES[p][1] for p in selected_patterns)
    print(f"\nPatrones seleccionados: {titulos}")
    wait_for_user("iniciar la visualización")

    for i, pattern in enumerate(selected_patterns, 1):
        titulo = PATRONES[pattern][1].upper()
        print(f"\n\n{'#'*80}")
        print(f"#  {titulo}  ({i} de {len(selected_patterns)})")
        print(f"{'#'*80}")

        await visualize_pattern(pattern)

    # ------------------------------------------------------------------------
    # RESUMEN FINAL
    # ------------------------------------------------------------------------
    print("\n\n" + "="*80)
    print("VISUALIZACION COMPLETADA")
    print("="*80)
    print(f"\nDirectorio de salida: {VIZ_DIR}")
    print("\nArchivos generados:")

    for pattern in selected_patterns:
        print(f"  • {pattern}_workflow.mmd (Mermaid)")
        print(f"  • {pattern}_workflow.dot (DOT/Graphviz)")

    print("\nCómo usarlos:")
    print("  • Pegue el contenido de un .mmd en https://mermaid.live")
    print("  • Los .mmd se renderizan solos dentro de un bloque ```mermaid en Markdown")
    print("  • Para convertir un .dot en imagen: dot -Tpng archivo.dot -o archivo.png")

    print("\nResumen de los patrones visualizados:")
    for pattern in selected_patterns:
        _c, titulo, uso = PATRONES[pattern]
        print(f"  {titulo}: {uso}")

    print("\n" + "="*80)
    print("¡Todos los patrones seleccionados se visualizaron correctamente!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
