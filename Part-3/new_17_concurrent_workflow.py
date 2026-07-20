"""
DEMO 17 — WORKFLOW CONCURRENTE / FAN-OUT + FAN-IN (Microsoft Agent Framework 1.11.0)
================================================================================

OBJETIVO PEDAGÓGICO
-------------------
Pasar de la cadena lineal de la demo 16 a un grafo que ejecuta trabajo EN PARALELO
y luego lo reúne. Es el segundo patrón fundamental de workflows.

    Dispatcher ─┬─► TotalsCalculator ──┐
                ├─► ClientInfoPreparer ─┼─► ResultsMerger ─► InvoiceRenderer
                └─► CreditChecker ─────┘
                └──────────────────────┘
                  (el original también viaja al merger)

CONCEPTOS CLAVE
---------------
1. FAN-OUT (`add_fan_out_edges`): un ejecutor difunde el MISMO mensaje a varios
   destinos, que se ejecutan CONCURRENTEMENTE (no en secuencia).

2. FAN-IN (`add_fan_in_edges`): varias aristas convergen en un destino con
   SINCRONIZACIÓN AUTOMÁTICA. El framework espera a que TODOS los orígenes
   terminen y entrega sus mensajes juntos, en UNA sola lista.
   → Por eso el handler recibe `list[...]` y no un mensaje suelto.

3. La concurrencia es REAL, no simulada: las tres tareas duermen 0.1s, 0.5s y
   0.8s. En secuencia serían ~1.4s; al ejecutarse en paralelo el bloque tarda
   ~0.8s (lo que tarda la más lenta). La demo lo mide y lo imprime.

4. CLASES `Executor` + `@handler` en vez del `@executor` de la demo 16: se usan
   cuando hay varios tipos de mensaje o el paso necesita configuración propia.

NOTA: esta demo NO usa ningún LLM — es cálculo local puro.

Ejecutar (desde el directorio Part-3, con el venv activo):
    python new_17_concurrent_workflow.py
"""

import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv
from typing_extensions import Never
from dataclasses import dataclass

# MIGRACIÓN 1.11.0: `WorkflowOutputEvent` fue ELIMINADO. Ahora existe un único
# `WorkflowEvent` que se discrimina por su atributo `.type` (ver run_workflow()).
from agent_framework import WorkflowBuilder, WorkflowContext, WorkflowEvent, Executor, handler

# Import our utilities
import sys
sys.path.append(str(Path(__file__).parent))
from invoice_utils import (
    InvoiceConfig, InvoiceData, read_invoices_csv, calculate_invoice_totals,
    render_invoice_text, save_invoice_file, log_action, ensure_directories,
    print_step
)

# Load environment
load_dotenv('.env03')

# Directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Global selection
selected_invoice_id = None

# Marca de tiempo para DEMOSTRAR que el paralelismo es real. Se toma justo antes
# del fan-out y se lee en el merger, de modo que mide SOLO el bloque concurrente
# y no incluye las pausas interactivas de input().
fanout_inicio: float | None = None

# Duración simulada de cada tarea paralela (segundos). En secuencia sumarían 1.4 s;
# ejecutándose en paralelo el bloque debe tardar ~0.8 s, la más lenta de las tres.
DURACION_TOTALS = 0.1
DURACION_CLIENT = 0.5
DURACION_CREDIT = 0.8
DURACION_SECUENCIAL = DURACION_TOTALS + DURACION_CLIENT + DURACION_CREDIT


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def show_menu(invoices: list[InvoiceData]) -> str:
    """Muestra el menú de facturas y devuelve el ID de la elegida."""
    print("\n" + "="*80)
    print("FACTURAS DISPONIBLES")
    print("="*80)
    
    for idx, inv in enumerate(invoices, 1):
        preferred_badge = "PREFERENTE" if inv.is_preferred else "ESTANDAR "
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
                print(f"Introduzca un número entre 1 y {len(invoices)}")
        except ValueError:
            print("Introduzca un número válido")


