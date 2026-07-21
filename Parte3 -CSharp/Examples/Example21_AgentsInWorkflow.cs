using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;
using MFA.CSharp.Part3.Infrastructure;
using static MFA.CSharp.Part3.Infrastructure.InvoiceUtils;

namespace MFA.CSharp.Part3.Examples;

/// <summary>
/// 21 · AGENTES DE IA dentro de un WORKFLOW.
/// Equivalente C# de <c>new_21_agents_in_workflow.py</c>.
///
/// <para><b>Objetivo pedagógico:</b> cierre de la serie. Hasta ahora los ejecutores
/// hacían cálculo determinista; aquí CUATRO de ellos delegan su trabajo en un
/// <b>agente de IA</b> distinto, cada uno con su especialidad. El grafo es el mismo
/// de siempre; lo que cambia es quién decide.</para>
///
/// <code>
/// Selector ─► Analista ─► Decisor ─► Comunicador ─► Resumidor
/// (código)     (IA)        (IA)         (IA)          (IA)
/// </code>
///
/// <para>⚠️ <b>ESTE EJEMPLO ES DIFERENTE A LOS ANTERIORES.</b> Es el ÚNICO de la
/// Parte 3 que llama a un modelo de verdad. Implica que:</para>
/// <list type="bullet">
///   <item>Necesita credenciales de Azure OpenAI en <c>appsettings03.json</c>.</item>
///   <item>Tarda bastante más (son 4 llamadas al modelo, una por agente).</item>
///   <item>Sus respuestas NO son deterministas: dos ejecuciones no dan lo mismo.</item>
///   <item>Consume cuota del modelo.</item>
/// </list>
/// <para>Los ejemplos 16-20 son cálculo local puro y no necesitan nada de esto.</para>
///
/// <para><b>Conceptos clave:</b></para>
/// <list type="number">
///   <item>UN AGENTE ES UN EJECUTOR MÁS. No hay clase especial: un <c>Executor</c>
///   corriente que, dentro de su handler, llama a <c>agent.RunAsync(prompt)</c>.</item>
///   <item>UN CLIENTE, VARIOS AGENTES: se crea UN solo <c>IChatClient</c> y se
///   comparte entre los cuatro. Lo que los diferencia son sus instrucciones.</item>
///   <item>LA SALIDA DE UN AGENTE ALIMENTA AL SIGUIENTE: el análisis condiciona la
///   decisión, la decisión condiciona la comunicación, y todo acaba en el resumen.</item>
/// </list>
///
/// <para>🔴 <b>DIFERENCIA CON PYTHON:</b> la versión de Python usa Azure AI Foundry
/// (<c>FoundryChatClient</c> + <c>az login</c>). Aquí se usa <b>Azure OpenAI directo
/// con API key</b>, igual que en la Parte 2 de C#, para mantener un único patrón de
/// autenticación en todo el proyecto .NET. El objetivo pedagógico es idéntico.</para>
/// </summary>
internal static partial class Example21_AgentsInWorkflow
{
    // =====================================================================
    // MENSAJE QUE VIAJA POR EL GRAFO
    // =====================================================================
    // Los ejemplos anteriores encadenaban records cada vez más grandes. Aquí se
    // usa UNO que va acumulando el trabajo de cada agente. Es mutable mediante
    // `with`, así cada paso añade su parte sin destruir lo anterior.

    internal sealed record ExpedienteFactura(
        InvoiceData Invoice,
        InvoiceTotals Totals,
        string Analisis = "",            // lo escribe el Analista
        string NivelRiesgo = "medio",    // se deduce del análisis
        string Decision = "",            // lo escribe el Decisor
        string ViaProcesamiento = "",    // se deduce de la decisión
        string Comunicacion = "",        // lo escribe el Comunicador
        string Resumen = "");            // lo escribe el Resumidor

    // =====================================================================
    // INSTRUCCIONES DE CADA AGENTE
    // =====================================================================
    // Lo ÚNICO que distingue a los cuatro agentes. Todas piden responder EN
    // ESPAÑOL: sin esa indicación el modelo tiende a contestar en inglés.

    private const string InstruccionesAnalista = """
        Eres un analista financiero experto en facturación.
        Analiza los datos de la factura y aporta:
        1. Observaciones de negocio sobre el cliente y la operación
        2. Evaluación de riesgo (bajo / medio / alto)
        3. Recomendaciones para su procesamiento
        4. Cualquier patrón inusual o motivo de preocupación

        Responde SIEMPRE en español, de forma concisa y estructurada.
        """;

