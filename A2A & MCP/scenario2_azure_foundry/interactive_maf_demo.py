"""
================================================================================
ESCENARIO 2 — Agentes en Azure AI Foundry + MCP de Microsoft Learn
================================================================================
Demo interactiva del Microsoft Agent Framework (MFA) que enseña, paso a paso:

  1. Cómo se CREAN tres agentes (Investigación, Ejecutor, Coordinador).
  2. Cómo se pasan MENSAJES A2A (Agent-to-Agent) entre ellos, en directo.
  3. Cómo un agente usa HERRAMIENTAS MCP remotas (Microsoft Learn) y cómo se
     APRUEBA cada llamada antes de que se ejecute (human-in-the-loop).

--------------------------------------------------------------------------------
MAPA DEL FLUJO  (el número de cada comentario del archivo remite a esta tabla;
                 sigue el ORDEN REAL DE EJECUCIÓN, no el orden del archivo)
--------------------------------------------------------------------------------
 [0]   Arranque del módulo ......... UTF-8, .env y silenciado de logs
 [1]   main() ...................... punto de entrada
 [2]   Configuracion.desde_entorno() lee y VALIDA el .env
 [3]   Consola.bienvenida() ........ portada de la demo
 [4]   FabricaDeAgentes ............ crea el ChatClient de Foundry (una sola vez)
 [5]   FASE 1 — creación de agentes
       [5.1] crear_agente_investigacion() .. Agent + herramienta MCP remota
       [5.2] crear_agente_ejecutor() ....... Agent sin herramientas
       [5.3] crear_agente_coordinador() .... Agent que conoce el directorio A2A
 [6]   RedA2A.registrar() .......... da de alta los tres buzones A2A
 [7]   Ficha JSON .................. agents_info_interactive.json
 [8]   FASE 2 — DemostracionA2A.ejecutar()
       [8.1] PASO 1  Usuario ........ → Coordinador
       [8.2] PASO 2  Coordinador .... → Investigación      (A2A)
       [8.3] PASO 3  Investigación .. → MCP Microsoft Learn (con aprobación)
       [8.4] PASO 4  Investigación .. → Coordinador        (A2A)
       [8.5] PASO 5  Coordinador .... → Ejecutor           (A2A)
       [8.6] PASO 6  Ejecutor ....... → Coordinador        (A2A)
       [8.7] PASO 7  Coordinador .... → Usuario            (respuesta final)
 [9]   Cierre ...................... se cierran la sesión MCP y la credencial

--------------------------------------------------------------------------------
CÓMO LEER LOS COMENTARIOS
--------------------------------------------------------------------------------
  ⚙️  MFA    → instrucción propia del Microsoft Agent Framework (la materia)
  🔌 MCP    → relativo al protocolo Model Context Protocol
  📡 A2A    → relativo a la comunicación entre agentes
  🏛️  SOLID  → decisión de diseño orientada a objetos (por qué está así)
  🔧 Infra  → Python/entorno; andamiaje, no forma parte del framework

--------------------------------------------------------------------------------
REQUISITOS
--------------------------------------------------------------------------------
  * `az login` hecho (se autentica con DefaultAzureCredential).
  * .env con AZURE_AI_PROJECT_ENDPOINT y AZURE_OPENAI_DEPLOYMENT_NAME.
  * Ejecutar:  python interactive_maf_demo.py

⚠️  ESTE ESCENARIO LLAMA A MODELOS DE VERDAD: consume cuota y no es determinista.

✅ NOVEDAD FRENTE A LA VERSIÓN ANTERIOR: los agentes son EFÍMEROS. Viven en
   memoria mientras dura la ejecución y NO se registran en el proyecto de Azure
   AI Foundry, así que ya no se acumulan copias en cada ejecución.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# [0] ARRANQUE DEL MÓDULO
# ──────────────────────────────────────────────────────────────────────────────
import asyncio
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

# 🔧 Infra [0.1] La consola de Windows usa cp1252 y revienta con los emojis
#    (UnicodeEncodeError). Hay que forzar UTF-8 antes de imprimir nada.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

# 🔧 Infra [0.2] Ruta ABSOLUTA al .env: si dependiera del directorio de trabajo,
#    lanzar el script desde otra carpeta lo dejaría sin configuración.
#    override=True para que el .env mande sobre variables viejas de la sesión.
DIRECTORIO_BASE = Path(__file__).resolve().parent
load_dotenv(DIRECTORIO_BASE / ".env", override=True)

# 🔧 Infra [0.3] El transporte (httpx, azure, mcp…) es muy hablador y tapa la
#    demo. Se sube el umbral a WARNING para que solo se vea lo importante.
for _biblioteca in ("httpx", "httpcore", "mcp", "openai", "azure", "agent_framework"):
    logging.getLogger(_biblioteca).setLevel(logging.WARNING)

# ⚙️ MFA [0.4] Los tres pilares que usa esta demo:
#    - Agent .................... el agente: modelo + instrucciones + herramientas
#    - MCPStreamableHTTPTool .... cliente MCP sobre HTTP (vive en el CORE de MFA)
#    - FoundryChatClient ........ el "motor": habla con Azure AI Foundry
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import DefaultAzureCredential

# 🔧 Infra [0.5] Constantes de presentación.
ANCHO = 78
URL_MCP_MICROSOFT_LEARN = "https://learn.microsoft.com/api/mcp"
PREGUNTA_POR_DEFECTO = "¿Qué niveles de servicio admiten servidores MCP en Azure API Management?"


def recortar(texto: str, limite: int = 160) -> str:
    """🔧 Infra Deja un texto en una sola línea y lo acorta para que quepa en la caja."""
    limpio = " ".join(str(texto).split())
    return limpio if len(limpio) <= limite else limpio[:limite] + "…"


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 1 — CONFIGURACIÓN
# 🏛️ SOLID (SRP): una única clase se encarga de leer y validar el entorno.
#    Nadie más vuelve a llamar a os.getenv(); el resto del programa recibe un
#    objeto ya validado y no puede arrancar a medio configurar.
# ══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Configuracion:
    """Datos de conexión al proyecto de Azure AI Foundry."""

    endpoint_proyecto: str
    modelo: str
    url_mcp: str = URL_MCP_MICROSOFT_LEARN

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        """[2] Lee el .env, compone lo que falte y falla pronto si algo no está."""
        # [2.1] El endpoint puede venir entero...
        endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")

        # [2.2] ...o componerse a partir del recurso + el nombre del proyecto.
        if not endpoint:
            recurso = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
            proyecto = os.getenv("AZURE_AI_FOUNDRY_PROJECT")
            if recurso and proyecto:
                endpoint = f"{recurso.rstrip('/')}/api/projects/{proyecto}"

        if not endpoint:
            raise ValueError(
                "Falta AZURE_AI_PROJECT_ENDPOINT en el .env "
                "(o bien AZURE_AI_FOUNDRY_ENDPOINT + AZURE_AI_FOUNDRY_PROJECT)."
            )

        # [2.3] ⚠️ Aquí AZURE_OPENAI_DEPLOYMENT_NAME nombra al MODELO DE FOUNDRY,
        #       no a un deployment de Azure OpenAI. El nombre de la variable se
        #       conserva por compatibilidad con el .env del ejercicio original.
        modelo = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not modelo:
            raise ValueError("Falta AZURE_OPENAI_DEPLOYMENT_NAME en el .env.")

        return cls(endpoint_proyecto=endpoint, modelo=modelo)


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 2 — PRESENTACIÓN
# 🏛️ SOLID (SRP + DIP): TODO lo que se imprime vive aquí. Los agentes no llaman
#    a print(): reciben una Consola. Así la lógica multiagente no depende de la
#    interfaz, y cambiar la terminal por una web o por logs no tocaría un solo
#    agente.
# ══════════════════════════════════════════════════════════════════════════════
class Consola:
    """Interfaz de terminal de la demo: cabeceras, pasos, sobres A2A y pausas."""

    def __init__(self, automatica: bool) -> None:
        # 🔧 Infra Modo automático: sin terminal interactiva (por ejemplo, salida
        #    redirigida a un archivo) no se puede pedir input() → se auto-avanza.
        self.automatica = automatica

    # ── Bloques de texto ──────────────────────────────────────────────────────
    def cabecera(self, titulo: str) -> None:
        print("\n" + "=" * ANCHO)
        print(titulo)
        print("=" * ANCHO)

    def paso(self, numero: int, total: int, descripcion: str) -> None:
        print(f"\n[{numero}/{total}] {descripcion}")
        print("-" * ANCHO)

    def info(self, texto: str) -> None:
        print(f"   {texto}")

    def exito(self, texto: str) -> None:
        print(f"\n✅ {texto}")

    def aviso(self, texto: str) -> None:
        print(f"\n⚠️  {texto}")

    def error(self, texto: str) -> None:
        print(f"\n❌ {texto}")

    def fragmento(self, texto: str) -> None:
        """Escribe SIN salto de línea: se usa para la salida en streaming."""
        print(texto, end="", flush=True)

    def salto(self) -> None:
        print()

    # ── El sobre A2A: la caja que enseña el mecanismo ─────────────────────────
    def sobre_a2a(self, mensaje: "MensajeA2A") -> None:
        """
        📡 A2A Dibuja el "sobre" de un mensaje entre agentes.

        Es el elemento didáctico central del escenario: hace VISIBLE algo que
        normalmente ocurre en silencio dentro del programa. Emisor,
        destinatario, tipo y carga útil son exactamente los cuatro campos que
        cualquier protocolo agente-a-agente necesita.
        """
        print("\n" + "▔" * ANCHO)
        print("📨 MENSAJE A2A")
        print("▔" * ANCHO)
        print(f"  De:        {mensaje.emisor}")
        print(f"  Para:      {mensaje.destinatario}")
        print(f"  Tipo:      {mensaje.tipo}")
        print(f"  Enviado:   {mensaje.enviado_en}")
        print(f"  Contenido: {recortar(mensaje.contenido)}")
        print("▔" * ANCHO)

    # ── Interacción ───────────────────────────────────────────────────────────
    def pausa(self, mensaje: str = "Pulsa Enter para continuar…") -> None:
        if self.automatica:
            print(f"\n{mensaje} [modo automático]")
            return
        try:
            input(f"\n{mensaje}")
        except EOFError:
            print(f"\n{mensaje} [sin terminal: continúo]")

    def preguntar(self, mensaje: str, por_defecto: str) -> str:
        if self.automatica:
            print(f"\n{mensaje}")
            print(f"🤔 [modo automático] {por_defecto}")
            return por_defecto
        try:
            respuesta = input(f"\n{mensaje}").strip()
        except EOFError:
            respuesta = ""
        if not respuesta:
            print(f"⚠️  Sin respuesta: uso la pregunta por defecto → {por_defecto}")
            return por_defecto
        return respuesta

    def confirmar(self, mensaje: str) -> bool:
        if self.automatica:
            print(f"{mensaje} [modo automático: SÍ]")
            return True
        try:
            respuesta = input(f"{mensaje} [S/n]: ").strip().lower()
        except EOFError:
            return True
        return respuesta in ("", "s", "si", "sí", "y", "yes")

    # ── Portada ───────────────────────────────────────────────────────────────
    def bienvenida(self, configuracion: Configuracion) -> None:
        """[3] Portada: qué se va a ver y contra qué se está trabajando."""
        self.cabecera("Microsoft Agent Framework (MFA) — Demo interactiva A2A + MCP")
        print("\nEn esta demo vas a ver, en este orden:")
        print("  1. Cómo se crean tres agentes con MFA sobre Azure AI Foundry.")
        print("  2. Cómo se envían mensajes A2A entre ellos, uno a uno.")
        print("  3. Cómo el Agente de Investigación consulta Microsoft Learn por MCP,")
        print("     pidiéndote permiso antes de cada llamada.")
        print("\n🔗 Proyecto Foundry:", configuracion.endpoint_proyecto)
        print("🧠 Modelo:", configuracion.modelo)
        print("🔌 Servidor MCP:", configuracion.url_mcp)
        if self.automatica:
            print("\n[INFO] Sin terminal interactiva: la demo avanzará sola.")


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 3 — EL CONTRATO A2A
# 🏛️ SOLID: los mensajes son objetos inmutables, no diccionarios sueltos. Un
#    typo como mensaje["remitente"] deja de ser un error silencioso en tiempo de
#    ejecución y pasa a ser un fallo evidente al construir el objeto.
# ══════════════════════════════════════════════════════════════════════════════
class TipoMensaje:
    """📡 A2A Vocabulario del protocolo. Constantes con nombre, no cadenas sueltas."""

    PETICION_USUARIO = "peticion_usuario"
    SOLICITUD_INVESTIGACION = "solicitud_investigacion"
    SOLICITUD_FORMATO = "solicitud_formato"
    CIERRE_FINAL = "cierre_final"
    PING = "ping"


@dataclass(frozen=True)
class MensajeA2A:
    """📡 A2A El sobre que viaja de un agente a otro."""

    emisor: str
    destinatario: str
    tipo: str
    contenido: str
    datos: dict[str, Any] = field(default_factory=dict)
    enviado_en: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


@dataclass(frozen=True)
class RespuestaA2A:
    """📡 A2A Lo que el destinatario devuelve al emisor."""

    emisor: str
    destinatario: str
    tipo: str
    contenido: str
    exito: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 4 — POLÍTICA DE APROBACIÓN DE HERRAMIENTAS MCP
# 🏛️ SOLID (OCP + DIP): "quién decide si una herramienta puede ejecutarse" es
#    una pieza intercambiable. Hoy hay dos implementaciones; mañana podría haber
#    una que consulte una lista blanca o pida el visto bueno a un supervisor,
#    sin tocar ni una línea de los agentes.
# ══════════════════════════════════════════════════════════════════════════════
class PoliticaDeAprobacion(Protocol):
    """Decide si se autoriza la ejecución de una herramienta MCP."""

    async def decidir(self, herramienta: str, argumentos: Any) -> bool: ...


class AprobacionInteractiva:
    """🔌 MCP Pregunta al usuario por cada llamada. Es el 'human-in-the-loop'."""

    def __init__(self, consola: Consola) -> None:
        self.consola = consola

    async def decidir(self, herramienta: str, argumentos: Any) -> bool:
        print("\n  ┌" + "─" * (ANCHO - 6) + "┐")
        print("  │ 🔐 SOLICITUD DE APROBACIÓN DE HERRAMIENTA MCP")
        print("  │ " + "─" * (ANCHO - 8))
        print(f"  │ Herramienta: {herramienta}")
        print(f"  │ Argumentos:  {recortar(argumentos, ANCHO - 24)}")
        print("  └" + "─" * (ANCHO - 6) + "┘")
        return self.consola.confirmar("  ¿Autorizas esta llamada?")


class AprobacionAutomatica:
    """🔌 MCP Autoriza siempre, pero deja constancia en pantalla."""

    def __init__(self, consola: Consola) -> None:
        self.consola = consola

    async def decidir(self, herramienta: str, argumentos: Any) -> bool:
        self.consola.info(f"🔐 Aprobación automática → {herramienta}")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 5 — LOS AGENTES
# 🏛️ SOLID (LSP): los tres heredan de AgenteA2A y exponen el MISMO método
#    atender(). Por eso la red A2A puede tratarlos como equivalentes y entregar
#    un mensaje sin saber a quién se lo está dando.
# ══════════════════════════════════════════════════════════════════════════════
class AgenteA2A(ABC):
    """
    Base común de todo agente que participa en la red A2A.

    Implementa el patrón *plantilla*: `atender()` (el buzón) es igual para
    todos, y cada agente concreto solo rellena `_procesar()`.
    """

    #  Nº máximo de rondas de aprobación antes de rendirse (evita bucles).
    MAXIMO_RONDAS = 6

    def __init__(
        self,
        nombre: str,
        descripcion: str,
        agente_mfa: Agent,
        consola: Consola,
        politica: PoliticaDeAprobacion | None = None,
    ) -> None:
        self.nombre = nombre
        self.descripcion = descripcion
        self.consola = consola
        self.politica = politica

        # ⚙️ MFA El objeto Agent del framework: modelo + instrucciones + tools.
        self._agente = agente_mfa

        # ⚙️ MFA La SESIÓN es el hilo de conversación. Mantenerla viva es lo que
        #    hace que el agente recuerde los turnos anteriores. Antes esto eran
        #    los "threads" que había que crear a mano contra el servicio.
        self._sesion = agente_mfa.create_session()

    # ── Tipos de mensaje que sabe atender ─────────────────────────────────────
    @property
    @abstractmethod
    def tipos_admitidos(self) -> frozenset[str]:
        """📡 A2A Las 'capacidades' que este agente publica hacia los demás."""

    # ── [8.x] EL BUZÓN A2A: única puerta de entrada al agente ─────────────────
    async def atender(self, mensaje: MensajeA2A) -> RespuestaA2A:
        """
        📡 A2A Recibe un sobre y decide qué hacer con él.

        Tres ramas:
          - `ping`  → prueba de vida, no gasta tokens.
          - tipo conocido → lo procesa el agente concreto.
          - tipo desconocido → error explícito (NUNCA una respuesta inventada).
        """
        if mensaje.tipo == TipoMensaje.PING:
            return self._responder(mensaje, f"{self.nombre} operativo. {self.descripcion}")

        if mensaje.tipo not in self.tipos_admitidos:
            return self._responder(
                mensaje,
                f"{self.nombre} no atiende mensajes de tipo '{mensaje.tipo}'.",
                exito=False,
            )

        texto = await self._procesar(mensaje)
        return self._responder(mensaje, texto)

    def _responder(self, mensaje: MensajeA2A, contenido: str, exito: bool = True) -> RespuestaA2A:
        return RespuestaA2A(
            emisor=self.nombre,
            destinatario=mensaje.emisor,
            tipo=f"{mensaje.tipo}_respuesta",
            contenido=contenido,
            exito=exito,
        )

    @abstractmethod
    async def _procesar(self, mensaje: MensajeA2A) -> str:
        """Lo único que cada agente concreto tiene que implementar."""

    # ── El turno de conversación con el modelo (compartido por los tres) ──────
    async def _conversar(self, entrada: Any) -> str:
        """
        ⚙️ MFA Ejecuta un turno completo contra el modelo y devuelve el texto.

        Dentro de este único `await` ocurre TODO esto:
          1. MFA envía instrucciones + historial + catálogo de herramientas.
          2. El modelo decide si responde o si llama a una herramienta.
          3. Si la herramienta exige aprobación, el framework NO la ejecuta:
             devuelve la respuesta con `user_input_requests` pendientes.
          4. Nosotros aprobamos (o no) y volvemos a llamar con esas respuestas.
          5. MFA ejecuta la herramienta por MCP y el modelo redacta con el
             resultado.

        El bucle `for` es exactamente ese ida y vuelta de aprobaciones.
        """
        partes: list[str] = []
        siguiente_entrada: Any = entrada

        for _ in range(self.MAXIMO_RONDAS):
            # ⚙️ MFA stream=True devuelve un flujo: el texto se ve aparecer en
            #    vivo, como en un chat, en lugar de saltar de golpe al final.
            flujo = self._agente.run(siguiente_entrada, stream=True, session=self._sesion)

            async for actualizacion in flujo:
                if actualizacion.text:
                    self.consola.fragmento(actualizacion.text)
                    partes.append(actualizacion.text)

            # ⚙️ MFA Al terminar el streaming, la respuesta consolidada trae las
            #    solicitudes de aprobación pendientes (si las hay).
            respuesta = await flujo.get_final_response()
            if not respuesta.user_input_requests:
                break

            self.consola.salto()
            siguiente_entrada = await self._resolver_aprobaciones(respuesta.user_input_requests)

        self.consola.salto()
        return "".join(partes).strip()

    async def _resolver_aprobaciones(self, solicitudes: Sequence[Any]) -> list[Any]:
        """🔌 MCP Convierte cada solicitud pendiente en un sí o un no."""
        respuestas = []
        for solicitud in solicitudes:
            llamada = solicitud.function_call
            aprobar = True
            if self.politica is not None:
                aprobar = await self.politica.decidir(llamada.name, llamada.arguments)
            if not aprobar:
                self.consola.aviso(f"Llamada RECHAZADA: {llamada.name}")
            # ⚙️ MFA Esta es la respuesta que el framework espera de vuelta.
            respuestas.append(solicitud.to_function_approval_response(aprobar))
        return respuestas

    # ── Ciclo de vida (por defecto no hay nada que abrir ni cerrar) ───────────
    async def abrir(self) -> None:
        return None

    async def cerrar(self) -> None:
        return None

    def ficha(self) -> dict[str, Any]:
        """[7] Datos del agente para la ficha JSON."""
        return {
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "tipos_admitidos": sorted(self.tipos_admitidos),
            "persistencia": "efímero (vive solo durante esta ejecución)",
        }


class AgenteInvestigacion(AgenteA2A):
    """
    [5.1] Agente de Investigación — el ÚNICO que tiene herramientas.

    Consulta la documentación oficial a través del servidor MCP remoto de
    Microsoft Learn. No inventa: busca, lee y cita.
    """

    def __init__(
        self,
        agente_mfa: Agent,
        herramienta_mcp: MCPStreamableHTTPTool,
        consola: Consola,
        politica: PoliticaDeAprobacion,
    ) -> None:
        super().__init__(
            nombre="Agente de Investigación",
            descripcion="Busca en la documentación de Microsoft Learn vía MCP.",
            agente_mfa=agente_mfa,
            consola=consola,
            politica=politica,
        )
        self._mcp = herramienta_mcp

    @property
    def tipos_admitidos(self) -> frozenset[str]:
        return frozenset({TipoMensaje.SOLICITUD_INVESTIGACION})

    async def _procesar(self, mensaje: MensajeA2A) -> str:
        """[8.3] Traduce el encargo A2A a una consulta y deja decidir al modelo."""
        self.consola.info("📡 Investigando en Microsoft Learn…\n")
        return await self._conversar(mensaje.contenido)

    def herramientas_descubiertas(self) -> list[str]:
        """
        🔌 MCP Nombres de las herramientas que publica el servidor.

        Nadie las escribió a mano: llegaron en el handshake del protocolo. Si
        Microsoft añade una herramienta mañana, aparece aquí sin tocar el código.
        """
        return [funcion.name for funcion in self._mcp.functions]

    async def cerrar(self) -> None:
        """[9] 🔌 MCP Cierra la sesión HTTP con el servidor MCP."""
        await self._mcp.close()


class AgenteEjecutor(AgenteA2A):
    """
    [5.2] Agente Ejecutor — no busca nada: da forma a lo que otros encontraron.

    Ilustra que un agente NO necesita herramientas para aportar valor: su
    especialidad está en las instrucciones.
    """

    @property
    def tipos_admitidos(self) -> frozenset[str]:
        return frozenset({TipoMensaje.SOLICITUD_FORMATO})

    async def _procesar(self, mensaje: MensajeA2A) -> str:
        """[8.5] Recibe el material en bruto y devuelve un informe legible."""
        self.consola.info("🧱 Dando formato al material recibido…\n")
        return await self._conversar(mensaje.contenido)


class AgenteCoordinador(AgenteA2A):
    """
    [5.3] Agente Coordinador — la puerta de entrada del usuario.

    No tiene herramientas ni documentación: su trabajo es DELEGAR. Interviene
    dos veces en el flujo:
      * al principio (`peticion_usuario`), traduciendo la pregunta en un
        encargo concreto para el Agente de Investigación;
      * al final (`cierre_final`), redactando la respuesta que lee el usuario.
    """

    @property
    def tipos_admitidos(self) -> frozenset[str]:
        return frozenset({TipoMensaje.PETICION_USUARIO, TipoMensaje.CIERRE_FINAL})

    async def _procesar(self, mensaje: MensajeA2A) -> str:
        if mensaje.tipo == TipoMensaje.PETICION_USUARIO:
            self.consola.info("🧭 Preparando el encargo para el Agente de Investigación…\n")
            indicacion = (
                "Un usuario pregunta lo siguiente:\n"
                f"«{mensaje.contenido}»\n\n"
                "Tú NO tienes documentación ni herramientas. Redacta el encargo que le "
                "enviarás al Agente de Investigación para que busque la respuesta en "
                "Microsoft Learn. Responde ÚNICAMENTE con el texto del encargo, en "
                "español, en una o dos frases, sin saludos ni explicaciones."
            )
        else:
            self.consola.info("🧭 Redactando la respuesta final para el usuario…\n")
            indicacion = (
                "El Agente Ejecutor te devuelve este informe ya formateado:\n\n"
                f"{mensaje.contenido}\n\n"
                "Preséntaselo al usuario como respuesta final a su pregunta original. "
                "Sé fiel al contenido, no inventes datos y responde en español."
            )
        return await self._conversar(indicacion)


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 6 — LA RED A2A
# 🏛️ SOLID (OCP): dar de alta un cuarto agente es una línea de `registrar()`.
#    Ni la red ni la demo necesitan un `if` nuevo por cada agente.
# ══════════════════════════════════════════════════════════════════════════════
class RedA2A:
    """📡 A2A Directorio de agentes + entrega de mensajes."""

    def __init__(self, consola: Consola) -> None:
        self.consola = consola
        self._buzones: dict[str, AgenteA2A] = {}

    def registrar(self, agente: AgenteA2A) -> None:
        """[6] Da de alta el buzón de un agente."""
        self._buzones[agente.nombre] = agente

    @property
    def agentes(self) -> Iterable[AgenteA2A]:
        return self._buzones.values()

    async def entregar(self, mensaje: MensajeA2A) -> RespuestaA2A:
        """
        📡 A2A Muestra el sobre y lo deposita en el buzón del destinatario.

        Este método es "el protocolo": el emisor no llama a un método del
        destinatario, entrega un mensaje a la red y la red lo enruta. Si el
        día de mañana esto viajara por HTTP, solo cambiaría aquí dentro.
        """
        self.consola.sobre_a2a(mensaje)

        destino = self._buzones.get(mensaje.destinatario)
        if destino is None:
            self.consola.error(f"Destinatario desconocido: {mensaje.destinatario}")
            return RespuestaA2A(
                emisor="RedA2A",
                destinatario=mensaje.emisor,
                tipo="error_de_entrega",
                contenido=f"No hay ningún agente registrado como '{mensaje.destinatario}'.",
                exito=False,
            )
        return await destino.atender(mensaje)


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 7 — FÁBRICA DE AGENTES
# 🏛️ SOLID (SRP + DIP): concentra el CÓMO se construye cada agente (cliente,
#    modelo, credencial, instrucciones). La demo pide agentes; no sabe nada de
#    endpoints ni de credenciales.
# ══════════════════════════════════════════════════════════════════════════════
class FabricaDeAgentes:
    """[4] Construye el ChatClient de Foundry y, con él, los tres agentes."""

    def __init__(self, configuracion: Configuracion, credencial: DefaultAzureCredential, consola: Consola) -> None:
        self.configuracion = configuracion
        self.consola = consola

        # ⚙️ MFA [4.1] EL CHATCLIENT NO ES EL AGENTE.
        #    El ChatClient es el "motor": sabe hablar con Azure AI Foundry, y
        #    nada más. El Agent es el "personaje": añade nombre, instrucciones,
        #    herramientas y memoria. Un mismo motor mueve a los tres personajes,
        #    igual que un solo motor de coche podría mover tres carrocerías.
        self._cliente = FoundryChatClient(
            project_endpoint=configuracion.endpoint_proyecto,
            model=configuracion.modelo,
            credential=credencial,
        )

    # ── [5.1] ────────────────────────────────────────────────────────────────
    async def crear_agente_investigacion(self) -> AgenteInvestigacion:
        self.consola.paso(1, 3, "Creando el Agente de Investigación (con herramientas MCP)")
        self.consola.info("Rol:         investigador documental")
        self.consola.info("Capacidad:   acceso a la documentación de Microsoft Learn")
        self.consola.info(f"Servidor MCP: {self.configuracion.url_mcp}")
        self.consola.pausa("¿Creamos el Agente de Investigación? Pulsa Enter…")

        # 🔌 MCP [5.1.1] Cliente MCP sobre HTTP en streaming. Vive en el CORE de
        #    MFA: no hace falta ningún subpaquete. Frente a la versión anterior,
        #    que declaraba la herramienta como un diccionario suelto y aprobaba
        #    las llamadas con peticiones REST escritas a mano, aquí el protocolo
        #    lo habla el framework.
        herramienta = MCPStreamableHTTPTool(
            name="microsoft_learn",
            url=self.configuracion.url_mcp,
            # 🔌 MCP [5.1.2] La joya de esta migración: una sola palabra sustituye
            #    a todo el código de aprobación manual del ejercicio original.
            approval_mode="always_require",
        )

        # 🔌 MCP [5.1.3] connect() hace el handshake y DESCUBRE las herramientas.
        await herramienta.connect()

        # ⚙️ MFA [5.1.4] El Agent: modelo + instrucciones + herramientas.
        #    ⚠️ Ojo: esto NO crea nada en el proyecto de Azure AI Foundry. El
        #    agente es EFÍMERO y vive en memoria. La versión anterior usaba
        #    `agents_client.create_agent(...)`, que dejaba un agente registrado
        #    en el servicio en CADA ejecución… y nunca lo borraba.
        agente_mfa = Agent(
            self._cliente,
            name="agente-investigacion",
            instructions=(
                "Eres el Agente de Investigación de una red multiagente.\n\n"
                "Tus capacidades:\n"
                "- Buscar en la documentación oficial de Microsoft con las herramientas MCP "
                "de Microsoft Learn.\n"
                "- Leer páginas concretas cuando necesites el detalle.\n\n"
                "Reglas:\n"
                "- Usa SIEMPRE las herramientas antes de responder: no contestes de memoria.\n"
                "- Sé preciso y cita la fuente (título y enlace) cuando la tengas.\n"
                "- Si la documentación no cubre algo, dilo claramente en vez de suponerlo.\n"
                "- Responde SIEMPRE en español, aunque la documentación esté en inglés."
            ),
            tools=[herramienta],
        )

        agente = AgenteInvestigacion(
            agente_mfa=agente_mfa,
            herramienta_mcp=herramienta,
            consola=self.consola,
            politica=AprobacionInteractiva(self.consola)
            if not self.consola.automatica
            else AprobacionAutomatica(self.consola),
        )

        self.consola.exito("Agente de Investigación creado")
        self.consola.info("Modo de aprobación: always_require (te pedirá permiso por cada llamada)")
        self.consola.info("Herramientas descubiertas POR PROTOCOLO (no escritas a mano):")
        for nombre in agente.herramientas_descubiertas():
            self.consola.info(f"   • {nombre}")
        return agente

    # ── [5.2] ────────────────────────────────────────────────────────────────
    async def crear_agente_ejecutor(self) -> AgenteEjecutor:
        self.consola.paso(2, 3, "Creando el Agente Ejecutor (sin herramientas)")
        self.consola.info("Rol:       procesador y redactor")
        self.consola.info("Capacidad: estructurar y resumir información recibida")
        self.consola.info("Herramientas MCP: ninguna — solo recibe encargos por A2A")
        self.consola.pausa("¿Creamos el Agente Ejecutor? Pulsa Enter…")

        agente_mfa = Agent(
            self._cliente,
            name="agente-ejecutor",
            instructions=(
                "Eres el Agente Ejecutor de una red multiagente.\n\n"
                "Tu trabajo:\n"
                "- Recibir información en bruto de otros agentes.\n"
                "- Estructurarla y resumirla en un informe claro y ordenado.\n"
                "- Usar títulos, viñetas y negritas para que se lea de un vistazo.\n\n"
                "Reglas:\n"
                "- NO añadas datos que no estén en el material recibido.\n"
                "- Conserva los enlaces y las fuentes que te lleguen.\n"
                "- Responde SIEMPRE en español."
            ),
        )

        agente = AgenteEjecutor(
            nombre="Agente Ejecutor",
            descripcion="Estructura y resume la información que le envían.",
            agente_mfa=agente_mfa,
            consola=self.consola,
        )
        self.consola.exito("Agente Ejecutor creado")
        return agente

    # ── [5.3] ────────────────────────────────────────────────────────────────
    async def crear_agente_coordinador(self) -> AgenteCoordinador:
        self.consola.paso(3, 3, "Creando el Agente Coordinador (orquesta la red A2A)")
        self.consola.info("Rol:       orquestador del flujo de trabajo")
        self.consola.info("Capacidad: delegar en los otros agentes vía A2A")
        self.consola.info("Herramientas MCP: ninguna — TIENE que delegar para saber algo")
        self.consola.pausa("¿Creamos el Agente Coordinador? Pulsa Enter…")

        agente_mfa = Agent(
            self._cliente,
            name="agente-coordinador",
            instructions=(
                "Eres el Agente Coordinador de una red multiagente.\n\n"
                "IMPORTANTE: no tienes documentación ni herramientas propias. Todo lo que "
                "sabes te llega de otros agentes por el protocolo A2A.\n\n"
                "Agentes disponibles:\n"
                "- Agente de Investigación: tiene las herramientas MCP de Microsoft Learn.\n"
                "- Agente Ejecutor: da formato y resume.\n\n"
                "Tu flujo de trabajo:\n"
                "1. Recibes la pregunta del usuario.\n"
                "2. Redactas un encargo de investigación claro y concreto.\n"
                "3. Recibes el informe ya formateado.\n"
                "4. Presentas la respuesta final al usuario.\n\n"
                "Responde SIEMPRE en español y no inventes información."
            ),
        )

        agente = AgenteCoordinador(
            nombre="Agente Coordinador",
            descripcion="Orquesta el trabajo de los demás agentes por A2A.",
            agente_mfa=agente_mfa,
            consola=self.consola,
        )
        self.consola.exito("Agente Coordinador creado")
        return agente


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 8 — EL GUION DE LA DEMOSTRACIÓN
# 🏛️ SOLID (SRP): esta clase solo sabe CONTAR la historia de los 7 pasos. No
#    construye agentes ni imprime cajas: pide a la red que entregue mensajes y
#    a la consola que los muestre.
# ══════════════════════════════════════════════════════════════════════════════
class DemostracionA2A:
    """[8] Los siete pasos del flujo multiagente, uno a uno y con pausas."""

    USUARIO = "Usuario"

    def __init__(self, red: RedA2A, consola: Consola) -> None:
        self.red = red
        self.consola = consola

    async def ejecutar(self) -> bool:
        self.consola.cabecera("FASE 2 — DEMOSTRACIÓN DE COMUNICACIÓN A2A")

        self.consola.info("🌐 Red de agentes registrada:")
        for agente in self.red.agentes:
            self.consola.info(f"   • {agente.nombre} — {agente.descripcion}")

        # [8.1] La pregunta del usuario.
        self.consola.cabecera("HAZ UNA PREGUNTA")
        pregunta = self.consola.preguntar(
            "🤔 Escribe tu pregunta sobre Microsoft/Azure: ", PREGUNTA_POR_DEFECTO
        )
        self.consola.pausa("Pulsa Enter para arrancar el flujo…")

        # ── [8.2] PASO 1 — Usuario → Coordinador ─────────────────────────────
        self.consola.cabecera("PASO 1/7 — Usuario → Agente Coordinador")
        respuesta_coordinador = await self.red.entregar(
            MensajeA2A(
                emisor=self.USUARIO,
                destinatario="Agente Coordinador",
                tipo=TipoMensaje.PETICION_USUARIO,
                contenido=pregunta,
            )
        )
        if not respuesta_coordinador.exito:
            self.consola.error("El Coordinador no pudo procesar la petición.")
            return False

        # 📌 Ojo al detalle: el encargo que redacta el Coordinador SE USA en el
        #    paso siguiente. En la versión anterior de esta demo se lanzaba el
        #    run del Coordinador y su respuesta se descartaba sin leerla.
        encargo = respuesta_coordinador.contenido or pregunta
        self.consola.exito("El Coordinador ha redactado el encargo de investigación")
        self.consola.pausa("Pulsa Enter para ver la delegación A2A…")

        # ── [8.3] PASO 2 — Coordinador → Investigación ───────────────────────
        self.consola.cabecera("PASO 2/7 — Agente Coordinador → Agente de Investigación (A2A)")
        self.consola.info("El Coordinador delega: él no tiene documentación, el otro sí.")

        # ── [8.4] PASO 3 — Investigación → MCP (ocurre DENTRO de la entrega) ──
        self.consola.info("Durante esta entrega verás el PASO 3: las llamadas MCP y su aprobación.")
        respuesta_investigacion = await self.red.entregar(
            MensajeA2A(
                emisor="Agente Coordinador",
                destinatario="Agente de Investigación",
                tipo=TipoMensaje.SOLICITUD_INVESTIGACION,
                contenido=encargo,
                datos={"pregunta_original": pregunta},
            )
        )
        if not respuesta_investigacion.exito or not respuesta_investigacion.contenido:
            self.consola.error("El Agente de Investigación no devolvió resultados.")
            return False

        # ── [8.5] PASO 4 — Investigación → Coordinador ───────────────────────
        self.consola.cabecera("PASO 4/7 — Agente de Investigación → Agente Coordinador (A2A)")
        self.consola.exito(
            f"Investigación completada: {len(respuesta_investigacion.contenido)} caracteres"
        )
        self.consola.pausa("Pulsa Enter para pasar el material al Agente Ejecutor…")

        # ── [8.6] PASO 5 — Coordinador → Ejecutor ────────────────────────────
        self.consola.cabecera("PASO 5/7 — Agente Coordinador → Agente Ejecutor (A2A)")
        respuesta_ejecutor = await self.red.entregar(
            MensajeA2A(
                emisor="Agente Coordinador",
                destinatario="Agente Ejecutor",
                tipo=TipoMensaje.SOLICITUD_FORMATO,
                contenido=(
                    "Da formato y resume este material de investigación para el usuario, "
                    f"que preguntó: «{pregunta}».\n\n{respuesta_investigacion.contenido}"
                ),
            )
        )
        if not respuesta_ejecutor.exito or not respuesta_ejecutor.contenido:
            self.consola.error("El Agente Ejecutor no devolvió resultados.")
            return False

        # ── [8.7] PASO 6 — Ejecutor → Coordinador ────────────────────────────
        self.consola.cabecera("PASO 6/7 — Agente Ejecutor → Agente Coordinador (A2A)")
        self.consola.exito("Formato aplicado")
        self.consola.pausa("Pulsa Enter para ver la respuesta final…")

        # ── [8.8] PASO 7 — Coordinador → Usuario ─────────────────────────────
        self.consola.cabecera("PASO 7/7 — Agente Coordinador → Usuario")
        respuesta_final = await self.red.entregar(
            MensajeA2A(
                emisor=self.USUARIO,
                destinatario="Agente Coordinador",
                tipo=TipoMensaje.CIERRE_FINAL,
                contenido=respuesta_ejecutor.contenido,
            )
        )
        if not respuesta_final.exito:
            self.consola.error("El Coordinador no pudo redactar la respuesta final.")
            return False

        self._resumen()
        return True

    def _resumen(self) -> None:
        self.consola.cabecera("RESUMEN DEL FLUJO A2A")
        print("  1. ✅ Usuario                → Agente Coordinador")
        print("  2. ✅ Agente Coordinador     → Agente de Investigación   (A2A)")
        print("  3. ✅ Agente de Investigación→ Microsoft Learn           (MCP)")
        print("  4. ✅ Agente de Investigación→ Agente Coordinador        (A2A)")
        print("  5. ✅ Agente Coordinador     → Agente Ejecutor           (A2A)")
        print("  6. ✅ Agente Ejecutor        → Agente Coordinador        (A2A)")
        print("  7. ✅ Agente Coordinador     → Usuario")
        print("\n🎉 Flujo multiagente completo demostrado de principio a fin.")


# ══════════════════════════════════════════════════════════════════════════════
# CAPA 9 — PROGRAMA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
def guardar_ficha(agentes: Iterable[AgenteA2A], configuracion: Configuracion) -> Path:
    """
    [7] Deja constancia en disco de la red que se acaba de montar.

    🔧 Infra La ruta se ancla al directorio del script, no al de trabajo: así el
    archivo aparece siempre en el mismo sitio se lance desde donde se lance.
    """
    destino = DIRECTORIO_BASE / "agents_info_interactive.json"
    ficha = {
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "proyecto_foundry": configuracion.endpoint_proyecto,
        "modelo": configuracion.modelo,
        "servidor_mcp": configuracion.url_mcp,
        "agentes": [agente.ficha() for agente in agentes],
    }
    destino.write_text(json.dumps(ficha, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino


async def main() -> None:
    """[1] Punto de entrada: monta la red, la enseña y la desmonta."""
    consola = Consola(automatica=not sys.stdin.isatty())

    # [2] Configuración validada (falla pronto si el .env está incompleto).
    configuracion = Configuracion.desde_entorno()

    # [3] Portada.
    consola.bienvenida(configuracion)
    consola.pausa("¿Empezamos? Pulsa Enter…")

    agentes: list[AgenteA2A] = []

    # ⚙️ MFA / 🔧 Infra La credencial es un recurso con ciclo de vida: se abre
    #    con `async with` para garantizar que se cierra pase lo que pase.
    async with DefaultAzureCredential() as credencial:
        # [4] Fábrica: crea el motor (ChatClient) una sola vez.
        fabrica = FabricaDeAgentes(configuracion, credencial, consola)
        try:
            # ── [5] FASE 1 ───────────────────────────────────────────────────
            consola.cabecera("FASE 1 — CREACIÓN DE LOS AGENTES")
            investigacion = await fabrica.crear_agente_investigacion()
            agentes.append(investigacion)
            consola.pausa("Pulsa Enter para crear el siguiente agente…")

            ejecutor = await fabrica.crear_agente_ejecutor()
            agentes.append(ejecutor)
            consola.pausa("Pulsa Enter para crear el siguiente agente…")

            coordinador = await fabrica.crear_agente_coordinador()
            agentes.append(coordinador)

            # ── [6] Alta en la red A2A ───────────────────────────────────────
            red = RedA2A(consola)
            for agente in agentes:
                red.registrar(agente)

            # ── [7] Ficha en disco ───────────────────────────────────────────
            ruta = guardar_ficha(agentes, configuracion)

            consola.cabecera("RED A2A LISTA")
            consola.info("Agentes activos:")
            for agente in agentes:
                consola.info(f"   • {agente.nombre}")
            consola.info(f"\n📄 Ficha guardada en: {ruta.name}")
            consola.info("♻️  Son agentes EFÍMEROS: no queda nada registrado en Foundry.")
            consola.pausa("¿Pasamos a la demostración A2A? Pulsa Enter…")

            # ── [8] FASE 2 ───────────────────────────────────────────────────
            correcto = await DemostracionA2A(red, consola).ejecutar()

            if correcto:
                consola.cabecera("🎉 DEMO COMPLETADA CORRECTAMENTE")
            else:
                consola.cabecera("⚠️  LA DEMO TERMINÓ CON INCIDENCIAS")

        finally:
            # ── [9] Cierre ───────────────────────────────────────────────────
            # 🔌 MCP Cerrar la sesión con el servidor MCP es obligatorio; si no,
            #    queda una conexión HTTP abierta. El `finally` garantiza que se
            #    cierre incluso si la demo revienta a mitad.
            for agente in agentes:
                await agente.cerrar()

    print("\n" + "=" * ANCHO)
    print("Gracias por usar la demo del Microsoft Agent Framework.")
    print("=" * ANCHO)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrumpida por el usuario.")
    except ValueError as error:  # configuración incompleta
        print(f"\n\n❌ Configuración: {error}")
    except Exception as error:  # noqa: BLE001 — demo didáctica: se muestra todo
        print(f"\n\n❌ Error inesperado: {error}")
        import traceback

        traceback.print_exc()
