using System.ComponentModel;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using MFA.CSharp.Part2.Infrastructure;

namespace MFA.CSharp.Part2.Examples;

/// <summary>
/// 12 · Memoria de largo plazo con extracción por IA.
/// Equivalente C# de new_12_long_term_memory_AI.py.
///
/// Objetivo pedagógico: mostrar que un agente puede tener DOS capas de memoria:
///   • Corto plazo → el historial de la sesión; se pierde al abrir una nueva.
///   • Largo plazo → un perfil del usuario que persiste en disco y sobrevive a
///     sesiones nuevas e incluso a reinicios del programa.
/// Y que ese perfil no se llena con reglas rígidas: es la propia IA la que decide
/// qué vale la pena recordar de cada mensaje.
///
/// Prueba clave: escribe 'new' para abrir una sesión limpia. El agente olvida la
/// conversación pero SIGUE sabiendo quién eres.
/// </summary>
internal static class Example12_LongTermMemoryAI
{
    private const string MemoryFile = "ai_memory_profile.json";

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 70));
        Console.WriteLine("🤖 DEMO 12: MEMORIA DE LARGO PLAZO CON IA + PERSISTENCIA EN ARCHIVO");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("\nConcepto: la IA decide sola qué información vale la pena guardar.");
        Console.WriteLine($"Archivo de memoria: {MemoryFile}");
        Console.WriteLine(new string('=', 70));

        // Un único chat client sirve para las dos cosas: conversar y extraer el perfil.
        IChatClient chatClient = AzureAgentFactory.CreateChatClient();

        Console.WriteLine("\n🔧 Creando agente con memoria impulsada por IA...");
        var memoria = new MemoriaConIA(chatClient);
        Console.WriteLine("   ✅ Analizador de memoria inicializado");

        // El context provider se engancha al agente vía AIContextProviders.
        AIAgent agent = new ChatClientAgent(
            chatClient,
            new ChatClientAgentOptions
            {
                Name = "MemoryBot",
                ChatOptions = new ChatOptions
                {
                    Instructions =
                        "Eres un asistente amable y cercano con memoria de largo plazo.\n" +
                        "Cuando reconozcas datos del perfil del usuario, menciónalos con " +
                        "naturalidad, salúdalo con entusiasmo y personaliza tus respuestas.\n" +
                        "Sé conversacional y cálido.",
                },
                AIContextProviders = [memoria],
            });

        Console.WriteLine("✅ Agente creado con memoria de largo plazo\n");

        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💡 COMANDOS:");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("  • Conversa normalmente — la IA extrae y guarda datos en el archivo");
        Console.WriteLine("  • 'new'     - Abre una sesión nueva (prueba la memoria entre sesiones)");
        Console.WriteLine("  • 'profile' - Muestra lo que la IA aprendió de ti");
        Console.WriteLine("  • 'quit'    - Salir");
        Console.WriteLine(new string('=', 70));

        int numeroSesion = 0;
        AgentSession? session = null;

        while (true)
        {
            // Crear sesión nueva cuando haga falta (al arrancar o tras 'new').
            if (session is null)
            {
                numeroSesion++;
                session = await agent.CreateSessionAsync();
                Console.WriteLine($"\n🆕 SESIÓN #{numeroSesion} creada\n");
            }

            Console.Write("Tú: ");
            string? input = Console.ReadLine()?.Trim();
            if (input is null) break;
            if (input.Length == 0) continue;

            if (input is "quit" or "exit" or "q")
            {
                Console.WriteLine("\n👋 ¡Demo terminada!");
                memoria.MostrarPerfil("📊 Perfil final aprendido por la IA:");
                break;
            }

            if (input is "new")
            {
                // Solo se descarta la sesión: el perfil de largo plazo sobrevive.
                session = null;
                Console.WriteLine("\n🔄 Sesión descartada. El perfil de largo plazo se mantiene.");
                continue;
            }

            if (input is "profile")
            {
                memoria.MostrarPerfil("📋 PERFIL APRENDIDO POR LA IA:");
                continue;
            }

            // El provider se dispara solo: inyecta el perfil antes y aprende después.
            Console.Write($"Agente (Sesión #{numeroSesion}): ");
            await foreach (AgentResponseUpdate update in agent.RunStreamingAsync(input, session))
            {
                Console.Write(update.Text);
            }
            Console.WriteLine("\n");
        }
    }

    // ========================================================================
    // MODELO DE SALIDA ESTRUCTURADA
    // ========================================================================
    // En vez de pedirle al modelo "devuelve JSON" y luego rebuscar las llaves en
    // el texto, declaramos la forma exacta que queremos. El framework la valida y
    // nos entrega objetos ya tipados.

    internal sealed class DatoPerfil
    {
        [Description("Atributo en snake_case: nombre, profesion, color_favorito...")]
        [JsonPropertyName("clave")]
        public string Clave { get; set; } = "";

        [Description("El valor del atributo, breve")]
        [JsonPropertyName("valor")]
        public string Valor { get; set; } = "";
    }

    internal sealed class PerfilExtraido
    {
        [Description("Datos personales duraderos. Vacío si el mensaje no aporta nada.")]
        [JsonPropertyName("datos")]
        public List<DatoPerfil> Datos { get; set; } = [];
    }

    // ========================================================================
    // CONTEXT PROVIDER: memoria de largo plazo impulsada por IA
    // ========================================================================

    /// <summary>
    /// Inyecta el perfil del usuario antes de cada run y lo actualiza después.
    ///
    /// Ciclo de vida en el Agent Framework de .NET:
    ///   • ProvideAIContextAsync(...) → ANTES de llamar al modelo. Devolvemos un
    ///     AIContext con instrucciones extra.
    ///   • StoreAIContextAsync(...)   → DESPUÉS. Le pedimos a la IA que analice lo
    ///     que dijo el usuario y guardamos lo que valga la pena.
    ///
    /// Importante: la MISMA instancia del provider se comparte entre todas las
    /// sesiones del agente, así que no debe guardar estado por sesión en campos.
    /// Aquí no es problema porque el perfil es global al usuario y vive en disco.
    /// </summary>
    private sealed class MemoriaConIA : AIContextProvider
    {
        private readonly IChatClient _chatClient;
        private readonly Dictionary<string, string> _perfil = [];
        private static readonly JsonSerializerOptions s_json = new() { WriteIndented = true };

        public MemoriaConIA(IChatClient chatClient) : base(null, null)
        {
            _chatClient = chatClient;
            CargarPerfil();
        }

        // ---------------------------------------------------------- disco --

        private void CargarPerfil()
        {
            if (!File.Exists(MemoryFile))
            {
                Console.WriteLine($"\n📋 [MEMORIA NUEVA] No existe {MemoryFile} todavía");
                return;
            }

            try
            {
                string contenido = File.ReadAllText(MemoryFile);
                var datos = JsonSerializer.Deserialize<Dictionary<string, string>>(contenido);
                if (datos is not null)
                {
                    foreach (var (k, v) in datos) _perfil[k] = v;
                }

                Console.WriteLine($"\n📂 [MEMORIA CARGADA] desde {MemoryFile}");
                Console.WriteLine(_perfil.Count > 0
                    ? $"   🧠 Perfil restaurado: {Resumen()}"
                    : "   📋 El archivo existe pero el perfil está vacío");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"\n⚠️  [ERROR AL CARGAR] {MemoryFile}: {ex.Message}");
            }
        }

        private void GuardarPerfil()
        {
            try
            {
                File.WriteAllText(MemoryFile, JsonSerializer.Serialize(_perfil, s_json));
                Console.WriteLine($"   💾 [GUARDADO EN DISCO] {MemoryFile}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"   ⚠️  [ERROR AL GUARDAR] {MemoryFile}: {ex.Message}");
            }
        }

        private string Resumen() => string.Join(", ", _perfil.Select(p => $"{p.Key}={p.Value}"));

        public void MostrarPerfil(string titulo)
        {
            Console.WriteLine($"\n{titulo}");
            if (_perfil.Count == 0)
            {
                Console.WriteLine("   (La IA todavía no ha aprendido nada de ti)");
            }
            else
            {
                foreach (var (clave, valor) in _perfil) Console.WriteLine($"   • {clave}: {valor}");
            }
            Console.WriteLine();
        }

        // ------------------------------------------- ganchos del framework --

        /// <summary>ANTES del modelo: inyecta el perfil como instrucciones adicionales.</summary>
        protected override ValueTask<AIContext> ProvideAIContextAsync(
            InvokingContext context, CancellationToken cancellationToken = default)
        {
            if (_perfil.Count == 0) return new ValueTask<AIContext>(new AIContext());

            Console.WriteLine("\n   💭 [INYECTANDO MEMORIA DE LARGO PLAZO]");
            Console.WriteLine($"   📋 Perfil: {Resumen()}\n");

            string lineas = string.Join("\n", _perfil.Select(p => $"- {p.Key}: {p.Value}"));

            return new ValueTask<AIContext>(new AIContext
            {
                Instructions =
                    $"""
                     [PERFIL DEL USUARIO - MEMORIA DE LARGO PLAZO]:
                     {lineas}

                     IMPORTANTE: esta información sobre el usuario persiste entre conversaciones.
                     Menciónala con naturalidad cuando venga al caso y saluda con entusiasmo si lo reconoces.
                     """
            });
        }

        /// <summary>DESPUÉS del modelo: la IA decide qué merece recordarse.</summary>
        protected override async ValueTask StoreAIContextAsync(
            InvokedContext context, CancellationToken cancellationToken = default)
        {
            // Si el run falló, no hay nada que aprender.
            if (context.InvokeException is not null) return;

            // Buscamos el último mensaje del usuario en esta invocación.
            string mensajeUsuario = context.RequestMessages
                .LastOrDefault(m => m.Role == ChatRole.User)?.Text ?? "";

            if (mensajeUsuario.Trim().Length < 3) return;

            Console.WriteLine($"\n   🤖 [IA ANALIZANDO]: '{mensajeUsuario}'");

            string perfilActual = _perfil.Count > 0 ? Resumen() : "vacío";
            string prompt =
                $"""
                 Extrae datos personales duraderos del mensaje del usuario.

                 Mensaje: "{mensajeUsuario}"
                 Perfil actual: {perfilActual}

                 Reglas:
                 - Solo datos factuales del usuario: nombre, edad, profesión, gustos, aficiones...
                 - Solo lo NUEVO o lo que haya CAMBIADO respecto del perfil actual.
                 - Si el mensaje no aporta nada personal (ej. "¿cómo estás?"), devuelve la lista vacía.
                 - Valores breves, claves en snake_case.
                 """;

            try
            {
                // Llamada de un solo turno con SALIDA ESTRUCTURADA: el genérico
                // <PerfilExtraido> hace que el framework pida y valide ese esquema,
                // en vez de parsear JSON a mano desde el texto.
                ChatResponse<PerfilExtraido> respuesta =
                    await _chatClient.GetResponseAsync<PerfilExtraido>(prompt, cancellationToken: cancellationToken);

                if (!respuesta.TryGetResult(out PerfilExtraido? extraido) || extraido.Datos.Count == 0)
                {
                    return;
                }

                foreach (DatoPerfil dato in extraido.Datos)
                {
                    if (string.IsNullOrWhiteSpace(dato.Clave)) continue;
                    _perfil[dato.Clave] = dato.Valor;
                    Console.WriteLine($"   💾 [IA APRENDIÓ] {dato.Clave} = {dato.Valor}");
                }

                GuardarPerfil();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"   ⚠️  [ERROR DE EXTRACCIÓN] {ex.Message}");
            }
        }
    }
}