def wait_for_user(message: str):
    """Pausa hasta que el usuario pulse ENTER (hace visible el avance)."""
    print(f"\n{'-'*80}")
    input(f"Pulse ENTER para {message} -> ")
    print(f"{'-'*80}\n")


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class InvoiceWithConfig:
    """Factura + configuración: lo que el dispatcher difunde a las 3 tareas."""
    invoice: InvoiceData
    config: InvoiceConfig


@dataclass
class TotalsResult:
    """Resultado de la tarea paralela 1 (cálculo de totales)."""
    invoice_id: str
    totals: dict


@dataclass
class ClientResult:
    """Resultado de la tarea paralela 2 (ficha del cliente)."""
    invoice_id: str
    client_info: dict


@dataclass
class CreditResult:
    """Resultado de la tarea paralela 3 (verificación de crédito)."""
    invoice_id: str
    credit_check: dict


@dataclass
class MergedResult:
    """Fusión de las tres ramas paralelas + los datos originales."""
    invoice: InvoiceData
    config: InvoiceConfig
    totals: dict
    client_info: dict
    credit_check: dict


# ============================================================================
# CONCURRENT WORKFLOW EXECUTORS
# ============================================================================

# PUNTO DE FAN-OUT del grafo. Carga los datos, deja elegir factura y difunde el
# MISMO mensaje a las tres tareas, que a partir de ahí corren en paralelo.
class Dispatcher(Executor):
    """Carga la factura y la reparte a los procesadores paralelos."""
    
    @handler
    async def dispatch(self, start_signal: str, ctx: WorkflowContext[InvoiceWithConfig]):
        """Lee el CSV, deja elegir una factura y la envía al fan-out."""
        print_step(1, "CARGAR Y SELECCIONAR FACTURA")

        # Los directorios se crean AQUÍ y no en el renderer: este mismo paso ya
        # escribe en logs/ con log_action(). Antes se creaban al final, así que en
        # una carpeta limpia la demo moría con FileNotFoundError.
        ensure_directories(str(OUTPUT_DIR), str(LOGS_DIR))

        config = InvoiceConfig()
        csv_path = DATA_DIR / "invoices.csv"
        all_invoices = read_invoices_csv(str(csv_path))
        
        print(f"Se cargaron {len(all_invoices)} facturas")
        
        # Let user select
        global selected_invoice_id
        selected_invoice_id = show_menu(all_invoices)
        selected_invoice = next(inv for inv in all_invoices if inv.invoice_id == selected_invoice_id)
        
        print(f"\nSeleccionada: {selected_invoice.invoice_id} - {selected_invoice.client_name}")
        print(f"   Importe: ${selected_invoice.subtotal:.2f}")
        print(f"   Preferente: {'SI' if selected_invoice.is_preferred else 'NO'}")
        
        log_action(f"Factura {selected_invoice_id} seleccionada para proceso paralelo", str(LOGS_DIR))
        
        wait_for_user("iniciar el proceso EN PARALELO")

        # Cronómetro DESPUÉS de la pausa interactiva: así el tiempo medido es solo
        # el del trabajo concurrente, sin contar lo que tarde el usuario.
        global fanout_inicio
        fanout_inicio = time.perf_counter()

        data = InvoiceWithConfig(invoice=selected_invoice, config=config)
        await ctx.send_message(data)


