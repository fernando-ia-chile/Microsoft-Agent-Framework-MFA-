"""
DEMO 19 — HUMAN-IN-THE-LOOP + CHECKPOINTING (Microsoft Agent Framework 1.11.0)
================================================================================

OBJETIVO PEDAGÓGICO
-------------------
Cuarto patrón: el workflow **se detiene de verdad**, devuelve el control al
programa que lo llamó, espera una respuesta humana y **reanuda** donde estaba.
Además guarda checkpoints en disco en cada pausa.

    Preparación ─► ConfirmarImpuesto ─► ConfirmarDescuento ─► Finalizar
                        ⏸ PAUSA              ⏸ PAUSA
                   (espera al humano)   (espera al humano)

CONCEPTOS CLAVE
---------------
1. `await ctx.request_info(datos, TipoDeRespuesta)`
   Emite un evento `type == "request_info"` y **detiene el workflow**. El estado
   pasa a `IDLE_WITH_PENDING_REQUESTS`. No es una pausa simulada con `input()`:
   el motor realmente cede el control.

2. `@response_handler`
   Método del MISMO ejecutor que recibe la respuesta cuando llega. El framework
   empareja petición y respuesta por los TIPOS de sus parámetros
   (`original_request` y `response`).
   → Por eso preguntar y procesar viven juntos: no hacen falta dos ejecutores.

3. REANUDAR: `workflow.run(responses={request_id: valor}, stream=True)`
   Se responde por `request_id`, así que puede haber varias peticiones a la vez.
   ⚠️ En la reanudación NO se vuelve a pasar el mensaje inicial: `message` y
   `responses` son excluyentes.

4. CHECKPOINTING: `WorkflowBuilder(..., checkpoint_storage=...)` guarda el estado
   al final de cada superstep, **incluidas las peticiones pendientes**. Eso es lo
   que permitiría retomar el trabajo incluso tras reiniciar el proceso.

⚠️ LA RESPUESTA DEL USUARIO IMPORTA DE VERDAD
---------------------------------------------
Si rechaza el impuesto, NO se suma al total. Si rechaza el descuento, NO se
resta. El total final cambia según lo que conteste — compruébelo ejecutando dos
veces con respuestas distintas.

NOTA: esta demo NO usa ningún LLM — es cálculo local puro.

Ejecutar (desde el directorio Part-3, con el venv activo):
    python new_19_interactive_checkpointing.py
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from typing_extensions import Never

# MIGRACIÓN 1.11.0: `WorkflowOutputEvent`, `WorkflowStatusEvent`,
# `RequestInfoExecutor` y `RequestInfoMessage` fueron ELIMINADOS. El HITL ahora se
# hace con `ctx.request_info()` + el decorador `@response_handler`.
from agent_framework import (
    WorkflowBuilder,
    Executor,
    handler,
    response_handler,
    WorkflowContext,
    WorkflowEvent,
    WorkflowRunState,
    FileCheckpointStorage,
)

# Import invoice utilities
sys.path.append(str(Path(__file__).parent))
from invoice_utils import (
    InvoiceConfig, InvoiceData, read_invoices_csv, calculate_invoice_totals,
    log_action, ensure_directories
)

# Directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
CHECKPOINTS_DIR = BASE_DIR / "checkpoints_simple"

# Nombre del workflow: hace falta para poder listar sus checkpoints al final
# (MIGRACIÓN 1.11.0: `list_checkpoints()` ahora exige `workflow_name`).
WORKFLOW_NAME = "facturacion_interactiva"


# ====== Tipos de petición y de estado ======

@dataclass
class TaxConfirmationRequest:
    """Petición que viaja al humano para confirmar el impuesto."""
    invoice_id: str
    question: str
    current_value: float
    options: str


@dataclass
class DiscountConfirmationRequest:
    """Petición que viaja al humano para confirmar el descuento."""
    invoice_id: str
    question: str
    current_value: float
    options: str


@dataclass
class InvoiceState:
    """Estado de la factura mientras recorre el workflow.

    Viaja de ejecutor en ejecutor acumulando las decisiones del humano. Todos los
    importes salen de la factura REAL seleccionada: no hay valores fijos.
    """
    invoice_id: str
    client_name: str
    subtotal: float
    tax_rate: float
    tax_amount: float
    discount_amount: float
    tax_confirmed: bool = False
    discount_confirmed: bool = False
    processing_stage: str = "preparation"


# ====== Ejecutores del workflow ======

# PASO 1 — ENTRADA del grafo. Convierte la factura elegida en el InvoiceState que
# recorrerá el resto del workflow. Aún no pregunta nada al humano.
class InvoicePreparation(Executor):
    """Prepara los datos de la factura para su aprobación."""

    @handler
    async def prepare(self, invoice_data: InvoiceData, ctx: WorkflowContext[InvoiceState]) -> None:
        """Calcula importes reales y construye el estado inicial."""
        print("\n" + "="*80)
        print("PASO 1: PREPARAR FACTURA")
        print("="*80)

        config = InvoiceConfig()
        totals = calculate_invoice_totals(invoice_data, config)

        # Los dos descuentos posibles se suman en uno solo para la confirmación
        discount_amount = totals['high_value_discount'] + totals['preferred_discount']

        state = InvoiceState(
            invoice_id=invoice_data.invoice_id,
            client_name=invoice_data.client_name,
            subtotal=invoice_data.subtotal,
            tax_rate=config.tax_rate,
            tax_amount=totals['tax'],
            discount_amount=discount_amount,
            processing_stage="preparation",
        )

        print(f"Factura seleccionada: {state.invoice_id}")
        print(f"   Cliente: {state.client_name}")
        print(f"   Importe: ${state.subtotal:.2f}")
        print(f"   Tasa de impuesto: {state.tax_rate * 100:g}%")
        print(f"   Impuesto calculado: ${state.tax_amount:.2f}")
        print(f"   Descuento aplicable: ${state.discount_amount:.2f}")

        # set_state() guarda datos DENTRO del checkpoint, por CLAVE.
        # MIGRACIÓN 1.11.0: la firma es `set_state(clave, valor)`, ya no acepta un
        # dict completo. Y `set_shared_state`/`get_shared_state` NO existen: el
        # estado que deba viajar entre pasos va en el propio mensaje.
        ctx.set_state("step", "preparation")
        ctx.set_state("invoice_id", state.invoice_id)

        await ctx.send_message(state)


# PASO 2 — PRIMERA PAUSA. Pregunta al humano y, cuando responde, aplica su
# decisión. Preguntar y procesar viven en la MISMA clase gracias a
# @response_handler; antes hacían falta dos ejecutores encadenados.
class TaxConfirmation(Executor):
    """Pide confirmación del impuesto y aplica la respuesta del humano."""

    @handler
    async def request_tax_confirmation(self, state: InvoiceState, ctx: WorkflowContext) -> None:
        """Detiene el workflow y pide al humano que confirme el impuesto."""
        print("\n" + "="*80)
        print("PASO 2: CONFIRMAR IMPUESTO")
        print("="*80)
        print(f"Factura: {state.invoice_id}")
        print(f"   Subtotal: ${state.subtotal:.2f}")
        print(f"   Tasa de impuesto: {state.tax_rate * 100:g}%")
        print(f"   Impuesto calculado: ${state.tax_amount:.2f}")
        print(f"\n>> El workflow se DETIENE aquí hasta recibir su respuesta...")

        ctx.set_state("step", "tax_request")
        ctx.set_state("invoice_id", state.invoice_id)

        # El estado del ejecutor se guarda para poder reconstruirlo al responder:
        # el response_handler solo recibe la petición y la respuesta, no el mensaje
        # original que entró por el @handler.
        self._state = state

        # request_info() PAUSA el workflow y emite un evento type="request_info".
        # El segundo argumento es el TIPO esperado de respuesta (aquí, bool).
        await ctx.request_info(
            TaxConfirmationRequest(
                invoice_id=state.invoice_id,
                question=f"¿Confirma el cálculo del impuesto de {state.invoice_id}?",
                current_value=state.tax_amount,
                options="Escriba 's' para confirmar o 'n' para omitirlo",
            ),
            bool,
        )

    @response_handler
    async def apply_tax_response(
        self,
        original_request: TaxConfirmationRequest,
        response: bool,
        ctx: WorkflowContext[InvoiceState],
    ) -> None:
        """Recibe la decisión del humano y la aplica al estado."""
        print("\n" + "="*80)
        print("PASO 3: APLICAR DECISION SOBRE EL IMPUESTO")
        print("="*80)

        # `original_request` es la petición que se envió: el framework la devuelve
        # emparejada con su respuesta, así se sabe SIEMPRE a qué se contesta.
        print(f"Respondiendo a: {original_request.question}")

        state = self._state
        state.tax_confirmed = response
        state.processing_stage = "tax_processed"

        # La respuesta MANDA: si se rechaza, el impuesto se pone a cero
        if response:
            print(f"Impuesto CONFIRMADO: ${state.tax_amount:.2f}")
        else:
            print(f"Impuesto OMITIDO (no se sumará al total)")
            state.tax_amount = 0.0

        ctx.set_state("step", "tax_processed")
        ctx.set_state("tax_confirmed", state.tax_confirmed)

        await ctx.send_message(state)


# PASO 4 — SEGUNDA PAUSA. Igual que la anterior, pero con un atajo: si la factura
# no tiene descuento aplicable, NO molesta al humano y sigue de largo.
class DiscountConfirmation(Executor):
    """Pide confirmación del descuento y aplica la respuesta del humano."""

    @handler
    async def request_discount_confirmation(self, state: InvoiceState, ctx: WorkflowContext[InvoiceState]) -> None:
        """Pide confirmación del descuento, salvo que no haya ninguno que aplicar."""
        print("\n" + "="*80)
        print("PASO 4: CONFIRMAR DESCUENTO")
        print("="*80)

        # Atajo: sin descuento no hay nada que preguntar. El workflow NO se detiene
        # y el mensaje pasa directo al siguiente paso.
        if state.discount_amount <= 0:
            print(f"La factura {state.invoice_id} no tiene descuento aplicable.")
            print("No se solicita confirmación: se continúa directamente.")
            state.discount_confirmed = False
            state.processing_stage = "discount_skipped"
            await ctx.send_message(state)
            return

        print(f"Factura: {state.invoice_id}")
        print(f"   Descuento total: ${state.discount_amount:.2f}")
        print(f"\n>> El workflow se DETIENE aquí hasta recibir su respuesta...")

        ctx.set_state("step", "discount_request")

        self._state = state

        await ctx.request_info(
            DiscountConfirmationRequest(
                invoice_id=state.invoice_id,
                question=f"¿Aplica el descuento a {state.invoice_id}?",
                current_value=state.discount_amount,
                options="Escriba 's' para aplicarlo o 'n' para omitirlo",
            ),
            bool,
        )

    @response_handler
    async def apply_discount_response(
        self,
        original_request: DiscountConfirmationRequest,
        response: bool,
        ctx: WorkflowContext[InvoiceState],
    ) -> None:
        """Recibe la decisión del humano y la aplica al estado."""
        print("\n" + "="*80)
        print("PASO 5: APLICAR DECISION SOBRE EL DESCUENTO")
        print("="*80)

        print(f"Respondiendo a: {original_request.question}")

        state = self._state
        state.discount_confirmed = response
        state.processing_stage = "discount_processed"

        if response:
            print(f"Descuento APLICADO: ${state.discount_amount:.2f}")
        else:
            print(f"Descuento OMITIDO (no se restará del total)")
            state.discount_amount = 0.0

        ctx.set_state("step", "discount_processed")
        ctx.set_state("discount_confirmed", state.discount_confirmed)

        await ctx.send_message(state)


# PASO 6 — TERMINAL del grafo. Calcula el total según lo que decidió el humano y
# guarda el archivo. `WorkflowContext[Never, str]`: no envía nada y PRODUCE la
# salida del workflow con ctx.yield_output().
class InvoiceFinalizer(Executor):
    """Calcula el total definitivo y guarda la factura."""

    @handler
    async def finalize(self, state: InvoiceState, ctx: WorkflowContext[Never, str]) -> None:
        """Aplica las decisiones humanas al total y escribe el archivo."""
        print("\n" + "="*80)
        print("PASO 6: FINALIZAR FACTURA")
        print("="*80)

        # AQUÍ SE VE EL EFECTO DEL HUMANO: cada importe se suma o resta solo si
        # fue confirmado.
        final_total = state.subtotal
        if state.tax_confirmed:
            final_total += state.tax_amount
        if state.discount_confirmed:
            final_total -= state.discount_amount

        print(f"Factura: {state.invoice_id}")
        print(f"   Cliente: {state.client_name}")
        print(f"   Subtotal: ${state.subtotal:.2f}")
        print(f"   Impuesto: {'$%.2f' % state.tax_amount if state.tax_confirmed else 'OMITIDO'}")
        print(f"   Descuento: {'-$%.2f' % state.discount_amount if state.discount_confirmed else 'OMITIDO'}")
        print(f"   TOTAL FINAL: ${final_total:.2f}")

        ensure_directories(str(OUTPUT_DIR))
        output_file = OUTPUT_DIR / f"{state.invoice_id}_final.txt"

        # El documento deja constancia de QUÉ decidió el humano, no solo del total
        lineas = [
            f"FACTURA: {state.invoice_id}",
            f"Cliente: {state.client_name}",
            f"Subtotal: ${state.subtotal:.2f}",
            f"Impuesto: {'$%.2f' % state.tax_amount if state.tax_confirmed else 'OMITIDO por el usuario'}",
            f"Descuento: {'-$%.2f' % state.discount_amount if state.discount_confirmed else 'OMITIDO por el usuario'}",
            f"TOTAL FINAL: ${final_total:.2f}",
            f"Estado: Completada con confirmaciones del usuario",
        ]
        output_file.write_text("\n".join(lineas) + "\n", encoding="utf-8")

        print(f"Archivo generado: {output_file}")

        ctx.set_state("step", "completed")
        ctx.set_state("final_total", final_total)

        log_action(
            f"Factura {state.invoice_id} finalizada por ${final_total:.2f} "
            f"(impuesto={'si' if state.tax_confirmed else 'no'}, "
            f"descuento={'si' if state.discount_confirmed else 'no'})",
            str(LOGS_DIR),
        )

        await ctx.yield_output(
            f"¡Factura {state.invoice_id} completada con las confirmaciones del usuario! "
            f"Total final: ${final_total:.2f}"
        )


# ====== Interacción con el humano ======

def preguntar_al_humano(request) -> bool:
    """Muestra la petición del workflow por consola y devuelve la decisión.

    Devuelve un `bool` porque es el `response_type` declarado en `request_info()`;
    el framework valida que el tipo coincida.
    """
    print("\n" + "-"*80)
    print("SE REQUIERE SU CONFIRMACION")
    print("-"*80)
    print(f"   {request.question}")
    print(f"   Valor actual: ${request.current_value:.2f}")
    print(f"   {request.options}")

    while True:
        respuesta = input("   Su respuesta (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            return True
        if respuesta in ("n", "no"):
            return False
        print("   Responda 's' o 'n'.")


async def run_interactive_workflow(workflow, selected_invoice: InvoiceData):
    """Ejecuta el ciclo completo PAUSA → RESPUESTA → REANUDACIÓN.

    Este bucle es el corazón de la demo:
      1. Se arranca el workflow con la factura.
      2. Si emite peticiones (`type == "request_info"`), se guarda su request_id.
      3. Se pregunta al humano por cada una.
      4. Se reanuda con `run(responses={...})` — SIN volver a pasar el mensaje.
      5. Se repite hasta que el workflow produzca su salida final.
    """
    print("\n" + "="*80)
    print("WORKFLOW INTERACTIVO DE APROBACION DE FACTURAS")
    print("="*80)
    print("Esta demo combina:")
    print("  - Interacción humana REAL (el workflow se detiene de verdad)")
    print("  - Checkpointing automático en cada pausa")
    print("  - Correlación petición/respuesta mediante request_id y tipos")
    print("="*80)

    # Primera ejecución: se pasa la factura como mensaje inicial
    pendientes: dict[str, object] = {}
    estado_final = None
    salida = None

    event: WorkflowEvent
    async for event in workflow.run(selected_invoice, stream=True):
        if event.type == "request_info":
            pendientes[event.request_id] = event.data
        elif event.type == "output":
            salida = event.data
        elif event.type == "status":
            estado_final = event.state

    # Mientras el workflow siga esperando respuestas, se atienden y se reanuda
    vuelta = 0
    while pendientes and salida is None:
        vuelta += 1

        # Comprobación explícita del estado: IDLE_WITH_PENDING_REQUESTS es la
        # prueba de que el motor se detuvo de verdad esperando al humano.
        en_pausa = estado_final == WorkflowRunState.IDLE_WITH_PENDING_REQUESTS
        print(f"\n(estado del workflow: {estado_final}"
              f"{' -> detenido esperando al humano' if en_pausa else ''})")

        # Se responde a TODAS las peticiones pendientes, indexadas por request_id
        respuestas = {rid: preguntar_al_humano(req) for rid, req in pendientes.items()}
        pendientes = {}

        print(f"\n>> Reanudando el workflow con {len(respuestas)} respuesta(s)...")

        # REANUDACIÓN: se pasan `responses`, NUNCA el mensaje inicial otra vez
        # (`message` y `responses` son mutuamente excluyentes).
        async for event in workflow.run(responses=respuestas, stream=True):
            if event.type == "request_info":
                pendientes[event.request_id] = event.data
            elif event.type == "output":
                salida = event.data
            elif event.type == "status":
                estado_final = event.state

    if salida is not None:
        print("\n" + "="*80)
        print("WORKFLOW COMPLETADO")
        print("="*80)
        print(salida)
        print(f"Pausas atendidas: {vuelta}")
        print("="*80)
    else:
        print("\nEl workflow terminó sin producir salida final.")


# ====== Funciones auxiliares ======

def show_invoice_menu(invoices: list[InvoiceData]) -> InvoiceData:
    """Muestra el menú de facturas y devuelve la elegida (el objeto, no el ID)."""
    print("\n" + "="*80)
    print("FACTURAS DISPONIBLES")
    print("="*80)

    for idx, inv in enumerate(invoices, 1):
        preferred_badge = "*" if inv.is_preferred else " "
        print(f"{idx}. {preferred_badge} {inv.invoice_id} - {inv.client_name}")
        print(f"   Importe: ${inv.subtotal:.2f} | Fecha: {inv.date}")
        print()

    while True:
        try:
            choice = input(f"Seleccione una factura (1-{len(invoices)}): ").strip()
            idx = int(choice)
            if 1 <= idx <= len(invoices):
                return invoices[idx - 1]
            else:
                print(f"Introduzca un número entre 1 y {len(invoices)}")
        except ValueError:
            print("Introduzca un número válido")


# ====== Punto de entrada ======

async def main():
    """Punto de entrada del workflow interactivo de aprobación."""
    ensure_directories(str(OUTPUT_DIR), str(LOGS_DIR), str(CHECKPOINTS_DIR))

    # Almacenamiento de checkpoints EN DISCO: sobrevive al fin del proceso.
    #
    # ⚠️ SEGURIDAD (novedad de 1.11.0): el estado se serializa con pickle, y al
    # LEERLO el framework solo admite una lista blanca de tipos (primitivos,
    # datetime, uuid y los propios de agent_framework). Los tipos PROPIOS hay que
    # declararlos en `allowed_checkpoint_types` con formato "modulo:ClaseQualname".
    #
    # Sin esta lista los checkpoints SE ESCRIBEN pero NO SE PUEDEN LEER: fallan
    # con "Checkpoint deserialization blocked for type ...", de modo que se
    # perdería justo la capacidad de reanudar que se quiere demostrar.
    modulo = __name__   # "__main__" al ejecutar el archivo directamente
    checkpoint_storage = FileCheckpointStorage(
        storage_path=str(CHECKPOINTS_DIR),
        allowed_checkpoint_types=[
            f"{modulo}:InvoiceState",
            f"{modulo}:TaxConfirmationRequest",
            f"{modulo}:DiscountConfirmationRequest",
        ],
    )

    csv_path = DATA_DIR / "invoices.csv"
    print(f"\nLeyendo facturas de: {csv_path}")
    all_invoices = read_invoices_csv(str(csv_path))
    print(f"Se cargaron {len(all_invoices)} facturas")

    selected_invoice = show_invoice_menu(all_invoices)

    log_action(
        f"Factura {selected_invoice.invoice_id} seleccionada para aprobación interactiva",
        str(LOGS_DIR),
    )

    # Se instancian los ejecutores; el id es el nombre que aparece en los eventos
    preparer = InvoicePreparation(id="preparer")
    tax_step = TaxConfirmation(id="tax_confirmation")
    discount_step = DiscountConfirmation(id="discount_confirmation")
    finalizer = InvoiceFinalizer(id="finalizer")

    # ------------------------------------------------------------------------
    # CONSTRUCCIÓN DEL GRAFO CON CHECKPOINTING
    # ------------------------------------------------------------------------
    # MIGRACIÓN 1.11.0:
    #   - `set_start_executor(x)` ELIMINADO  → `WorkflowBuilder(start_executor=x)`
    #   - `.with_checkpointing(storage)` ELIMINADO → `checkpoint_storage=` en el
    #     constructor
    #   - `name=` es necesario para poder listar los checkpoints después
    #
    # El grafo es una cadena simple de 4 ejecutores: las pausas NO son nodos del
    # grafo, ocurren DENTRO de un ejecutor al llamar a request_info().
    workflow = (
        WorkflowBuilder(
            start_executor=preparer,
            output_from=[finalizer],
            checkpoint_storage=checkpoint_storage,
            name=WORKFLOW_NAME,
        )
        .add_edge(preparer, tax_step)
        .add_edge(tax_step, discount_step)
        .add_edge(discount_step, finalizer)
        .build()
    )

    print("\nEstructura del workflow:")
    print("   Preparar -> Confirmar impuesto -> Confirmar descuento -> Finalizar")
    print("   Se guardan checkpoints automáticamente en cada pausa")

    await run_interactive_workflow(workflow, selected_invoice)

    # ------------------------------------------------------------------------
    # RESUMEN DE CHECKPOINTS
    # ------------------------------------------------------------------------
    print("\n" + "="*80)
    print("RESUMEN DE CHECKPOINTS")
    print("="*80)

    try:
        # MIGRACIÓN 1.11.0: `list_checkpoints()` ahora EXIGE `workflow_name`
        all_cps = await checkpoint_storage.list_checkpoints(workflow_name=WORKFLOW_NAME)
        if all_cps:
            print(f"Se crearon {len(all_cps)} checkpoints durante la ejecución")
            print(f"Guardados en: {CHECKPOINTS_DIR}")
            for i, cp in enumerate(all_cps[-3:]):   # solo los 3 últimos
                ts = getattr(cp, "timestamp", "n/d")
                print(f"   [{i}] {str(cp.checkpoint_id)[:16]}... - {ts}")
        else:
            print("No se encontraron checkpoints")
    except Exception as e:
        print(f"No se pudieron listar los checkpoints: {e}")

    print("\nConceptos demostrados:")
    print("   - Interacción humana real con ctx.request_info() + @response_handler")
    print("   - Pausa efectiva del workflow (estado IDLE_WITH_PENDING_REQUESTS)")
    print("   - Reanudación con run(responses={request_id: valor})")
    print("   - Checkpointing automático, incluidas las peticiones pendientes")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
