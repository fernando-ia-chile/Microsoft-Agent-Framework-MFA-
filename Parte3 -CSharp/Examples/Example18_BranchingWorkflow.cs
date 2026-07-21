using Microsoft.Agents.AI.Workflows;
using MFA.CSharp.Part3.Infrastructure;
using static MFA.CSharp.Part3.Infrastructure.InvoiceUtils;

namespace MFA.CSharp.Part3.Examples;

/// <summary>
/// 18 · Workflow con RAMIFICACIÓN CONDICIONAL.
/// Equivalente C# de <c>new_18_branching_workflow.py</c>.
///
/// <para><b>Objetivo pedagógico:</b> el grafo ya no es fijo. Según los DATOS, la
/// factura recorre un camino u otro. Es el equivalente a un <c>switch</c> dentro
/// del grafo.</para>
///
/// <code>
///                    ┌─► Archivador ──┐ (vuelve a decidir)
///                    │                │
///    Cargador ───────┼─► AltoValor ───┐
///     (decide)       ├─► Preferente ──┼─► Finalizador
///                    └─► Estandar ────┘
///                       (Default: si nada coincide)
/// </code>
///
/// <para><b>Conceptos clave:</b></para>
/// <list type="number">
///   <item><c>AddSwitch(origen, sb =&gt; sb.AddCase(pred, destino).WithDefault(destino))</c>.
///   Las condiciones se evalúan EN ORDEN y gana LA PRIMERA que devuelve true;
///   <c>WithDefault</c> recoge lo que no encaja en ningún caso.</item>
///   <item>LA CONDICIÓN ES UN <c>Func&lt;T, bool&gt;</c> normal: recibe el mensaje y
///   devuelve un booleano. Se puede probar por separado, sin levantar el workflow.</item>
///   <item>RE-ENRUTADO EN CADENA: el archivador NO termina el trabajo, vuelve a
///   decidir. Por eso hay DOS switches: uno en el cargador y otro en el archivador.</item>
///   <item>CONVERGENCIA: las tres ramas de negocio terminan en el mismo finalizador
///   mediante <c>AddEdge</c> normales.</item>
/// </list>
///
/// <para>⚠️ <b>DETALLE IMPORTANTE:</b> la rama de ARCHIVADO solo se activa si YA
/// EXISTE el archivo de esa factura. Procese <b>la misma factura dos veces</b> para
/// verla en acción; el menú marca <c>[YA EXISTE -&gt; se archivará]</c>.</para>
///
/// <para><b>NOTA:</b> este ejemplo NO usa ningún LLM — es cálculo local puro.</para>
/// </summary>
internal static partial class Example18_BranchingWorkflow
{
    // =====================================================================
    // TIPOS DE DECISIÓN
    // =====================================================================

    /// <summary>
    /// Motivo por el que se enruta una factura.
    /// <para>
    /// ⚠️ DIFERENCIA CON PYTHON: allí la decisión es una CADENA
    /// (<c>"high_value"</c>, <c>"preferred"</c>...) y un typo pasa desapercibido.
    /// Aquí es un <c>enum</c>: el compilador valida cada uso y el <c>switch</c>
    /// avisa si se olvida un caso.
    /// </para>
    /// </summary>
    internal enum TipoDecision
    {
        NecesitaArchivado,
        AltoValor,
        Preferente,
        Estandar,
    }

    /// <summary>
    /// Factura + su decisión de enrutado: es el mensaje que viaja por el grafo.
    /// Lleva TODO lo necesario (factura, config, totales y motivo) para que
    /// cualquier rama pueda trabajar sin volver a calcular.
    /// </summary>
    internal sealed record DecisionFactura(InvoiceData Invoice, InvoiceConfig Config,
                                           InvoiceTotals Totals, TipoDecision Tipo, string Motivo);

    // =====================================================================
    // ANÁLISIS: EL "CEREBRO" DE LA RAMIFICACIÓN
    // =====================================================================

    /// <summary>
    /// Decide POR QUÉ RAMA debe ir la factura y explica el motivo.
    /// <para>
    /// ⚠️ El ORDEN de las comprobaciones importa — se devuelve la PRIMERA que se
    /// cumple, igual que hará el switch del grafo.
    /// </para>
    /// </summary>
    private static (TipoDecision Tipo, string Motivo) AnalizarEnrutado(InvoiceData invoice, InvoiceConfig config)
    {
        // 1º) ¿Ya existe una factura previa con este ID? Hay que archivarla antes
        if (File.Exists(Path.Combine(OutputDir, $"{invoice.InvoiceId}.txt")))
            return (TipoDecision.NecesitaArchivado, "Ya existe un archivo previo: hay que archivarlo");

        // 2º) ¿Supera el umbral de alto valor?
        if (invoice.Subtotal >= config.HighValueThreshold)
            return (TipoDecision.AltoValor,
                    $"Alto valor ({Money(invoice.Subtotal)}): se aplica descuento por volumen");

        // 3º) ¿Es cliente preferente?
        if (invoice.IsPreferred)
            return (TipoDecision.Preferente, "Cliente preferente: se aplica descuento por fidelidad");

        // 4º) Si no encaja en nada, procesamiento normal (rama Default)
        return (TipoDecision.Estandar, "Procesamiento normal");
    }