# TAREA PARALELA 1 — aplica las reglas de negocio (descuentos + impuesto).
# Corre a la vez que ClientInfoPreparer y CreditChecker: ninguna espera a la otra.
class TotalsCalculator(Executor):
    """Calcula los totales de la factura (TAREA PARALELA 1)."""
    
    @handler
    async def calculate(self, data: InvoiceWithConfig, ctx: WorkflowContext[TotalsResult]):
        """Calcula subtotal, descuentos, impuesto y total."""
        print(f"\n[TOTALES] Calculando totales de {data.invoice.invoice_id}...")
        
        # Simula tiempo de proceso (ver DURACION_* arriba)
        await asyncio.sleep(DURACION_TOTALS)
        
        totals = calculate_invoice_totals(data.invoice, data.config)
        
        print(f"   ¡Cálculo completado!")
        print(f"      Subtotal: ${totals['subtotal']:.2f}")
        print(f"      Descuentos: -${totals['total_discount']:.2f}")
        print(f"      Impuesto: ${totals['tax']:.2f}")
        print(f"      Total: ${totals['total']:.2f}")
        
        result = TotalsResult(invoice_id=data.invoice.invoice_id, totals=totals)
        await ctx.send_message(result)


# TAREA PARALELA 2 — arma la ficha comercial del cliente.
# No depende de los importes, por eso puede correr a la vez que el cálculo.
class ClientInfoPreparer(Executor):
    """Prepara la información del cliente (TAREA PARALELA 2)."""
    
    @handler
    async def prepare(self, data: InvoiceWithConfig, ctx: WorkflowContext[ClientResult]):
        """Construye la ficha del cliente (estado, saludo, gestor)."""
        print(f"\n[CLIENTE] Preparando ficha de cliente de {data.invoice.invoice_id}...")
        
        # Simula tiempo de proceso (ver DURACION_* arriba)
        await asyncio.sleep(DURACION_CLIENT)
        
        client_info = {
            'name': data.invoice.client_name,
            'email': data.invoice.client_email,
            'is_preferred': data.invoice.is_preferred,
            'status': 'VIP' if data.invoice.is_preferred else 'Estandar',
            'greeting': f"Estimado/a {data.invoice.client_name}:",
            'account_manager': f"AM-{data.invoice.client_name[:3].upper()}",
            'last_order_date': '2024-12-01' if data.invoice.is_preferred else '2024-11-15'
        }
        
        print(f"   ¡Ficha de cliente lista!")
        print(f"      Nombre: {client_info['name']}")
        print(f"      Categoría: {client_info['status']}")
        print(f"      Email: {client_info['email']}")
        print(f"      Gestor de cuenta: {client_info['account_manager']}")
        
        result = ClientResult(invoice_id=data.invoice.invoice_id, client_info=client_info)
        await ctx.send_message(result)


# TAREA PARALELA 3 — simula una verificación de crédito (la más lenta: 0.8 s).
# Al ser la más lenta, es la que marca la duración total del bloque paralelo.
class CreditChecker(Executor):
    """Realiza la verificación de crédito (TAREA PARALELA 3)."""
    
    @handler
    async def check_credit(self, data: InvoiceWithConfig, ctx: WorkflowContext[CreditResult]):
        """Asigna score, límite y riesgo, y aprueba o rechaza la factura."""
        print(f"\n[CREDITO] Verificando crédito de {data.invoice.invoice_id}...")
        
        # Simula tiempo de proceso (ver DURACION_* arriba)
        await asyncio.sleep(DURACION_CREDIT)
        
        # Simulate credit check logic based on invoice amount and client status
        invoice_amount = data.invoice.subtotal
        is_preferred = data.invoice.is_preferred
        
        # Lógica de scoring: cliente preferente > factura alta > resto
        if is_preferred:
            credit_score = 850
            credit_limit = 50000
            risk_level = "LOW"
        elif invoice_amount > 5000:
            credit_score = 720
            credit_limit = 25000
            risk_level = "MEDIUM"
        else:
            credit_score = 650
            credit_limit = 10000
            risk_level = "MEDIUM"
        
        # ¿Cabe el importe dentro del límite de crédito?
        approved = invoice_amount <= credit_limit
        
        credit_check = {
            'credit_score': credit_score,
            'credit_limit': credit_limit,
            'risk_level': risk_level,
            'approved': approved,
            'invoice_amount': invoice_amount,
            'available_credit': credit_limit - invoice_amount if approved else 0,
            'check_timestamp': '2024-12-09T10:30:00Z'
        }
        
        status = "APROBADO" if approved else "RECHAZADO"
        print(f"   ¡Verificación de crédito completada!")
        print(f"      Estado: {status}")
        print(f"      Puntuación: {credit_score}")
        print(f"      Límite: ${credit_limit:,.0f}")
        print(f"      Riesgo: {risk_level}")
        
        result = CreditResult(invoice_id=data.invoice.invoice_id, credit_check=credit_check)
        await ctx.send_message(result)


