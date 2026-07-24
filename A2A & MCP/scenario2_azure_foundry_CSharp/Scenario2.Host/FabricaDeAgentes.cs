using Azure.AI.Projects;
using Azure.Identity;
using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;
using Scenario2.Host.Agents;
using Scenario2.Host.Aprobacion;

namespace Scenario2.Host;

// =============================================================================
// CAPA 7 — FÁBRICA DE AGENTES
// =============================================================================
// 🏛️ SOLID (SRP + DIP): concentra el CÓMO se construye cada agente (cliente,
//    modelo, credencial, instrucciones). La demo pide agentes; no sabe nada de
//    endpoints ni de credenciales.

/// <summary>[4] Construye el cliente del proyecto de Foundry y, con él, los tres agentes.</summary>
public sealed class FabricaDeAgentes
{
    private readonly Configuracion _configuracion;
    private readonly Consola _consola;
    private readonly AIProjectClient _proyecto;

    public FabricaDeAgentes(Configuracion configuracion, Consola consola)
    {
        _configuracion = configuracion;
        _consola = consola;

        // ⚙️ MFA [4.1] EL CLIENTE DEL PROYECTO NO ES EL AGENTE.
        //    AIProjectClient es el "motor": sabe hablar con Azure AI Foundry, y nada
        //    más. El agente es el "personaje": añade nombre, instrucciones,
        //    herramientas y memoria. Un mismo motor mueve a los tres personajes,
        //    igual que un solo motor de coche podría mover tres carrocerías.
        //
        // 🔐 [4.2] DefaultAzureCredential busca tu identidad allí donde esté (Azure
        //    CLI, Visual Studio, variables de entorno, identidad gestionada…).
        //    NO hay ninguna clave de API en el proyecto. Requiere `az login`.
        _proyecto = new AIProjectClient(new Uri(configuracion.EndpointProyecto), new DefaultAzureCredential());
    }

    // =========================================================================
    // [5.1] Agente de Investigación — el único con herramientas
    // =========================================================================
    public async Task<AgenteInvestigacion> CrearAgenteInvestigacionAsync(CancellationToken ct = default)
    {
        _consola.Paso(1, 3, "Creando el Agente de Investigación (con herramientas MCP)");
        _consola.Info("Rol:          investigador documental");
        _consola.Info("Capacidad:    acceso a la documentación de Microsoft Learn");
        _consola.Info($"Servidor MCP: {_configuracion.UrlMcp}");
        _consola.Pausa("¿Creamos el Agente de Investigación? Pulsa Enter…");

        // 🔌 MCP [5.1.1] Transporte HTTP en streaming hacia un servidor MCP REMOTO.
        //    Contrasta con el escenario 1, donde el transporte era stdio y el
        //    servidor un subproceso local. El protocolo es el mismo; cambia el cable.
        var transporte = new HttpClientTransport(new HttpClientTransportOptions
        {
            Name = "microsoft_learn",
            Endpoint = new Uri(_configuracion.UrlMcp),
        });

        // 🔌 MCP [5.1.2] CreateAsync hace el handshake `initialize` del protocolo.
        var clienteMcp = await McpClient.CreateAsync(transporte, cancellationToken: ct);

        // 🔌 MCP [5.1.3] Las herramientas se DESCUBREN por protocolo; no están
        //    escritas a mano en ninguna parte.
        var herramientas = await clienteMcp.ListToolsAsync(cancellationToken: ct);

        // 🔌 MCP [5.1.4] La joya de esta demo: envolver cada herramienta en
        //    ApprovalRequiredAIFunction obliga a que un HUMANO autorice la llamada
        //    antes de que se ejecute. Es el equivalente exacto del kwarg
        //    approval_mode="always_require" de la versión Python.
        AITool[] conAprobacion = [.. herramientas.Select(h => new ApprovalRequiredAIFunction(h))];

        // ⚙️ MFA [5.1.5] AsAIAgent une cliente + modelo + instrucciones + herramientas.
        //    ⚠️ Ojo: esto NO crea nada en el proyecto de Azure AI Foundry. El agente
        //    es EFÍMERO y vive en memoria. El SDK antiguo usaba CreateAgent(...),
        //    que dejaba un agente registrado en el servicio en CADA ejecución… y
        //    nunca lo borraba.
        var agenteMfa = _proyecto.AsAIAgent(
            model: _configuracion.Modelo,
            name: "agente-investigacion",
            instructions:
                """
                Eres el Agente de Investigación de una red multiagente.

                Tus capacidades:
                - Buscar en la documentación oficial de Microsoft con las herramientas MCP de Microsoft Learn.
                - Leer páginas concretas cuando necesites el detalle.

                Reglas:
                - Usa SIEMPRE las herramientas antes de responder: no contestes de memoria.
                - Sé preciso y cita la fuente (título y enlace) cuando la tengas.
                - Si la documentación no cubre algo, dilo claramente en vez de suponerlo.
                - Responde SIEMPRE en español, aunque la documentación esté en inglés.
                """,
            tools: conAprobacion);

        // 🏛️ SOLID (DIP): la política de aprobación se INYECTA. Cambiarla por una
        //    lista blanca no obligaría a tocar el agente.
        IPoliticaDeAprobacion politica = _consola.Automatica
            ? new AprobacionAutomatica(_consola)
            : new AprobacionInteractiva(_consola);

        var agente = new AgenteInvestigacion(agenteMfa, clienteMcp, [.. herramientas], _consola, politica);

        _consola.Exito("Agente de Investigación creado");
        _consola.Info("Modo de aprobación: obligatoria (te pedirá permiso por cada llamada)");
        _consola.Info("Herramientas descubiertas POR PROTOCOLO (no escritas a mano):");
        foreach (var nombre in agente.HerramientasDescubiertas())
            _consola.Info($"   • {nombre}");

        return agente;
    }

