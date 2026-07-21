using System.Diagnostics;
using Microsoft.Agents.AI.Workflows;
using MFA.CSharp.Part3.Infrastructure;
using static MFA.CSharp.Part3.Infrastructure.InvoiceUtils;

namespace MFA.CSharp.Part3.Examples;

/// <summary>
/// 17 · Workflow CONCURRENTE (fan-out / fan-in).
/// Equivalente C# de <c>new_17_concurrent_workflow.py</c>.
///
/// <para><b>Objetivo pedagógico:</b> pasar de la cadena lineal del ejemplo 16 a un
/// grafo que ejecuta trabajo EN PARALELO y luego lo reúne.</para>
///
/// <code>
/// Dispatcher ─┬─► CalculadoraTotales ──┐
///             ├─► PreparadorCliente  ──┼─► Fusionador ─► Renderizador
///             └─► VerificadorCredito ──┘
/// </code>
///
/// <para><b>Conceptos clave:</b></para>
/// <list type="number">
///   <item><b>FAN-OUT</b> (<c>AddFanOutEdge</c>): un ejecutor difunde el MISMO mensaje
///   a varios destinos, que se ejecutan CONCURRENTEMENTE.</item>
///   <item><b>FAN-IN</b> (<c>AddFanInBarrierEdge</c>): varias aristas convergen en un
///   destino con SINCRONIZACIÓN AUTOMÁTICA — la "barrera" espera a que TODOS los
///   orígenes terminen y entrega sus mensajes juntos, en una LISTA.</item>
///   <item>La concurrencia es REAL: las tres tareas tardan 0.1s, 0.5s y 0.8s. En
///   secuencia serían ~1.4s; en paralelo el bloque tarda ~0.8s. El ejemplo lo mide.</item>
/// </list>
///
/// <para><b>NOTA:</b> este ejemplo NO usa ningún LLM — es cálculo local puro.</para>
/// </summary>
internal static partial class Example17_ConcurrentWorkflow
{
    // =====================================================================
    // CONSTANTES DE TIEMPO
    // =====================================================================
    // Duración simulada de cada tarea paralela. En secuencia sumarían 1.4 s;
    // ejecutándose en paralelo el bloque debe tardar ~0.8 s, la más lenta.
    private static readonly TimeSpan DuracionTotales = TimeSpan.FromSeconds(0.1);
    private static readonly TimeSpan DuracionCliente = TimeSpan.FromSeconds(0.5);
    private static readonly TimeSpan DuracionCredito = TimeSpan.FromSeconds(0.8);
    private static readonly TimeSpan DuracionSecuencial = DuracionTotales + DuracionCliente + DuracionCredito;

    // Cronómetro para DEMOSTRAR que el paralelismo es real. Arranca justo antes
    // del fan-out y se lee en el fusionador, de modo que mide SOLO el bloque
    // concurrente y no incluye las pausas interactivas.
    private static Stopwatch? s_cronometro;

    // =====================================================================
    // MENSAJES QUE VIAJAN POR EL GRAFO
    // =====================================================================

    internal sealed record FacturaConConfig(InvoiceData Invoice, InvoiceConfig Config);
    internal sealed record ResultadoTotales(string InvoiceId, InvoiceTotals Totals);
    internal sealed record ResultadoCliente(string InvoiceId, FichaCliente Info);
    internal sealed record ResultadoCredito(string InvoiceId, EvaluacionCredito Credito);

    /// <summary>Ficha comercial del cliente (la arma la tarea paralela 2).</summary>
    internal sealed record FichaCliente(string Nombre, string Email, bool EsPreferente,
                                        string Categoria, string Saludo, string GestorCuenta,
                                        string UltimoPedido);

    /// <summary>Resultado de la verificación de crédito (tarea paralela 3).</summary>
    internal sealed record EvaluacionCredito(int Puntuacion, decimal Limite, string Riesgo,
                                             bool Aprobado, decimal ImporteFactura,
                                             decimal CreditoDisponible, string FechaVerificacion);

    /// <summary>Fusión de las tres ramas paralelas + los datos originales.</summary>
    internal sealed record ResultadoFusionado(InvoiceData Invoice, InvoiceConfig Config,
                                              InvoiceTotals Totals, FichaCliente Cliente,
                                              EvaluacionCredito Credito);