class ResultsMerger(Executor):
    """Reúne los resultados de las tres tareas paralelas (punto de FAN-IN).

    MIGRACIÓN 1.11.0 — SINCRONIZACIÓN NATIVA
    ----------------------------------------
    Antes este ejecutor tenía CUATRO handlers (uno por tipo de mensaje), guardaba
    cada resultado en un atributo de instancia y un método `_check_and_merge()`
    comprobaba a mano si ya habían llegado los cuatro, con reseteo manual al final.

    Eso ya no hace falta: `add_fan_in_edges(...)` sincroniza por nosotros. El
    framework espera a que TODOS los orígenes terminen y entrega sus mensajes
    JUNTOS en una sola lista → un único handler, y CERO estado mutable.

    Ventaja real: el estado en la instancia era frágil. Si el workflow se
    reejecutaba sin recrear el ejecutor, los residuos de la corrida anterior
    podían disparar un merge prematuro.
    """

    @handler
    async def merge(
        self,
        results: list[InvoiceWithConfig | TotalsResult | ClientResult | CreditResult],
        ctx: WorkflowContext[MergedResult],
    ):
        """Recibe los 4 mensajes ya sincronizados y los fusiona en uno solo.

        La lista es HETEROGÉNEA: llegan el mensaje original del dispatcher más los
        tres resultados paralelos. El orden NO está garantizado, así que se
        clasifican por tipo en vez de por posición.
        """
        print(f"\n[FUSION] Fan-in completo: {len(results)} mensajes recibidos juntos")

        # PRUEBA DE QUE EL PARALELISMO ES REAL: si las tres tareas se hubieran
        # ejecutado en secuencia, aquí habrían pasado ~1.4 s. En paralelo tarda
        # lo que la más lenta (~0.8 s).
        if fanout_inicio is not None:
            transcurrido = time.perf_counter() - fanout_inicio
            ahorro = DURACION_SECUENCIAL - transcurrido
            print(f"   [TIEMPO] Bloque paralelo: {transcurrido:.2f}s "
                  f"(en secuencia habria tardado {DURACION_SECUENCIAL:.2f}s "
                  f"-> ahorro {ahorro:.2f}s)")

        original: InvoiceWithConfig | None = None
        totals: TotalsResult | None = None
        client: ClientResult | None = None
        credit: CreditResult | None = None

        # Clasificación por tipo — nunca por índice: el orden de llegada depende
        # de cuánto tarde cada tarea paralela.
        for r in results:
            if isinstance(r, InvoiceWithConfig):
                original = r
            elif isinstance(r, TotalsResult):
                totals = r
                print(f"   [FUSION] TOTALES de {r.invoice_id}")
            elif isinstance(r, ClientResult):
                client = r
                print(f"   [FUSION] FICHA DE CLIENTE de {r.invoice_id}")
            elif isinstance(r, CreditResult):
                credit = r
                print(f"   [FUSION] VERIFICACION DE CREDITO de {r.invoice_id}")

        # Si el grafo está bien cableado esto no debería fallar nunca; se valida
        # de forma explícita para que un error de cableado se vea de inmediato.
        if not (original and totals and client and credit):
            raise RuntimeError(
                "Fan-in incompleto: falta algún mensaje. Revisa add_fan_in_edges()."
            )

        print(f"\n[FUSION] Las tres tareas paralelas terminaron: fusionando resultados...")

        merged = MergedResult(
            invoice=original.invoice,
            config=original.config,
            totals=totals.totals,
            client_info=client.client_info,
            credit_check=credit.credit_check,
        )

        wait_for_user("proceed to RENDERING")

        await ctx.send_message(merged)