    // =========================================================================
    // [5.2] Agente Ejecutor — sin herramientas
    // =========================================================================
    public Task<AgenteEjecutor> CrearAgenteEjecutorAsync(CancellationToken ct = default)
    {
        _consola.Paso(2, 3, "Creando el Agente Ejecutor (sin herramientas)");
        _consola.Info("Rol:              procesador y redactor");
        _consola.Info("Capacidad:        estructurar y resumir información recibida");
        _consola.Info("Herramientas MCP: ninguna — solo recibe encargos por A2A");
        _consola.Pausa("¿Creamos el Agente Ejecutor? Pulsa Enter…");

        var agenteMfa = _proyecto.AsAIAgent(
            model: _configuracion.Modelo,
            name: "agente-ejecutor",
            instructions:
                """
                Eres el Agente Ejecutor de una red multiagente.

                Tu trabajo:
                - Recibir información en bruto de otros agentes.
                - Estructurarla y resumirla en un informe claro y ordenado.
                - Usar títulos, viñetas y negritas para que se lea de un vistazo.

                Reglas:
                - NO añadas datos que no estén en el material recibido.
                - Conserva los enlaces y las fuentes que te lleguen.
                - Responde SIEMPRE en español.
                """);

        var agente = new AgenteEjecutor(agenteMfa, _consola);
        _consola.Exito("Agente Ejecutor creado");
        return Task.FromResult(agente);
    }

    // =========================================================================
    // [5.3] Agente Coordinador — orquesta la red
    // =========================================================================
    public Task<AgenteCoordinador> CrearAgenteCoordinadorAsync(CancellationToken ct = default)
    {
        _consola.Paso(3, 3, "Creando el Agente Coordinador (orquesta la red A2A)");
        _consola.Info("Rol:              orquestador del flujo de trabajo");
        _consola.Info("Capacidad:        delegar en los otros agentes vía A2A");
        _consola.Info("Herramientas MCP: ninguna — TIENE que delegar para saber algo");
        _consola.Pausa("¿Creamos el Agente Coordinador? Pulsa Enter…");

        var agenteMfa = _proyecto.AsAIAgent(
            model: _configuracion.Modelo,
            name: "agente-coordinador",
            instructions:
                """
                Eres el Agente Coordinador de una red multiagente.

                IMPORTANTE: no tienes documentación ni herramientas propias. Todo lo que
                sabes te llega de otros agentes por el protocolo A2A.

                Agentes disponibles:
                - Agente de Investigación: tiene las herramientas MCP de Microsoft Learn.
                - Agente Ejecutor: da formato y resume.

                Tu flujo de trabajo:
                1. Recibes la pregunta del usuario.
                2. Redactas un encargo de investigación claro y concreto.
                3. Recibes el informe ya formateado.
                4. Presentas la respuesta final al usuario.

                Responde SIEMPRE en español y no inventes información.
                """);

        var agente = new AgenteCoordinador(agenteMfa, _consola);
        _consola.Exito("Agente Coordinador creado");
        return Task.FromResult(agente);
    }
}
