"""
DEMO 21 — AGENTES DE IA DENTRO DE UN WORKFLOW (Microsoft Agent Framework 1.11.0)
================================================================================

OBJETIVO PEDAGÓGICO
-------------------
Cierre de la serie: hasta ahora los ejecutores hacían cálculo determinista. Aquí
CUATRO de ellos delegan su trabajo en un **agente de IA** distinto, cada uno con
su especialidad. El grafo es el mismo de siempre; lo que cambia es quién decide.

    Selector ─► Analista ─► Decisor ─► Comunicador ─► Resumidor
    (código)     (IA)        (IA)         (IA)          (IA)

⚠️ ESTA DEMO ES DIFERENTE A LAS ANTERIORES
------------------------------------------
Es la ÚNICA de Part-3 que llama a un modelo de verdad. Implica que:
  • Necesita credenciales de Azure AI Foundry y `az login` hecho.
  • Tarda bastante más (son 4 llamadas al modelo, una por agente).
  • Sus respuestas NO son deterministas: dos ejecuciones no dan lo mismo.
  • Consume cuota del modelo.
Las demos 16-20 son cálculo local puro y no necesitan nada de esto.

CONCEPTOS CLAVE
---------------
1. UN AGENTE ES UN EJECUTOR MÁS. No hay una clase especial: un `Executor`
   corriente que, dentro de su `@handler`, llama a `agent.run(prompt)`.

2. UN CLIENTE, VARIOS AGENTES. Se crea UN solo `FoundryChatClient` y se comparte
   entre los cuatro agentes. Lo que los diferencia son sus `instructions`, no la
   conexión.

3. ESPECIALIZACIÓN POR INSTRUCCIONES: analista financiero, decisor de negocio,
   redactor de comunicaciones y resumidor ejecutivo. Mismo modelo, cuatro
   comportamientos.

4. LA SALIDA DE UN AGENTE ALIMENTA AL SIGUIENTE: el análisis condiciona la
   decisión, la decisión condiciona la comunicación, y todo acaba en el resumen.

CONFIGURACIÓN NECESARIA (en `.env03`)
--------------------------------------
    AZURE_AI_PROJECT_ENDPOINT       endpoint del proyecto de Azure AI Foundry
    AZURE_AI_MODEL_DEPLOYMENT_NAME  nombre del despliegue del modelo

Autenticación por `AzureCliCredential`: hay que ejecutar **`az login`** antes.
No se usa API key en esta demo.

Ejecutar (desde el directorio Part-3, con el venv activo):
    az login
    python new_21_agents_in_workflow.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from typing_extensions import Never
from dataclasses import dataclass, field

# MIGRACIÓN 1.11.0: `ChatAgent` y `agent_framework.azure.AzureAIAgentClient` fueron
# ELIMINADOS. Ahora se usa `Agent` (núcleo) + `FoundryChatClient` (paquete
# agent-framework-foundry).
from agent_framework import (
    WorkflowBuilder, WorkflowContext, WorkflowEvent,
    Executor, handler, Agent
)
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import AzureCliCredential

# Import our utilities
import sys
sys.path.append(str(Path(__file__).parent))
from invoice_utils import (
    InvoiceConfig, InvoiceData, read_invoices_csv, calculate_invoice_totals,
    save_invoice_file, log_action, ensure_directories, print_step
)

# Load environment
# Las variables de Foundry viven en .env03 junto a las de Azure OpenAI
# (antes esta demo cargaba `.env01`, un archivo que NO existe en Part-3).
load_dotenv('.env03', override=True)

# Directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Azure AI configuration
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")


# ============================================================================
# MENSAJES QUE VIAJAN POR EL GRAFO
# ============================================================================
# Las demos anteriores encadenaban tuplas cada vez más largas
# (`tuple[InvoiceData, dict, str, str]`), difíciles de leer y de ampliar. Aquí se
# usa UN dataclass que va acumulando el trabajo de cada agente.

@dataclass
class ExpedienteFactura:
    """Expediente que recorre el workflow acumulando lo que aporta cada agente."""
    invoice: InvoiceData
    totals: dict
    analisis: str = ""            # lo escribe el Analista
    nivel_riesgo: str = "medio"   # se deduce del análisis
    decision: str = ""            # lo escribe el Decisor
    via_procesamiento: str = ""   # se deduce de la decisión
    comunicacion: str = ""        # lo escribe el Comunicador
    resumen: str = ""             # lo escribe el Resumidor


# ============================================================================
# INSTRUCCIONES DE CADA AGENTE
# ============================================================================
# Lo ÚNICO que distingue a los cuatro agentes. Todas piden responder EN ESPAÑOL:
# sin esa indicación el modelo tiende a contestar en inglés.

INSTRUCCIONES_ANALISTA = """Eres un analista financiero experto en facturación.
Analiza los datos de la factura y aporta:
1. Observaciones de negocio sobre el cliente y la operación
2. Evaluación de riesgo (bajo / medio / alto)
3. Recomendaciones para su procesamiento
4. Cualquier patrón inusual o motivo de preocupación