# PASO FINAL — TERMINAL del grafo. Recibe el MergedResult ya fusionado, compone
# el documento y lo guarda. `WorkflowContext[Never, str]`: no envía nada y PRODUCE
# la salida del workflow con ctx.yield_output().
class InvoiceRenderer(Executor):
    """Renderiza y guarda la factura final."""
    
    @handler
    async def render(self, data: MergedResult, ctx: WorkflowContext[Never, str]):
        """Compone factura + crédito + cliente en un solo documento y lo guarda."""
        print_step(3, "RENDERIZAR Y GUARDAR")
        
        ensure_directories(str(OUTPUT_DIR), str(LOGS_DIR))
        
        print(f"Renderizando la factura {data.invoice.invoice_id}...")
        
        # Render invoice text
        invoice_text = render_invoice_text(data.invoice, data.totals, data.config)
        
        # Add credit check information
        credit_info = f"""
RESULTADO DE LA VERIFICACION DE CREDITO:
====================
Estado: {'APROBADO' if data.credit_check['approved'] else 'RECHAZADO'}
Puntuacion de credito: {data.credit_check['credit_score']}
Limite de credito: ${data.credit_check['credit_limit']:,.2f}
Nivel de riesgo: {data.credit_check['risk_level']}
Importe de la factura: ${data.credit_check['invoice_amount']:,.2f}
Credito disponible: ${data.credit_check['available_credit']:,.2f}
Fecha de verificacion: {data.credit_check['check_timestamp']}

"""
        
        # Add client information
        client_info = f"""
INFORMACION DEL CLIENTE:
==================
Nombre: {data.client_info['name']}
Email: {data.client_info['email']}
Categoria: {data.client_info['status']}
Gestor de cuenta: {data.client_info['account_manager']}
Ultimo pedido: {data.client_info['last_order_date']}

"""
        
        # Combine all information
        full_invoice_text = invoice_text + credit_info + client_info
        
        # Show preview
        print(f"\n{'-'*80}")
        print("VISTA PREVIA DE LA FACTURA:")
        print(f"{'-'*80}")
        print(full_invoice_text)
        print(f"{'-'*80}")
        
        # Save to file
        filepath = save_invoice_file(data.invoice.invoice_id, full_invoice_text, str(OUTPUT_DIR))
        
        print(f"\n¡Factura guardada correctamente!")
        print(f"   Ubicación: {filepath}")
        print(f"   Cliente: {data.client_info['name']} ({data.client_info['status']})")
        print(f"   Importe: ${data.totals['total']:.2f}")
        print(f"   Crédito: {'APROBADO' if data.credit_check['approved'] else 'RECHAZADO'} (Puntuación: {data.credit_check['credit_score']})")
        
        log_action(f"Factura {data.invoice.invoice_id} renderizada y guardada (workflow concurrente con verificación de crédito)", str(LOGS_DIR))
        
        summary = f"¡Workflow concurrente completado! Factura {data.invoice.invoice_id} procesada con 3 tareas en paralelo."
        await ctx.yield_output(summary)


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