    private const string InstruccionesDecisor = """
        Eres un responsable de decisiones de negocio en facturación.
        Según los datos y el análisis recibido, decide la acción a tomar:

        1. APROBAR   : procesamiento estándar
        2. PRIORIDAD : procesamiento acelerado
        3. REVISAR   : requiere revisión manual
        4. RETENER   : retener temporalmente el procesamiento

        Ten en cuenta: categoría del cliente, importe, nivel de riesgo y reglas de negocio.
        Empieza tu respuesta con la palabra de la acción elegida en MAYÚSCULAS y explica
        brevemente el motivo. Responde SIEMPRE en español.
        """;

    private const string InstruccionesComunicador = """
        Eres un especialista en comunicación con clientes.
        Redactas mensajes profesionales y cercanos: acuses de recibo de facturas, avisos
        de pago, agradecimientos y ofertas para clientes preferentes.

        Ajusta el tono a la relación con el cliente. Responde SIEMPRE en español, de
        forma breve y profesional.
        """;

    private const string InstruccionesResumidor = """
        Eres un asistente de dirección que redacta resúmenes ejecutivos.
        Incluye:
        1. Datos clave de la operación
        2. Decisiones de negocio tomadas
        3. Observaciones sobre el cliente
        4. Próximos pasos o recomendaciones

        Responde SIEMPRE en español, en tono profesional y accionable.
        """;

    // =====================================================================
    // AYUDA COMPARTIDA POR LOS EJECUTORES CON IA
    // =====================================================================
    // Los cuatro hacen lo mismo: construir un prompt, llamar al agente y guardar
    // el texto. Se factoriza aquí para no repetir cuatro veces la misma fontanería.

    /// <summary>Llama al agente y devuelve su respuesta en texto.</summary>
    private static async Task<string> PreguntarAsync(AIAgent agente, string nombre, string prompt,
                                                     CancellationToken ct)
    {
        Console.WriteLine($"🤖 Agente '{nombre}' trabajando...");
        // AgentResponse expone .Text (el texto plano) además de .Messages y .Usage
        AgentResponse respuesta = await agente.RunAsync(prompt, cancellationToken: ct);
        return respuesta.Text;
    }

    /// <summary>Imprime la respuesta del agente enmarcada, para que se lea bien.</summary>
    private static void Mostrar(string titulo, string texto)
    {
        Console.WriteLine($"\n{titulo}");
        Console.WriteLine(new string('-', 80));
        Console.WriteLine(texto);
        Console.WriteLine(new string('-', 80));
    }