Responde SIEMPRE en español, de forma concisa y estructurada."""

INSTRUCCIONES_DECISOR = """Eres un responsable de decisiones de negocio en facturación.
Según los datos y el análisis recibido, decide la acción a tomar:

1. APROBAR   : procesamiento estándar
2. PRIORIDAD : procesamiento acelerado
3. REVISAR   : requiere revisión manual
4. RETENER   : retener temporalmente el procesamiento

Ten en cuenta: categoría del cliente, importe, nivel de riesgo y reglas de negocio.
Empieza tu respuesta con la palabra de la acción elegida en MAYÚSCULAS y explica
brevemente el motivo. Responde SIEMPRE en español."""

INSTRUCCIONES_COMUNICADOR = """Eres un especialista en comunicación con clientes.
Redactas mensajes profesionales y cercanos: acuses de recibo de facturas, avisos
de pago, agradecimientos y ofertas para clientes preferentes.

Ajusta el tono a la relación con el cliente. Responde SIEMPRE en español, de
forma breve y profesional."""

INSTRUCCIONES_RESUMIDOR = """Eres un asistente de dirección que redacta resúmenes ejecutivos.
Incluye:
1. Datos clave de la operación
2. Decisiones de negocio tomadas
3. Observaciones sobre el cliente
4. Próximos pasos o recomendaciones