    // =====================================================================
    // CONDICIONES DE ENRUTADO
    // =====================================================================
    // Son funciones normales: reciben el mensaje y devuelven bool. El grafo las
    // evalúa EN ORDEN y usa la primera que dé true. Al ser funciones corrientes
    // se pueden probar de forma aislada, sin levantar el workflow.

    private static bool EsNecesarioArchivar(DecisionFactura? d) => d?.Tipo == TipoDecision.NecesitaArchivado;
    private static bool EsAltoValor(DecisionFactura? d) => d?.Tipo == TipoDecision.AltoValor;
    private static bool EsPreferente(DecisionFactura? d) => d?.Tipo == TipoDecision.Preferente;

    // =====================================================================
    // PUNTO DE DECISIÓN INICIAL
    // =====================================================================
    // Carga la factura, la analiza y emite una DecisionFactura; el switch
    // posterior mira ese objeto para elegir la rama.
    internal sealed partial class CargadorFacturas(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(DecisionFactura)])]
        public async ValueTask HandleAsync(string senal, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(1, "CARGAR Y SELECCIONAR FACTURA");

            // Los directorios se crean AQUÍ: este mismo paso ya escribe en logs/
            EnsureDirectories(OutputDir, LogsDir, ArchiveDir);

            var config = InvoiceConfig.Load();
            List<InvoiceData> todas = ReadInvoicesCsv();
            Console.WriteLine($"Se cargaron {todas.Count} facturas");

            // marcarExistentes: señala cuáles activarán la rama de archivado
            InvoiceData elegida = ShowMenu(todas, marcarExistentes: true);

            Console.WriteLine($"\nSeleccionada: {elegida.InvoiceId} - {elegida.ClientName}");
            Console.WriteLine($"   Importe: {Money(elegida.Subtotal)}");
            Console.WriteLine($"   Preferente: {(elegida.IsPreferred ? "SI" : "NO")}");

            // Aquí se decide la rama; el grafo solo ejecuta lo que diga esta función
            (TipoDecision tipo, string motivo) = AnalizarEnrutado(elegida, config);
            InvoiceTotals totales = CalculateInvoiceTotals(elegida, config);

            Console.WriteLine("\nRESULTADO DEL ANALISIS:");
            Console.WriteLine($"   Tipo de decisión: {tipo}");
            Console.WriteLine($"   Motivo: {motivo}");

            if (tipo == TipoDecision.AltoValor)
            {
                Console.WriteLine($"   Umbral de alto valor: {Money(config.HighValueThreshold)}");
                Console.WriteLine($"   Descuento por alto valor: {Money(totales.HighValueDiscount)}");
            }
            else if (tipo == TipoDecision.Preferente)
            {
                Console.WriteLine($"   Descuento por fidelidad: {Money(totales.PreferredDiscount)}");
            }

            LogAction($"Factura {elegida.InvoiceId} seleccionada y analizada: {tipo}");
            WaitForUser("iniciar el workflow con RAMIFICACION");

            await context.SendMessageAsync(new DecisionFactura(elegida, config, totales, tipo, motivo), ct);
        }
    }

    // =====================================================================
    // RAMA DE ARCHIVADO
    // =====================================================================
    // Es especial: NO va al finalizador, sino que vuelve a decidir. Por eso tiene
    // su propio switch en el grafo (ver ConstruirWorkflow).
    internal sealed partial class ManejadorArchivado(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(DecisionFactura)])]
        public async ValueTask HandleAsync(DecisionFactura d, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine($"\n[RAMA ARCHIVADO] {d.Invoice.InvoiceId}");
            Console.WriteLine($"   Motivo: {d.Motivo}");

            bool archivada = ArchiveOldInvoice(d.Invoice.InvoiceId);

            if (archivada)
            {
                Console.WriteLine($"   Factura anterior archivada en {ArchiveDir}");
                LogAction($"Factura anterior {d.Invoice.InvoiceId} archivada");
            }

            Console.WriteLine("   Continuando al siguiente punto de decisión...");

            // CLAVE: se vuelve a analizar. Como el archivo ya se movió, esta vez
            // AnalizarEnrutado() NO devolverá NecesitaArchivado y la factura
            // seguirá por su rama de negocio.
            //
            // Se usa `with` (copia con cambios) en vez de mutar el objeto: evita
            // efectos colaterales si alguien conservara el mensaje original.
            // Es el equivalente al dataclasses.replace() de Python.
            (TipoDecision tipo, string motivo) = AnalizarEnrutado(d.Invoice, d.Config);
            DecisionFactura siguiente = d with { Tipo = tipo, Motivo = motivo };

            Console.WriteLine($"   Siguiente decisión: {tipo}");
            Console.WriteLine($"   Motivo: {motivo}");

            WaitForUser("continuar a la SIGUIENTE RAMA");

            await context.SendMessageAsync(siguiente, ct);
        }
    }

    // =====================================================================
    // RAMA 1 de negocio — factura que supera el umbral de alto valor
    // =====================================================================
    internal sealed partial class ManejadorAltoValor(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(DecisionFactura)])]
        public async ValueTask HandleAsync(DecisionFactura d, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine($"\n[RAMA ALTO VALOR] {d.Invoice.InvoiceId}");
            Console.WriteLine($"   Motivo: {d.Motivo}");
            Console.WriteLine($"   Total original: {Money(d.Totals.Total)}");
            Console.WriteLine($"   Descuento por alto valor: {Money(d.Totals.HighValueDiscount)}");
            Console.WriteLine("   Procesamiento especial aplicado");

            LogAction($"Descuento por alto valor aplicado a {d.Invoice.InvoiceId}");
            WaitForUser("continuar a la FINALIZACION");

            await context.SendMessageAsync(d, ct);
        }
    }

    // =====================================================================
    // RAMA 2 de negocio — cliente preferente (fidelidad)
    // =====================================================================
    internal sealed partial class ManejadorPreferente(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(DecisionFactura)])]
        public async ValueTask HandleAsync(DecisionFactura d, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine($"\n[RAMA CLIENTE PREFERENTE] {d.Invoice.InvoiceId}");
            Console.WriteLine($"   Motivo: {d.Motivo}");
            Console.WriteLine($"   Cliente: {d.Invoice.ClientName}");
            Console.WriteLine($"   Total original: {Money(d.Totals.Total)}");
            Console.WriteLine($"   Descuento por fidelidad: {Money(d.Totals.PreferredDiscount)}");
            Console.WriteLine("   Recompensas de fidelidad aplicadas");

            LogAction($"Descuento de cliente preferente aplicado a {d.Invoice.InvoiceId}");
            WaitForUser("continuar a la FINALIZACION");

            await context.SendMessageAsync(d, ct);
        }
    }

    // =====================================================================
    // RAMA 3 de negocio — la del Default: recoge todo lo que no encaja arriba
    // =====================================================================
    internal sealed partial class ManejadorEstandar(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(DecisionFactura)])]
        public async ValueTask HandleAsync(DecisionFactura d, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine($"\n[RAMA ESTANDAR] {d.Invoice.InvoiceId}");
            Console.WriteLine($"   Motivo: {d.Motivo}");
            Console.WriteLine($"   Cliente: {d.Invoice.ClientName}");
            Console.WriteLine($"   Total: {Money(d.Totals.Total)}");
            Console.WriteLine("   Procesamiento estándar");

            LogAction($"Procesamiento estándar para {d.Invoice.InvoiceId}");
            WaitForUser("continuar a la FINALIZACION");

            await context.SendMessageAsync(d, ct);
        }
    }

    // =====================================================================
    // PUNTO DE CONVERGENCIA — TERMINAL del grafo
    // =====================================================================
    // Las tres ramas de negocio acaban aquí.
    internal sealed partial class FinalizadorFactura(string id) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(DecisionFactura d, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(3, "RENDERIZAR Y GUARDAR");

            Console.WriteLine($"Renderizando la factura {d.Invoice.InvoiceId}...");

            string facturaTexto = RenderInvoiceText(d.Invoice, d.Totals, d.Config);

            // Se deja constancia EN EL DOCUMENTO de qué rama se recorrió: es lo que
            // hace visible el resultado de la ramificación al abrir el archivo.
            string bloqueRama = $"""

                DECISION DE RAMIFICACION:
                =========================
                Tipo de decisión: {d.Tipo}
                Motivo: {d.Motivo}

                """;

            string completo = facturaTexto + bloqueRama;
            string ruta = SaveInvoiceFile(d.Invoice.InvoiceId, completo);

            Console.WriteLine($"\n{new string('-', 80)}");
            Console.WriteLine("VISTA PREVIA DE LA FACTURA:");
            Console.WriteLine(new string('-', 80));
            Console.WriteLine(completo);
            Console.WriteLine(new string('-', 80));

            Console.WriteLine("\n¡Factura guardada correctamente!");
            Console.WriteLine($"   Ubicación: {ruta}");
            Console.WriteLine($"   Rama: {d.Tipo}");
            Console.WriteLine($"   Total: {Money(d.Totals.Total)}");

            LogAction($"Factura {d.Invoice.InvoiceId} finalizada por la rama {d.Tipo}");

            await context.YieldOutputAsync(
                $"¡Workflow con ramificación completado! Factura {d.Invoice.InvoiceId} " +
                $"procesada por la rama {d.Tipo}.", ct);
        }
    }

    // =====================================================================
    // PUNTO DE ENTRADA
    // =====================================================================

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("GENERADOR DE FACTURAS - WORKFLOW CON RAMIFICACION");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("\nEsta demo muestra RAMIFICACION CONDICIONAL con pasos interactivos:");
        Console.WriteLine("   • Usted elige UNA factura para procesar");
        Console.WriteLine("   • El sistema la analiza y decide qué camino debe seguir");
        Console.WriteLine("   • La factura recorre la rama que le corresponde:");
        Console.WriteLine("     1. ¿Ya existe el archivo? -> Archiva primero la versión anterior");
        Console.WriteLine("     2. ¿Factura de alto valor? -> Aplica descuento por volumen");
        Console.WriteLine("     3. ¿Cliente preferente? -> Aplica descuento por fidelidad");
        Console.WriteLine("     4. En cualquier otro caso -> Procesamiento estándar");
        Console.WriteLine("\nPatrón del workflow:");
        Console.WriteLine("   Carga -> [¿Archivar?] -> [Alto valor / Preferente / Estandar] -> Finalizacion");
        Console.WriteLine("           +--------- ENRUTADO CONDICIONAL ---------+");
        Console.WriteLine("\nCONSEJO: procese DOS VECES la misma factura para ver la rama de archivado.");
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
        var cargador = new CargadorFacturas("cargador");
        var archivador = new ManejadorArchivado("manejador_archivado");
        var altoValor = new ManejadorAltoValor("manejador_alto_valor");
        var preferente = new ManejadorPreferente("manejador_preferente");
        var estandar = new ManejadorEstandar("manejador_estandar");
        var finalizador = new FinalizadorFactura("finalizador");

        // -----------------------------------------------------------------
        // CONSTRUCCIÓN DEL GRAFO CON RAMIFICACIÓN
        // -----------------------------------------------------------------
        // SWITCH 1: decisión inicial. Se evalúa EN ORDEN y gana la primera
        // condición que devuelve true; WithDefault recoge el resto.
        //
        // SWITCH 2: tras archivar se DECIDE OTRA VEZ. Aquí ya no puede volver a
        // salir NecesitaArchivado (el archivo se movió), por eso este grupo no
        // incluye esa rama: evita un bucle infinito.
        Workflow workflow = new WorkflowBuilder(cargador)
            .AddSwitch(cargador, sw => sw
                .AddCase<DecisionFactura>(EsNecesarioArchivar, [archivador])
                .AddCase<DecisionFactura>(EsAltoValor, [altoValor])
                .AddCase<DecisionFactura>(EsPreferente, [preferente])
                .WithDefault([estandar]))
            .AddSwitch(archivador, sw => sw
                .AddCase<DecisionFactura>(EsAltoValor, [altoValor])
                .AddCase<DecisionFactura>(EsPreferente, [preferente])
                .WithDefault([estandar]))
            // CONVERGENCIA: las tres ramas de negocio terminan en el finalizador
            .AddEdge(altoValor, finalizador)
            .AddEdge(preferente, finalizador)
            .AddEdge(estandar, finalizador)
            .WithOutputFrom(finalizador)
            .WithName("facturacion_ramificada")
            .Build();

        StreamingRun run = await InProcessExecution.RunStreamingAsync(workflow, "start");

        await foreach (WorkflowEvent evt in run.WatchStreamAsync())
        {
            if (evt is WorkflowOutputEvent salida)
            {
                Console.WriteLine("\n" + new string('=', 80));
                Console.WriteLine("WORKFLOW CON RAMIFICACION COMPLETADO");
                Console.WriteLine(new string('=', 80));
                Console.WriteLine(salida.Data);
                Console.WriteLine("\nRevise los siguientes directorios:");
                Console.WriteLine($"   • Salida: {OutputDir}");
                Console.WriteLine($"   • Archivo histórico: {ArchiveDir}");
                Console.WriteLine($"   • Registros: {LogsDir}");
                Console.WriteLine("\nNota: ¡la factura siguió su rama según las reglas de negocio!");
                Console.WriteLine(new string('=', 80));
            }
            else if (evt is ExecutorFailedEvent fallo)
            {
                Console.WriteLine($"\n❌ Falló un ejecutor: {fallo.Data}");
            }
        }
    }
}