    // =====================================================================
    // PUNTO DE FAN-OUT
    // =====================================================================
    // Carga los datos, deja elegir factura y difunde el MISMO mensaje a las tres
    // tareas, que a partir de ahí corren en paralelo.
    internal sealed partial class Dispatcher(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(FacturaConConfig)])]
        public async ValueTask HandleAsync(string senal, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(1, "CARGAR Y SELECCIONAR FACTURA");

            // Los directorios se crean AQUÍ: este mismo paso ya escribe en logs/
            EnsureDirectories(OutputDir, LogsDir);

            var config = InvoiceConfig.Load();
            List<InvoiceData> todas = ReadInvoicesCsv();
            Console.WriteLine($"Se cargaron {todas.Count} facturas");

            InvoiceData elegida = ShowMenu(todas);

            Console.WriteLine($"\nSeleccionada: {elegida.InvoiceId} - {elegida.ClientName}");
            Console.WriteLine($"   Importe: {Money(elegida.Subtotal)}");
            Console.WriteLine($"   Preferente: {(elegida.IsPreferred ? "SI" : "NO")}");

            LogAction($"Factura {elegida.InvoiceId} seleccionada para proceso paralelo");
            WaitForUser("iniciar el proceso EN PARALELO");

            // Cronómetro DESPUÉS de la pausa interactiva: así el tiempo medido es
            // solo el del trabajo concurrente, sin contar lo que tarde el usuario.
            s_cronometro = Stopwatch.StartNew();

            await context.SendMessageAsync(new FacturaConConfig(elegida, config), ct);
        }
    }

    // =====================================================================
    // TAREA PARALELA 1 — reglas de negocio (descuentos + impuesto)
    // =====================================================================
    // Corre a la vez que PreparadorCliente y VerificadorCredito: ninguna espera a la otra.
    internal sealed partial class CalculadoraTotales(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(ResultadoTotales)])]
        public async ValueTask HandleAsync(FacturaConConfig msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine($"\n[TOTALES] Calculando totales de {msg.Invoice.InvoiceId}...");

            await Task.Delay(DuracionTotales, ct);   // simula tiempo de proceso

            InvoiceTotals t = CalculateInvoiceTotals(msg.Invoice, msg.Config);

            Console.WriteLine("   ¡Cálculo completado!");
            Console.WriteLine($"      Subtotal: {Money(t.Subtotal)}");
            Console.WriteLine($"      Descuentos: -{Money(t.TotalDiscount)}");
            Console.WriteLine($"      Impuesto: {Money(t.Tax)}");
            Console.WriteLine($"      Total: {Money(t.Total)}");

            await context.SendMessageAsync(new ResultadoTotales(msg.Invoice.InvoiceId, t), ct);
        }
    }

    // =====================================================================
    // TAREA PARALELA 2 — ficha comercial del cliente
    // =====================================================================
    // No depende de los importes, por eso puede correr a la vez que el cálculo.
    internal sealed partial class PreparadorCliente(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(ResultadoCliente)])]
        public async ValueTask HandleAsync(FacturaConConfig msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine($"\n[CLIENTE] Preparando ficha de cliente de {msg.Invoice.InvoiceId}...");

            await Task.Delay(DuracionCliente, ct);

            InvoiceData inv = msg.Invoice;
            var ficha = new FichaCliente(
                Nombre: inv.ClientName,
                Email: inv.ClientEmail,
                EsPreferente: inv.IsPreferred,
                Categoria: inv.IsPreferred ? "VIP" : "Estandar",
                Saludo: $"Estimado/a {inv.ClientName}:",
                GestorCuenta: $"GC-{inv.ClientName[..Math.Min(3, inv.ClientName.Length)].ToUpperInvariant()}",
                UltimoPedido: inv.IsPreferred ? "2024-12-01" : "2024-11-15");

            Console.WriteLine("   ¡Ficha de cliente lista!");
            Console.WriteLine($"      Nombre: {ficha.Nombre}");
            Console.WriteLine($"      Categoría: {ficha.Categoria}");
            Console.WriteLine($"      Gestor de cuenta: {ficha.GestorCuenta}");

            await context.SendMessageAsync(new ResultadoCliente(inv.InvoiceId, ficha), ct);
        }
    }

    // =====================================================================
    // TAREA PARALELA 3 — verificación de crédito (la más lenta: 0.8 s)
    // =====================================================================
    // Al ser la más lenta, es la que marca la duración total del bloque paralelo.
    internal sealed partial class VerificadorCredito(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(ResultadoCredito)])]
        public async ValueTask HandleAsync(FacturaConConfig msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine($"\n[CREDITO] Verificando crédito de {msg.Invoice.InvoiceId}...");

            await Task.Delay(DuracionCredito, ct);

            InvoiceData inv = msg.Invoice;
            decimal importe = inv.Subtotal;

            // Lógica de scoring: cliente preferente > factura alta > resto
            (int puntuacion, decimal limite, string riesgo) = inv.IsPreferred
                ? (850, 50000m, "BAJO")
                : importe > 5000m
                    ? (720, 25000m, "MEDIO")
                    : (650, 10000m, "MEDIO");

            // ¿Cabe el importe dentro del límite de crédito?
            bool aprobado = importe <= limite;

            var credito = new EvaluacionCredito(
                Puntuacion: puntuacion,
                Limite: limite,
                Riesgo: riesgo,
                Aprobado: aprobado,
                ImporteFactura: importe,
                CreditoDisponible: aprobado ? limite - importe : 0m,
                FechaVerificacion: DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ssZ"));

            Console.WriteLine("   ¡Verificación de crédito completada!");
            Console.WriteLine($"      Estado: {(aprobado ? "APROBADO" : "RECHAZADO")}");
            Console.WriteLine($"      Puntuación: {puntuacion}");
            Console.WriteLine($"      Límite: {MoneyGrouped(limite)}");
            Console.WriteLine($"      Riesgo: {riesgo}");

            await context.SendMessageAsync(new ResultadoCredito(inv.InvoiceId, credito), ct);
        }
    }

    // =====================================================================
    // PUNTO DE FAN-IN
    // =====================================================================
    // 🔴 DIFERENCIA IMPORTANTE CON PYTHON
    // -----------------------------------
    // En Python, `add_fan_in_edges` AGREGA los mensajes y el handler recibe una
    // LISTA de una sola vez:
    //
    //     async def merge(self, results: list[...], ctx): ...
    //
    // En .NET, `AddFanInBarrierEdge` **sincroniza pero NO agrega**: espera a que
    // todos los orígenes terminen y entonces entrega CADA MENSAJE POR SEPARADO,
    // con su tipo original. Por eso aquí hay un handler por tipo y el ejecutor
    // ACUMULA en campos hasta tenerlos todos.
    //
    // Consecuencia práctica: el estado de instancia vuelve a ser necesario en C#,
    // mientras que en Python se pudo eliminar. Se reinicia tras cada fusión para
    // que una segunda ejecución no arrastre residuos.
    internal sealed partial class Fusionador(string id) : Executor(id)
    {
        private FacturaConConfig? _original;
        private ResultadoTotales? _totales;
        private ResultadoCliente? _cliente;
        private ResultadoCredito? _credito;

        [MessageHandler(Send = [typeof(ResultadoFusionado)])]
        public async ValueTask HandleOriginalAsync(FacturaConConfig msg, IWorkflowContext context,
                                                   CancellationToken ct = default)
        {
            _original = msg;
            await IntentarFusionarAsync(context, ct);
        }

        [MessageHandler(Send = [typeof(ResultadoFusionado)])]
        public async ValueTask HandleTotalesAsync(ResultadoTotales msg, IWorkflowContext context,
                                                  CancellationToken ct = default)
        {
            _totales = msg;
            Console.WriteLine($"   [FUSION] TOTALES de {msg.InvoiceId}");
            await IntentarFusionarAsync(context, ct);
        }

        [MessageHandler(Send = [typeof(ResultadoFusionado)])]
        public async ValueTask HandleClienteAsync(ResultadoCliente msg, IWorkflowContext context,
                                                  CancellationToken ct = default)
        {
            _cliente = msg;
            Console.WriteLine($"   [FUSION] FICHA DE CLIENTE de {msg.InvoiceId}");
            await IntentarFusionarAsync(context, ct);
        }

        [MessageHandler(Send = [typeof(ResultadoFusionado)])]
        public async ValueTask HandleCreditoAsync(ResultadoCredito msg, IWorkflowContext context,
                                                  CancellationToken ct = default)
        {
            _credito = msg;
            Console.WriteLine($"   [FUSION] VERIFICACION DE CREDITO de {msg.InvoiceId}");
            await IntentarFusionarAsync(context, ct);
        }

        /// <summary>
        /// Fusiona SOLO cuando han llegado los cuatro mensajes. La barrera garantiza
        /// que eso ocurre dentro del mismo superstep, pero la comprobación explícita
        /// deja el invariante a la vista.
        /// </summary>
        private async ValueTask IntentarFusionarAsync(IWorkflowContext context, CancellationToken ct)
        {
            if (_original is null || _totales is null || _cliente is null || _credito is null)
                return;   // todavía faltan mensajes

            Console.WriteLine("\n[FUSION] Fan-in completo: llegaron los 4 mensajes");

            // PRUEBA DE QUE EL PARALELISMO ES REAL: si las tres tareas se hubieran
            // ejecutado en secuencia, aquí habrían pasado ~1.4 s.
            if (s_cronometro is not null)
            {
                s_cronometro.Stop();
                TimeSpan transcurrido = s_cronometro.Elapsed;
                TimeSpan ahorro = DuracionSecuencial - transcurrido;
                Console.WriteLine($"   [TIEMPO] Bloque paralelo: {transcurrido.TotalSeconds:0.00}s " +
                                  $"(en secuencia habria tardado {DuracionSecuencial.TotalSeconds:0.00}s " +
                                  $"-> ahorro {ahorro.TotalSeconds:0.00}s)");
                s_cronometro = null;
            }

            Console.WriteLine("[FUSION] Las tres tareas paralelas terminaron: fusionando resultados...");

            var fusionado = new ResultadoFusionado(_original.Invoice, _original.Config,
                                                   _totales.Totals, _cliente.Info, _credito.Credito);

            // Reinicio: permite reejecutar el workflow sin arrastrar residuos
            _original = null; _totales = null; _cliente = null; _credito = null;

            WaitForUser("continuar al RENDERIZADO");

            await context.SendMessageAsync(fusionado, ct);
        }
    }

    // =====================================================================
    // PASO FINAL — TERMINAL del grafo
    // =====================================================================
    internal sealed partial class Renderizador(string id) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(ResultadoFusionado msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(3, "RENDERIZAR Y GUARDAR");

            Console.WriteLine($"Renderizando la factura {msg.Invoice.InvoiceId}...");

            string facturaTexto = RenderInvoiceText(msg.Invoice, msg.Totals, msg.Config);

            EvaluacionCredito c = msg.Credito;
            FichaCliente f = msg.Cliente;

            string bloqueCredito = $"""

                RESULTADO DE LA VERIFICACION DE CREDITO:
                ========================================
                Estado: {(c.Aprobado ? "APROBADO" : "RECHAZADO")}
                Puntuacion de credito: {c.Puntuacion}
                Limite de credito: {MoneyGrouped(c.Limite)}
                Nivel de riesgo: {c.Riesgo}
                Importe de la factura: {MoneyGrouped(c.ImporteFactura)}
                Credito disponible: {MoneyGrouped(c.CreditoDisponible)}
                Fecha de verificacion: {c.FechaVerificacion}

                """;

            string bloqueCliente = $"""

                INFORMACION DEL CLIENTE:
                ========================
                Nombre: {f.Nombre}
                Email: {f.Email}
                Categoria: {f.Categoria}
                Gestor de cuenta: {f.GestorCuenta}
                Ultimo pedido: {f.UltimoPedido}

                """;

            string completo = facturaTexto + bloqueCredito + bloqueCliente;

            Console.WriteLine($"\n{new string('-', 80)}");
            Console.WriteLine("VISTA PREVIA DE LA FACTURA:");
            Console.WriteLine(new string('-', 80));
            Console.WriteLine(completo);
            Console.WriteLine(new string('-', 80));

            string ruta = SaveInvoiceFile(msg.Invoice.InvoiceId, completo);

            Console.WriteLine("\n¡Factura guardada correctamente!");
            Console.WriteLine($"   Ubicación: {ruta}");
            Console.WriteLine($"   Cliente: {f.Nombre} ({f.Categoria})");
            Console.WriteLine($"   Importe: {Money(msg.Totals.Total)}");
            Console.WriteLine($"   Crédito: {(c.Aprobado ? "APROBADO" : "RECHAZADO")} (Puntuación: {c.Puntuacion})");

            LogAction($"Factura {msg.Invoice.InvoiceId} renderizada y guardada " +
                      "(workflow concurrente con verificación de crédito)");

            await context.YieldOutputAsync(
                $"¡Workflow concurrente completado! Factura {msg.Invoice.InvoiceId} " +
                "procesada con 3 tareas en paralelo.", ct);
        }
    }

    // =====================================================================
    // PUNTO DE ENTRADA
    // =====================================================================

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("GENERADOR DE FACTURAS - WORKFLOW CONCURRENTE");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("\nEsta demo muestra PROCESO EN PARALELO con pasos interactivos:");
        Console.WriteLine("   • Usted elige UNA factura para procesar");
        Console.WriteLine("   • TRES tareas se ejecutan SIMULTANEAMENTE:");
        Console.WriteLine("     1. Calcular totales (importes, descuentos, impuesto)");
        Console.WriteLine("     2. Preparar ficha del cliente (nombre, categoría, email)");
        Console.WriteLine("     3. Verificar crédito (puntuación, límite, aprobación)");
        Console.WriteLine("   • Los resultados SE FUSIONAN cuando terminan las tres tareas");
        Console.WriteLine("\nPatrón del workflow:");
        Console.WriteLine("   Dispatcher -> [Totales + Ficha cliente + Crédito] -> Fusion -> Renderizado");
        Console.WriteLine("                 +--------- EJECUCION EN PARALELO ---------+");
        Console.WriteLine(new string('=', 80));

        while (true)
        {
            await EjecutarWorkflowAsync();

            Console.WriteLine("\n" + new string('=', 80));
            Console.Write("\n¿Procesar otra factura? (s/n): ");
            string? respuesta = Console.ReadLine()?.Trim().ToLowerInvariant();

            if (respuesta is not ("s" or "si" or "y" or "yes"))
            {
                Console.WriteLine("\n¡Gracias por usar el Generador de Facturas!");
                Console.WriteLine(new string('=', 80));
                break;
            }

            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("REINICIANDO EL WORKFLOW...");
            Console.WriteLine(new string('=', 80));
        }
    }

    private static async Task EjecutarWorkflowAsync()
    {
        var dispatcher = new Dispatcher("dispatcher");
        var totales = new CalculadoraTotales("calculadora_totales");
        var cliente = new PreparadorCliente("preparador_cliente");
        var credito = new VerificadorCredito("verificador_credito");
        var fusionador = new Fusionador("fusionador");
        var renderizador = new Renderizador("renderizador");

        // -----------------------------------------------------------------
        // CONSTRUCCIÓN DEL GRAFO CONCURRENTE
        // -----------------------------------------------------------------
        // FAN-OUT: el dispatcher difunde el MISMO FacturaConConfig a las tres
        // tareas, que corren CONCURRENTEMENTE.
        //
        // FAN-IN (barrera): las cuatro aristas convergen en el fusionador CON
        // SINCRONIZACIÓN AUTOMÁTICA. El dispatcher se incluye como origen porque
        // el fusionador necesita la factura original para reconstruir el resultado.
        Workflow workflow = new WorkflowBuilder(dispatcher)
            .AddFanOutEdge(dispatcher, [totales, cliente, credito])
            .AddFanInBarrierEdge([dispatcher, totales, cliente, credito], fusionador)
            .AddEdge(fusionador, renderizador)
            .WithOutputFrom(renderizador)
            .WithName("facturacion_concurrente")
            .Build();

        StreamingRun run = await InProcessExecution.RunStreamingAsync(workflow, "start");

        await foreach (WorkflowEvent evt in run.WatchStreamAsync())
        {
            if (evt is WorkflowOutputEvent salida)
            {
                Console.WriteLine("\n" + new string('=', 80));
                Console.WriteLine("WORKFLOW CONCURRENTE COMPLETADO");
                Console.WriteLine(new string('=', 80));
                Console.WriteLine(salida.Data);
                Console.WriteLine("\nRevise los siguientes directorios:");
                Console.WriteLine($"   • Salida: {OutputDir}");
                Console.WriteLine($"   • Registros: {LogsDir}");
                Console.WriteLine("\nNota: ¡los tres ejecutores corrieron EN PARALELO para mayor rendimiento!");
                Console.WriteLine("   ¡Cada factura incluye totales, ficha de cliente Y verificación de crédito!");
                Console.WriteLine(new string('=', 80));
            }
            else if (evt is ExecutorFailedEvent fallo)
            {
                Console.WriteLine($"\n❌ Falló un ejecutor: {fallo.Data}");
            }
        }
    }
}