Responde SIEMPRE en español, en tono profesional y accionable."""


# ============================================================================
# EJECUTORES
# ============================================================================

# PASO 1 — ENTRADA del grafo. Ejecutor TRADICIONAL: no usa IA, solo lee el CSV y
# deja elegir la factura. Se incluye a propósito para dejar claro que agentes y
# código determinista conviven en el mismo grafo.
class InvoiceSelector(Executor):
    """Carga las facturas y deja que el usuario elija una (sin IA)."""

    @handler
    async def select_invoice(self, start_signal: str, ctx: WorkflowContext[ExpedienteFactura]) -> None:
        """Lee el CSV, muestra el menú y crea el expediente inicial."""
        print_step(1, "SELECCIONAR FACTURA")

        # Los directorios se crean aquí: este paso ya escribe en logs/
        ensure_directories(str(OUTPUT_DIR), str(LOGS_DIR))

        config = InvoiceConfig()
        invoices = read_invoices_csv(str(DATA_DIR / "invoices.csv"))
        print(f"Se cargaron {len(invoices)} facturas")

        invoice = mostrar_menu(invoices)
        totals = calculate_invoice_totals(invoice, config)

        print(f"\nSeleccionada: {invoice.invoice_id} - {invoice.client_name}")
        print(f"   Importe: ${invoice.subtotal:.2f}")
        print(f"   Total con impuestos y descuentos: ${totals['total']:.2f}")
        print(f"   Cliente preferente: {'SI' if invoice.is_preferred else 'NO'}")

        log_action(f"Factura {invoice.invoice_id} seleccionada para proceso con agentes", str(LOGS_DIR))

        await ctx.send_message(ExpedienteFactura(invoice=invoice, totals=totals))


# CLASE BASE de los cuatro ejecutores con IA.
# Todos hacen lo mismo: construir un prompt, llamar al agente y guardar el texto.
# Lo único que cambia son las instrucciones y el prompt, así que se factoriza aquí
# para no repetir cuatro veces la misma fontanería.
class AgenteEjecutor(Executor):
    """Base de los ejecutores que delegan su trabajo en un agente de IA."""

    def __init__(self, id: str, client: FoundryChatClient, nombre: str, instrucciones: str):
        super().__init__(id=id)
        # El agente se crea UNA vez y se reutiliza en cada invocación del ejecutor.
        # Todos los agentes comparten el MISMO cliente: lo que los diferencia son
        # sus instrucciones.
        self._agente = Agent(client, name=nombre, instructions=instrucciones)
        self._nombre = nombre

    async def _preguntar(self, prompt: str) -> str:
        """Llama al agente y devuelve su respuesta en texto."""
        print(f"🤖 Agente '{self._nombre}' trabajando...")
        resultado = await self._agente.run(prompt)
        return resultado.text

    @staticmethod
    def _mostrar(titulo: str, texto: str):
        """Imprime la respuesta del agente enmarcada, para que se lea bien."""
        print(f"\n{titulo}")
        print("─" * 80)
        print(texto)
        print("─" * 80)


# PASO 2 — PRIMER AGENTE: analiza la factura y evalúa el riesgo.
class InvoiceAnalyzerAgent(AgenteEjecutor):
    """Agente que analiza la factura y aporta observaciones de negocio."""

    @handler
    async def analyze_invoice(self, exp: ExpedienteFactura, ctx: WorkflowContext[ExpedienteFactura]) -> None:
        """Pide al agente un análisis y deduce de él el nivel de riesgo."""
        print_step(2, "ANALISIS POR AGENTE")

        config = InvoiceConfig()
        inv, t = exp.invoice, exp.totals

        prompt = f"""Analiza esta factura:

Factura: {inv.invoice_id}
Cliente: {inv.client_name} ({inv.client_email})
Concepto: {inv.item_description}
Cantidad: {inv.quantity}
Precio unitario: ${inv.unit_price:.2f}
Subtotal: ${inv.subtotal:.2f}
Cliente preferente: {'Si' if inv.is_preferred else 'No'}
Fecha: {inv.date}

Importes calculados:
- Descuento por alto valor: ${t['high_value_discount']:.2f}
- Descuento cliente preferente: ${t['preferred_discount']:.2f}
- Impuesto: ${t['tax']:.2f}
- Total a pagar: ${t['total']:.2f}

Reglas de negocio:
- Umbral de alto valor: ${config.high_value_threshold:.2f}
- Tasa de impuesto: {config.tax_rate * 100:g}%
- Descuento por alto valor: {config.high_value_discount * 100:g}%
- Descuento cliente preferente: {config.preferred_client_discount * 100:g}%

Entrega tu análisis de forma estructurada."""

        exp.analisis = await self._preguntar(prompt)
        self._mostrar("📊 Análisis del agente:", exp.analisis)

        # Se extrae una etiqueta de riesgo del texto libre para que el resto del
        # workflow pueda usarla. Es deliberadamente simple: el objetivo es mostrar
        # cómo se aterriza una respuesta de IA a un valor manejable por el código.
        texto = exp.analisis.lower()
        if "riesgo alto" in texto or "alto riesgo" in texto:
            exp.nivel_riesgo = "alto"
        elif "riesgo bajo" in texto or "bajo riesgo" in texto:
            exp.nivel_riesgo = "bajo"
        else:
            exp.nivel_riesgo = "medio"

        print(f"\n   Nivel de riesgo detectado: {exp.nivel_riesgo.upper()}")
        log_action(f"Agente analizó {inv.invoice_id}: riesgo={exp.nivel_riesgo}", str(LOGS_DIR))

        await ctx.send_message(exp)


# PASO 3 — SEGUNDO AGENTE: decide qué hacer con la factura.
class DecisionAgent(AgenteEjecutor):
    """Agente que decide la vía de procesamiento de la factura."""

    @handler
    async def make_decision(self, exp: ExpedienteFactura, ctx: WorkflowContext[ExpedienteFactura]) -> None:
        """Pide una decisión al agente y la traduce a una vía de procesamiento."""
        print_step(3, "DECISION POR AGENTE")

        config = InvoiceConfig()
        inv = exp.invoice

        # El prompt incluye el ANÁLISIS del agente anterior: así se encadena el
        # trabajo de un agente con el siguiente.
        prompt = f"""Decide cómo procesar esta factura:

Factura: {inv.invoice_id}
Cliente: {inv.client_name} (preferente: {'Si' if inv.is_preferred else 'No'})
Importe total: ${exp.totals['total']:.2f}
Nivel de riesgo: {exp.nivel_riesgo}

Análisis previo del analista:
{exp.analisis[:600]}

Reglas de negocio:
- Umbral de alto valor: ${config.high_value_threshold:.2f}
- Los clientes preferentes tienen prioridad
- Un riesgo alto exige revisión manual

Elige entre: APROBAR, PRIORIDAD, REVISAR o RETENER, y justifica brevemente."""

        exp.decision = await self._preguntar(prompt)
        self._mostrar("⚖️  Decisión del agente:", exp.decision)

        # Se busca la palabra clave en el texto para elegir la vía. El orden
        # importa: se comprueban primero las más específicas.
        texto = exp.decision.upper()
        if "PRIORIDAD" in texto:
            exp.via_procesamiento = "prioridad"
        elif "REVISAR" in texto:
            exp.via_procesamiento = "revision"
        elif "RETENER" in texto:
            exp.via_procesamiento = "retenida"
        else:
            exp.via_procesamiento = "estandar"

        print(f"\n   Vía de procesamiento: {exp.via_procesamiento.upper()}")
        log_action(f"Agente decidió vía '{exp.via_procesamiento}' para {inv.invoice_id}", str(LOGS_DIR))

        await ctx.send_message(exp)


# PASO 4 — TERCER AGENTE: redacta el mensaje para el cliente.
class CommunicationAgent(AgenteEjecutor):
    """Agente que redacta la comunicación personalizada al cliente."""

    @handler
    async def generate_communication(self, exp: ExpedienteFactura, ctx: WorkflowContext[ExpedienteFactura]) -> None:
        """Pide al agente un correo de acuse de recibo para el cliente."""
        print_step(4, "COMUNICACION POR AGENTE")

        inv = exp.invoice

        prompt = f"""Redacta un correo de acuse de recibo para este cliente:

Datos del cliente:
- Nombre: {inv.client_name}
- Email: {inv.client_email}
- Cliente preferente: {'Si' if inv.is_preferred else 'No'}

Datos de la factura:
- Factura: {inv.invoice_id}
- Concepto: {inv.item_description}
- Importe: ${exp.totals['total']:.2f}
- Fecha: {inv.date}
- Vía de procesamiento decidida: {exp.via_procesamiento}

Incluye: saludo personalizado, resumen de la factura, cualquier nota especial
según su categoría y la decisión tomada, y una despedida profesional.
Que sea breve y cercano."""

        exp.comunicacion = await self._preguntar(prompt)
        self._mostrar("📧 Comunicación generada:", exp.comunicacion)

        log_action(f"Agente generó comunicación para {inv.invoice_id}", str(LOGS_DIR))

        await ctx.send_message(exp)


# PASO 5 — CUARTO AGENTE y TERMINAL del grafo. Resume todo y guarda el informe.
# `WorkflowContext[Never, str]`: no envía nada y PRODUCE la salida del workflow.
class SummaryAgent(AgenteEjecutor):
    """Agente que redacta el resumen ejecutivo y cierra el workflow."""

    @handler
    async def create_summary(self, exp: ExpedienteFactura, ctx: WorkflowContext[Never, str]) -> None:
        """Pide el resumen ejecutivo, guarda el informe completo y termina."""
        print_step(5, "RESUMEN EJECUTIVO POR AGENTE")

        inv = exp.invoice

        prompt = f"""Redacta un resumen ejecutivo del procesamiento de esta factura:

Factura: {inv.invoice_id}
Cliente: {inv.client_name}
Importe total: ${exp.totals['total']:.2f}
Vía de procesamiento: {exp.via_procesamiento}
Nivel de riesgo: {exp.nivel_riesgo}

Análisis del analista:
{exp.analisis[:400]}

Decisión tomada:
{exp.decision[:400]}

Se generó además una comunicación para el cliente.

Destaca los puntos clave y los resultados."""

        exp.resumen = await self._preguntar(prompt)
        self._mostrar("📋 Resumen ejecutivo:", exp.resumen)

        # El informe reúne el trabajo de los CUATRO agentes en un solo documento
        informe = f"""
RESUMEN EJECUTIVO - FACTURA {inv.invoice_id}
{'='*80}

DATOS DEL CLIENTE:
- Nombre: {inv.client_name}
- Email: {inv.client_email}
- Cliente preferente: {'Si' if inv.is_preferred else 'No'}

DATOS ECONOMICOS:
- Subtotal: ${exp.totals['subtotal']:.2f}
- Total a pagar: ${exp.totals['total']:.2f}
- Via de procesamiento: {exp.via_procesamiento}
- Nivel de riesgo: {exp.nivel_riesgo}

ANALISIS DEL AGENTE:
{exp.analisis}

DECISION DEL AGENTE:
{exp.decision}

COMUNICACION AL CLIENTE:
{exp.comunicacion}

RESUMEN EJECUTIVO:
{exp.resumen}

