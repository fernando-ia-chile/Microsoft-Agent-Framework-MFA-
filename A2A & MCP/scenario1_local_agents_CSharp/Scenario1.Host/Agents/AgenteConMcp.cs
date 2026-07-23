using System.ClientModel;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;
using OpenAI.Chat;
using Scenario1.Host.A2A;

namespace Scenario1.Host.Agents;

/// <summary>
/// Base común de los agentes que consumen un servidor MCP.
/// </summary>
/// <remarks>
/// Reúne lo que comparten el Agente de Investigación y el Agente Ejecutor:
/// crear el cliente de chat, lanzar el servidor MCP como subproceso, descubrir sus
/// herramientas y construir el agente de MFA.
/// </remarks>
internal abstract class AgenteConMcp : IAgenteA2A
{
    private readonly string _proyectoServidorMcp;
    private readonly string _nombreHerramientaMcp;

    private McpClient? _clienteMcp;
    private AIAgent? _agente;

    protected AgenteConMcp(string proyectoServidorMcp, string nombreHerramientaMcp)
    {
        _proyectoServidorMcp = proyectoServidorMcp;
        _nombreHerramientaMcp = nombreHerramientaMcp;
    }

    public abstract string AgenteId { get; }
    public abstract string Nombre { get; }
    public abstract string Rol { get; }

    /// <summary>Instrucciones del agente (su system prompt).</summary>
    protected abstract string Instrucciones { get; }

    /// <summary>Agente de MFA ya construido. Requiere haber llamado a <see cref="ConectarAsync"/>.</summary>
    protected AIAgent Agente => _agente
        ?? throw new InvalidOperationException($"{Nombre}: llama primero a ConectarAsync().");

    // =========================================================================
    // CICLO DE VIDA MCP — conexión perezosa (solo la primera vez)
    // =========================================================================
    /// <summary>Conecta con el servidor MCP y construye el agente. Idempotente.</summary>
    public async Task ConectarAsync(CancellationToken ct = default)
    {
        if (_agente is not null) return;

        var rutaServidor = Configuracion.RutaServidorMcp(_proyectoServidorMcp);
        Console.WriteLine($"   🔌 Conectando por MCP (stdio) con {Path.GetFileName(rutaServidor)}...");

        // [C.1] 🔌 MCP: el transporte stdio lanza el servidor como SUBPROCESO y habla
        //       JSON-RPC con él por entrada/salida estándar. No abre ningún puerto.
        //       Command = "dotnet" + la DLL compilada garantiza el mismo runtime.
        var transporte = new StdioClientTransport(new StdioClientTransportOptions
        {
            Name = _nombreHerramientaMcp,
            Command = "dotnet",
            Arguments = [rutaServidor],
            // 🔧 Infra: el stderr del servidor se descarta para que sus mensajes de
            //    arranque no se mezclen con la interfaz del agente.
            StandardErrorLines = _ => { },
        });

        // [C.2] 🔌 MCP: CreateAsync hace el handshake `initialize` del protocolo.
        _clienteMcp = await McpClient.CreateAsync(transporte, cancellationToken: ct);

        // [C.3] 🔌 MCP: las herramientas se DESCUBREN por protocolo; no están escritas
        //       a mano en ninguna parte. Si mañana el servidor publica una tool nueva,
        //       aparece aquí sola. Eso es MCP.
        var herramientas = await _clienteMcp.ListToolsAsync(cancellationToken: ct);
        Console.WriteLine($"   ✅ MCP conectado. Herramientas descubiertas: {string.Join(", ", herramientas.Select(h => h.Name))}");

        // [C.4] ⚙️ MFA: el ChatClient es el CANAL hacia el modelo; todavía no es agente.
        //       ⚠️ El endpoint debe ser SOLO la base (sin /openai/...): la librería
        //       completa la ruta por su cuenta.
        ChatClient clienteChat = new AzureOpenAIClient(
                new Uri(Configuracion.Endpoint),
                new ApiKeyCredential(Configuracion.ApiKey))
            .GetChatClient(Configuracion.Deployment);

        // [C.5] ⚙️ MFA: AsAIAgent une cliente + instrucciones + herramientas.
        //       McpClientTool deriva de AIFunction, así que las herramientas MCP se
        //       pasan igual que cualquier función local: el framework le enseña su
        //       esquema al modelo y ejecuta la que el modelo decida invocar.
        _agente = clienteChat.AsAIAgent(
            instructions: Instrucciones,
            name: AgenteId,
            tools: [.. herramientas.Cast<AITool>()]);
    }

    /// <summary>Buzón del agente. Lo implementa cada agente concreto.</summary>
    public abstract Task<RespuestaA2A> ManejarMensajeAsync(MensajeA2A mensaje, CancellationToken ct = default);

    // =========================================================================
    // EJECUCIÓN — el modelo decide qué herramienta MCP usar
    // =========================================================================
    /// <summary>
    /// Envía una instrucción al agente y devuelve su respuesta, mostrándola en streaming.
    /// </summary>
    protected async Task<string> PreguntarAlAgenteAsync(string instruccion, CancellationToken ct)
    {
        await ConectarAsync(ct);

        Console.WriteLine();
        Console.WriteLine("   🤖 Respuesta del agente:");
        Console.Write("   ");

        // ⚙️ MFA: RunStreamingAsync devuelve un flujo asíncrono de fragmentos. Por
        //    debajo, en este único bucle ocurre todo el ciclo:
        //      modelo -> decide llamar a una tool -> el framework la ejecuta por MCP
        //      -> el servidor hace su trabajo -> el resultado vuelve al modelo
        //      -> el modelo redacta la respuesta final.
        //    (La variante sin streaming sería `await Agente.RunAsync(instruccion)`.)
        var texto = new System.Text.StringBuilder();
        await foreach (var fragmento in Agente.RunStreamingAsync(instruccion, cancellationToken: ct))
        {
            if (string.IsNullOrEmpty(fragmento.Text)) continue;
            texto.Append(fragmento.Text);
            Console.Write(fragmento.Text);
        }
        Console.WriteLine();

        return texto.ToString().Trim();
    }

    /// <summary>Cierra la sesión MCP y termina el subproceso del servidor.</summary>
    public async ValueTask DisposeAsync()
    {
        // ⚙️ MFA: sin cerrar el cliente, el subproceso del servidor quedaría huérfano.
        if (_clienteMcp is not null)
            await _clienteMcp.DisposeAsync();

        _clienteMcp = null;
        _agente = null;
    }
}