    // =====================================================================
    // PASO 1 — ENTRADA del grafo (SIN IA)
    // =====================================================================
    // Ejecutor tradicional: solo lee el CSV y deja elegir la factura. Se incluye
    // a propósito para dejar claro que agentes y código determinista conviven en
    // el mismo grafo.
    internal sealed partial class SelectorFactura(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(ExpedienteFactura)])]
        public async ValueTask HandleAsync(string senal, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(1, "SELECCIONAR FACTURA");

            EnsureDirectories(OutputDir, LogsDir);

            var config = InvoiceConfig.Load();
            List<InvoiceData> todas = ReadInvoicesCsv();
            Console.WriteLine($"Se cargaron {todas.Count} facturas");

            InvoiceData elegida = ShowMenu(todas);
            InvoiceTotals totales = CalculateInvoiceTotals(elegida, config);

            Console.WriteLine($"\nSeleccionada: {elegida.InvoiceId} - {elegida.ClientName}");
            Console.WriteLine($"   Importe: {Money(elegida.Subtotal)}");
            Console.WriteLine($"   Total con impuestos y descuentos: {Money(totales.Total)}");
            Console.WriteLine($"   Cliente preferente: {(elegida.IsPreferred ? "SI" : "NO")}");

            LogAction($"Factura {elegida.InvoiceId} seleccionada para proceso con agentes");

            await context.SendMessageAsync(new ExpedienteFactura(elegida, totales), ct);
        }
    }

    // =====================================================================
    // PASO 2 — PRIMER AGENTE: analiza la factura y evalúa el riesgo
    // =====================================================================
    internal sealed partial class AgenteAnalista(string id, AIAgent agente) : Executor(id)
    {
        [MessageHandler(Send = [typeof(ExpedienteFactura)])]
        public async ValueTask HandleAsync(ExpedienteFactura exp, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(2, "ANALISIS POR AGENTE");

            var config = InvoiceConfig.Load();
            InvoiceData inv = exp.Invoice;
            InvoiceTotals t = exp.Totals;

            string prompt = $"""
                Analiza esta factura:

                Factura: {inv.InvoiceId}
                Cliente: {inv.ClientName} ({inv.ClientEmail})
                Concepto: {inv.ItemDescription}
                Cantidad: {inv.Quantity}
                Precio unitario: {Money(inv.UnitPrice)}
                Subtotal: {Money(inv.Subtotal)}
                Cliente preferente: {(inv.IsPreferred ? "Si" : "No")}
                Fecha: {inv.Date}

                Importes calculados:
                - Descuento por alto valor: {Money(t.HighValueDiscount)}
                - Descuento cliente preferente: {Money(t.PreferredDiscount)}
                - Impuesto: {Money(t.Tax)}
                - Total a pagar: {Money(t.Total)}

                Reglas de negocio:
                - Umbral de alto valor: {Money(config.HighValueThreshold)}
                - Tasa de impuesto: {Pct(config.TaxRate)}
                - Descuento por alto valor: {Pct(config.HighValueDiscount)}
                - Descuento cliente preferente: {Pct(config.PreferredClientDiscount)}

                Entrega tu análisis de forma estructurada.
                """;

            string analisis = await PreguntarAsync(agente, "Analista", prompt, ct);
            Mostrar("📊 Análisis del agente:", analisis);

            // Se extrae una etiqueta de riesgo del texto libre para que el resto del
            // workflow pueda usarla. Es deliberadamente simple: el objetivo es
            // mostrar cómo se aterriza una respuesta de IA a un valor manejable.
            string texto = analisis.ToLowerInvariant();
            string riesgo = texto.Contains("riesgo alto") || texto.Contains("alto riesgo") ? "alto"
                          : texto.Contains("riesgo bajo") || texto.Contains("bajo riesgo") ? "bajo"
                          : "medio";

            Console.WriteLine($"\n   Nivel de riesgo detectado: {riesgo.ToUpperInvariant()}");
            LogAction($"Agente analizó {inv.InvoiceId}: riesgo={riesgo}");

            await context.SendMessageAsync(exp with { Analisis = analisis, NivelRiesgo = riesgo }, ct);
        }
    }

    // =====================================================================
    // PASO 3 — SEGUNDO AGENTE: decide qué hacer con la factura
    // =====================================================================
    internal sealed partial class AgenteDecisor(string id, AIAgent agente) : Executor(id)
    {
        [MessageHandler(Send = [typeof(ExpedienteFactura)])]
        public async ValueTask HandleAsync(ExpedienteFactura exp, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(3, "DECISION POR AGENTE");

            var config = InvoiceConfig.Load();
            InvoiceData inv = exp.Invoice;

            // El prompt incluye el ANÁLISIS del agente anterior: así se encadena el
            // trabajo de un agente con el siguiente.
            string prompt = $"""
                Decide cómo procesar esta factura:

                Factura: {inv.InvoiceId}
                Cliente: {inv.ClientName} (preferente: {(inv.IsPreferred ? "Si" : "No")})
                Importe total: {Money(exp.Totals.Total)}
                Nivel de riesgo: {exp.NivelRiesgo}

                Análisis previo del analista:
                {Recortar(exp.Analisis, 600)}

                Reglas de negocio:
                - Umbral de alto valor: {Money(config.HighValueThreshold)}
                - Los clientes preferentes tienen prioridad
                - Un riesgo alto exige revisión manual

                Elige entre: APROBAR, PRIORIDAD, REVISAR o RETENER, y justifica brevemente.
                """;

            string decision = await PreguntarAsync(agente, "Decisor", prompt, ct);
            Mostrar("⚖️  Decisión del agente:", decision);

            // Se busca la palabra clave en el texto para elegir la vía. El orden
            // importa: se comprueban primero las más específicas.
            string mayus = decision.ToUpperInvariant();
            string via = mayus.Contains("PRIORIDAD") ? "prioridad"
                       : mayus.Contains("REVISAR") ? "revision"
                       : mayus.Contains("RETENER") ? "retenida"
                       : "estandar";

            Console.WriteLine($"\n   Vía de procesamiento: {via.ToUpperInvariant()}");
            LogAction($"Agente decidió vía '{via}' para {inv.InvoiceId}");

            await context.SendMessageAsync(exp with { Decision = decision, ViaProcesamiento = via }, ct);
        }
    }

    // =====================================================================
    // PASO 4 — TERCER AGENTE: redacta el mensaje para el cliente
    // =====================================================================
    internal sealed partial class AgenteComunicador(string id, AIAgent agente) : Executor(id)
    {
        [MessageHandler(Send = [typeof(ExpedienteFactura)])]
        public async ValueTask HandleAsync(ExpedienteFactura exp, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(4, "COMUNICACION POR AGENTE");

            InvoiceData inv = exp.Invoice;

            string prompt = $"""
                Redacta un correo de acuse de recibo para este cliente:

                Datos del cliente:
                - Nombre: {inv.ClientName}
                - Email: {inv.ClientEmail}
                - Cliente preferente: {(inv.IsPreferred ? "Si" : "No")}

                Datos de la factura:
                - Factura: {inv.InvoiceId}
                - Concepto: {inv.ItemDescription}
                - Importe: {Money(exp.Totals.Total)}
                - Fecha: {inv.Date}
                - Vía de procesamiento decidida: {exp.ViaProcesamiento}

                Incluye: saludo personalizado, resumen de la factura, cualquier nota especial
                según su categoría y la decisión tomada, y una despedida profesional.
                Que sea breve y cercano.
                """;

            string comunicacion = await PreguntarAsync(agente, "Comunicador", prompt, ct);
            Mostrar("📧 Comunicación generada:", comunicacion);

            LogAction($"Agente generó comunicación para {inv.InvoiceId}");

            await context.SendMessageAsync(exp with { Comunicacion = comunicacion }, ct);
        }
    }

    // =====================================================================
    // PASO 5 — CUARTO AGENTE y TERMINAL del grafo
    // =====================================================================
    // Resume todo, guarda el informe y cierra el workflow.
    internal sealed partial class AgenteResumidor(string id, AIAgent agente) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(ExpedienteFactura exp, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(5, "RESUMEN EJECUTIVO POR AGENTE");

            InvoiceData inv = exp.Invoice;

            string prompt = $"""
                Redacta un resumen ejecutivo del procesamiento de esta factura:

                Factura: {inv.InvoiceId}
                Cliente: {inv.ClientName}
                Importe total: {Money(exp.Totals.Total)}
                Vía de procesamiento: {exp.ViaProcesamiento}
                Nivel de riesgo: {exp.NivelRiesgo}

                Análisis del analista:
                {Recortar(exp.Analisis, 400)}

                Decisión tomada:
                {Recortar(exp.Decision, 400)}

                Se generó además una comunicación para el cliente.

                Destaca los puntos clave y los resultados.
                """;

            string resumen = await PreguntarAsync(agente, "Resumidor", prompt, ct);
            Mostrar("📋 Resumen ejecutivo:", resumen);

            // El informe reúne el trabajo de los CUATRO agentes en un solo documento
            string informe = $"""

                RESUMEN EJECUTIVO - FACTURA {inv.InvoiceId}
                {new string('=', 80)}

                DATOS DEL CLIENTE:
                - Nombre: {inv.ClientName}
                - Email: {inv.ClientEmail}
                - Cliente preferente: {(inv.IsPreferred ? "Si" : "No")}

                DATOS ECONOMICOS:
                - Subtotal: {Money(exp.Totals.Subtotal)}
                - Total a pagar: {Money(exp.Totals.Total)}
                - Via de procesamiento: {exp.ViaProcesamiento}
                - Nivel de riesgo: {exp.NivelRiesgo}

                ANALISIS DEL AGENTE:
                {exp.Analisis}

                DECISION DEL AGENTE:
                {exp.Decision}

                COMUNICACION AL CLIENTE:
                {exp.Comunicacion}

                RESUMEN EJECUTIVO:
                {resumen}

                {new string('=', 80)}
                """;

            string ruta = SaveInvoiceFile($"{inv.InvoiceId}_informe_agentes", informe);
            Console.WriteLine($"\n💾 Informe guardado en: {ruta}");

            LogAction($"Workflow con agentes completado para {inv.InvoiceId}");

            await context.YieldOutputAsync(
                $"✅ ¡Workflow con agentes completado! Factura {inv.InvoiceId} procesada con IA " +
                $"(vía: {exp.ViaProcesamiento}, riesgo: {exp.NivelRiesgo}).", ct);
        }
    }

    /// <summary>Recorta un texto largo para no inflar el prompt del siguiente agente.</summary>
    private static string Recortar(string texto, int max)
        => texto.Length <= max ? texto : texto[..max] + "...";

    // =====================================================================
    // PUNTO DE ENTRADA
    // =====================================================================

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("🤖 AGENTES DENTRO DE WORKFLOWS - GENERADOR DE FACTURAS");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("\n✨ Esta demo integra AGENTES DE IA en los pasos del workflow:");
        Console.WriteLine("   • Un agente analiza la factura y evalúa el riesgo");
        Console.WriteLine("   • Un agente decide cómo procesarla");
        Console.WriteLine("   • Un agente redacta la comunicación al cliente");
        Console.WriteLine("   • Un agente elabora el resumen ejecutivo");
        Console.WriteLine("\n🔄 Patrón del workflow:");
        Console.WriteLine("   Seleccionar → Analizar → Decidir → Comunicar → Resumir");
        Console.WriteLine("     (código)      (IA)      (IA)       (IA)       (IA)");
        Console.WriteLine("\n⚠️  A diferencia de los ejemplos 16-20, este SÍ llama a un modelo real:");
        Console.WriteLine("   requiere credenciales, tarda más y sus respuestas varían en cada ejecución.");
        Console.WriteLine(new string('=', 80));

        // Comprobación de configuración ANTES de intentar conectarse: así el error
        // es claro en vez de una excepción críptica del SDK.
        if (!AzureAgentFactory.IsConfigured())
        {
            Console.WriteLine("\n❌ Falta configuración de Azure OpenAI en appsettings03.json");
            Console.WriteLine("   Se necesitan: AzureOpenAI:Endpoint, AzureOpenAI:ChatDeploymentName y AzureOpenAI:ApiKey");
            return;
        }

        try
        {
            // UN cliente compartido por los cuatro agentes; lo que los distingue
            // son sus instrucciones.
            IChatClient chatClient = AzureAgentFactory.CreateChatClient();

            var selector = new SelectorFactura("selector");
            var analista = new AgenteAnalista("analista",
                AzureAgentFactory.CreateAgent(chatClient, "Analista", InstruccionesAnalista));
            var decisor = new AgenteDecisor("decisor",
                AzureAgentFactory.CreateAgent(chatClient, "Decisor", InstruccionesDecisor));
            var comunicador = new AgenteComunicador("comunicador",
                AzureAgentFactory.CreateAgent(chatClient, "Comunicador", InstruccionesComunicador));
            var resumidor = new AgenteResumidor("resumidor",
                AzureAgentFactory.CreateAgent(chatClient, "Resumidor", InstruccionesResumidor));

            // La topología es una CADENA LINEAL idéntica a la del ejemplo 16:
            // meter agentes en un workflow no cambia cómo se construye el grafo.
            Workflow workflow = new WorkflowBuilder(selector)
                .AddEdge(selector, analista)
                .AddEdge(analista, decisor)
                .AddEdge(decisor, comunicador)
                .AddEdge(comunicador, resumidor)
                .WithOutputFrom(resumidor)
                .WithName("facturacion_con_agentes")
                .Build();

            StreamingRun run = await InProcessExecution.RunStreamingAsync(workflow, "start");

            await foreach (WorkflowEvent evt in run.WatchStreamAsync())
            {
                if (evt is WorkflowOutputEvent salida)
                {
                    Console.WriteLine("\n" + new string('=', 80));
                    Console.WriteLine("🎉 WORKFLOW CON AGENTES COMPLETADO");
                    Console.WriteLine(new string('=', 80));
                    Console.WriteLine(salida.Data);
                    Console.WriteLine("\n📁 Revise los siguientes directorios:");
                    Console.WriteLine($"   • Salida: {OutputDir}");
                    Console.WriteLine($"   • Registros: {LogsDir}");
                    Console.WriteLine("\n🤖 Este workflow usó agentes de IA para:");
                    Console.WriteLine("   • Analizar la factura y evaluar el riesgo");
                    Console.WriteLine("   • Decidir la vía de procesamiento");
                    Console.WriteLine("   • Redactar la comunicación al cliente");
                    Console.WriteLine("   • Elaborar el resumen ejecutivo");
                    Console.WriteLine(new string('=', 80));
                }
                else if (evt is ExecutorFailedEvent fallo)
                {
                    Console.WriteLine($"\n❌ Falló un ejecutor: {fallo.Data}");
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"\n❌ Error al ejecutar el workflow con agentes: {ex.GetType().Name}");
            Console.WriteLine($"   {ex.Message}");
            Console.WriteLine("\n   Comprobaciones:");
            Console.WriteLine("   • ¿Es correcto AzureOpenAI:Endpoint? Debe ser SOLO la base, sin /openai/...");
            Console.WriteLine("   • ¿La API key es válida y no ha caducado?");
            Console.WriteLine("   • ¿Está desplegado el modelo indicado en ChatDeploymentName?");
        }
    }
}