{'='*80}
"""

        filepath = save_invoice_file(f"{inv.invoice_id}_informe_agentes", informe, str(OUTPUT_DIR))
        print(f"\n💾 Informe guardado en: {filepath}")

        log_action(f"Workflow con agentes completado para {inv.invoice_id}", str(LOGS_DIR))

        await ctx.yield_output(
            f"✅ ¡Workflow con agentes completado! Factura {inv.invoice_id} procesada con IA "
            f"(vía: {exp.via_procesamiento}, riesgo: {exp.nivel_riesgo})."
        )


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def mostrar_menu(invoices: list[InvoiceData]) -> InvoiceData:
    """Muestra el menú de facturas y devuelve la elegida."""
    print("\n" + "="*80)
    print("FACTURAS DISPONIBLES")
    print("="*80)

    for idx, inv in enumerate(invoices, 1):
        insignia = "PREFERENTE" if inv.is_preferred else "ESTANDAR  "
        print(f"{idx}. {insignia} {inv.invoice_id} - {inv.client_name}")
        print(f"   Importe: ${inv.subtotal:.2f} | Fecha: {inv.date}")
        print()

    while True:
        try:
            eleccion = input(f"Seleccione una factura (1-{len(invoices)}): ").strip()
            idx = int(eleccion)
            if 1 <= idx <= len(invoices):
                return invoices[idx - 1]
            print(f"Introduzca un número entre 1 y {len(invoices)}")
        except ValueError:
            print("Introduzca un número válido")


# ============================================================================
# WORKFLOW PRINCIPAL
# ============================================================================

async def run_agent_workflow(client: FoundryChatClient):
    """Construye y ejecuta el workflow con agentes integrados."""

    # Se instancian los ejecutores. Los cuatro agentes COMPARTEN el mismo cliente
    # y se distinguen solo por sus instrucciones.
    selector = InvoiceSelector(id="selector")
    analyzer = InvoiceAnalyzerAgent("analista", client, "Analista", INSTRUCCIONES_ANALISTA)
    decider = DecisionAgent("decisor", client, "Decisor", INSTRUCCIONES_DECISOR)
    communicator = CommunicationAgent("comunicador", client, "Comunicador", INSTRUCCIONES_COMUNICADOR)
    summarizer = SummaryAgent("resumidor", client, "Resumidor", INSTRUCCIONES_RESUMIDOR)

    # ------------------------------------------------------------------------
    # CONSTRUCCIÓN DEL GRAFO
    # ------------------------------------------------------------------------
    # MIGRACIÓN 1.11.0: `set_start_executor(x)` fue ELIMINADO → argumento del
    # constructor. `output_from=[...]` evita el DeprecationWarning.
    #
    # La topología es una CADENA LINEAL idéntica a la de la demo 16: meter
    # agentes en un workflow no cambia cómo se construye el grafo.
    workflow = (
        WorkflowBuilder(
            start_executor=selector,
            output_from=[summarizer],
            name="facturacion_con_agentes",
        )
        .add_edge(selector, analyzer)
        .add_edge(analyzer, decider)
        .add_edge(decider, communicator)
        .add_edge(communicator, summarizer)
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
            print("🎉 WORKFLOW CON AGENTES COMPLETADO")
            print("="*80)
            print(event.data)
            print("\n📁 Revise los siguientes directorios:")
            print(f"   • Salida: {OUTPUT_DIR}")
            print(f"   • Registros: {LOGS_DIR}")
            print("\n🤖 Este workflow usó agentes de IA para:")
            print("   • Analizar la factura y evaluar el riesgo")
            print("   • Decidir la vía de procesamiento")
            print("   • Redactar la comunicación al cliente")
            print("   • Elaborar el resumen ejecutivo")
            print("="*80)
        elif event.type == "failed":
            print("\n❌ El workflow falló:")
            print(f"   {event.details}")


async def main():
    """Punto de entrada de la demo."""

    print("\n" + "="*80)
    print("🤖 AGENTES DENTRO DE WORKFLOWS - GENERADOR DE FACTURAS")
    print("="*80)
    print("\n✨ Esta demo integra AGENTES DE IA en los pasos del workflow:")
    print("   • Un agente analiza la factura y evalúa el riesgo")
    print("   • Un agente decide cómo procesarla")
    print("   • Un agente redacta la comunicación al cliente")
    print("   • Un agente elabora el resumen ejecutivo")
    print("\n🔄 Patrón del workflow:")
    print("   Seleccionar → Analizar → Decidir → Comunicar → Resumir")
    print("     (código)      (IA)      (IA)       (IA)       (IA)")
    print("\n⚠️  A diferencia de las demos 16-20, esta SÍ llama a un modelo real:")
    print("   requiere credenciales, tarda más y sus respuestas varían en cada ejecución.")
    print("="*80)

    # Comprobación de configuración ANTES de intentar conectarse: así el error es
    # claro en vez de un fallo de autenticación críptico.
    if not PROJECT_ENDPOINT or not MODEL_DEPLOYMENT:
        print("\n❌ Falta configuración de Azure AI en .env03")
        print("   Se necesitan: AZURE_AI_PROJECT_ENDPOINT y AZURE_AI_MODEL_DEPLOYMENT_NAME")
        return

    print(f"\n🔗 Proyecto: {PROJECT_ENDPOINT}")
    print(f"🧠 Modelo:   {MODEL_DEPLOYMENT}")

    try:
        # AzureCliCredential SÍ es context manager y hay que cerrarlo.
        # ⚠️ FoundryChatClient NO lo es: se crea y se usa directamente (un
        # `async with` sobre él falla con "missed __aexit__ method").
        async with AzureCliCredential() as credential:
            client = FoundryChatClient(
                project_endpoint=PROJECT_ENDPOINT,
                model=MODEL_DEPLOYMENT,
                credential=credential,
            )
            await run_agent_workflow(client)

    except Exception as e:
        # El fallo más habitual es no haber hecho `az login`
        print(f"\n❌ Error al ejecutar el workflow con agentes: {type(e).__name__}")
        print(f"   {e}")
        print("\n   Comprobaciones:")
        print("   • ¿Ha ejecutado `az login`?")
        print("   • ¿Es correcto AZURE_AI_PROJECT_ENDPOINT en .env03?")
        print("   • ¿Está desplegado el modelo indicado en AZURE_AI_MODEL_DEPLOYMENT_NAME?")
        return

    print("\n" + "="*80)
    print("¡Demo completada! Agentes integrados con éxito en el workflow.")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