async def run_workflow():
    """Construye y ejecuta el workflow concurrente para UNA factura."""
    
    # Se instancian los ejecutores; el id es el nombre que aparece en los eventos
    dispatcher = Dispatcher(id="dispatcher")
    totals_calc = TotalsCalculator(id="totals_calculator")
    client_prep = ClientInfoPreparer(id="client_preparer")
    credit_checker = CreditChecker(id="credit_checker")
    merger = ResultsMerger(id="merger")
    renderer = InvoiceRenderer(id="renderer")

    # ------------------------------------------------------------------------
    # CONSTRUCCIÓN DEL GRAFO CONCURRENTE
    # ------------------------------------------------------------------------
    # MIGRACIÓN 1.11.0: `set_start_executor(x)` fue ELIMINADO como método →
    # ahora es un argumento del CONSTRUCTOR. `output_from=[...]` declara qué
    # ejecutor produce la salida final (sin él salta un DeprecationWarning).
    #
    # FAN-OUT: el dispatcher difunde el MISMO InvoiceWithConfig a las tres tareas,
    # que corren CONCURRENTEMENTE.
    #
    # FAN-IN: las cuatro aristas convergen en el merger CON SINCRONIZACIÓN
    # AUTOMÁTICA. El dispatcher se incluye como origen porque el merger necesita
    # la factura original (config incluida) para reconstruir el resultado final.
    #
    # Antes esto se cableaba metiendo el merger dentro de la lista del fan-out y
    # añadiendo además tres `add_edge` sueltos hacia él. Funcionaba, pero eran
    # aristas independientes SIN sincronización: el merger se invocaba una vez por
    # cada mensaje y tenía que llevar la cuenta a mano. `add_fan_in_edges` expresa
    # la intención real —"espera a los cuatro"— en una sola línea.
    workflow = (
        WorkflowBuilder(
            start_executor=dispatcher,
            output_from=[renderer],          # el paso terminal del grafo
        )
        .add_fan_out_edges(dispatcher, [totals_calc, client_prep, credit_checker])
        .add_fan_in_edges([dispatcher, totals_calc, client_prep, credit_checker], merger)
        .add_edge(merger, renderer)
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
            print("WORKFLOW CONCURRENTE COMPLETADO")
            print("="*80)
            print(event.data)
            print("\nRevise los siguientes directorios:")
            print(f"   • Salida: {OUTPUT_DIR}")
            print(f"   • Registros: {LOGS_DIR}")
            print("\nNota: ¡los tres ejecutores corrieron EN PARALELO para mayor rendimiento!")
            print("   ¡Cada factura incluye totales, ficha de cliente Y verificación de crédito!")
            print("="*80)


async def main():
    """Punto de entrada: permite procesar varias facturas seguidas.

    Cada vuelta construye un workflow NUEVO (en run_workflow), que es la forma
    recomendada de hacer ejecuciones independientes: una instancia de Workflow
    conserva su estado entre llamadas a run().
    """
    
    print("\n" + "="*80)
    print("GENERADOR DE FACTURAS - WORKFLOW CONCURRENTE")
    print("="*80)
    print("\nEsta demo muestra PROCESO EN PARALELO con pasos interactivos:")
    print("   • Usted elige UNA factura para procesar")
    print("   • TRES tareas se ejecutan SIMULTANEAMENTE:")
    print("     1. Calcular totales (importes, descuentos, impuesto)")
    print("     2. Preparar ficha del cliente (nombre, categoría, email)")
    print("     3. Verificar crédito (puntuación, límite, aprobación)")
    print("   • Los resultados SE FUSIONAN cuando terminan las tres tareas")
    print("   • La factura final se renderiza y se guarda")
    print("\nPatrón del workflow:")
    print("   Dispatcher -> [Totales + Ficha cliente + Crédito] -> Fusion -> Renderizado")
    print("                 +--------- EJECUCION EN PARALELO ---------+")
    print("="*80)
    
    while True:
        await run_workflow()
        
        print("\n" + "="*80)
        choice = input("\n¿Procesar otra factura? (s/n): ").strip().lower()
        
        if choice not in ('s', 'y'):  # se aceptan 's' e 'y'
            print("\n¡Gracias por usar el Generador de Facturas!")
            print("="*80)
            break
        
        print("\n" + "="*80)
        print("REINICIANDO EL WORKFLOW...")
        print("="*80)


if __name__ == "__main__":
    asyncio.run(main())