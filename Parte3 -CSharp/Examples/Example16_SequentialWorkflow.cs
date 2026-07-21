using Microsoft.Agents.AI.Workflows;
using MFA.CSharp.Part3.Infrastructure;
using static MFA.CSharp.Part3.Infrastructure.InvoiceUtils;

namespace MFA.CSharp.Part3.Examples;

/// <summary>
/// 16 · Workflow SECUENCIAL.
/// Equivalente C# de <c>new_16_sequential_workflow.py</c>.
///
/// <para><b>Objetivo pedagógico:</b> el patrón de workflow más simple, una CADENA
/// LINEAL de ejecutores donde la salida de cada paso alimenta al siguiente. Es la
/// base de los ejemplos 17-21.</para>
///
/// <code>
/// CargarConfig → LeerFacturas → CalcularTotales → Renderizar → Guardar
/// </code>
///
/// <para><b>Conceptos clave:</b></para>
/// <list type="number">
///   <item>
///     <b>EJECUTOR:</b> unidad de trabajo del grafo. En .NET se declara como
///     <c>partial class : Executor</c> con métodos marcados <c>[MessageHandler]</c>.
///     Un generador de código construye el enrutado en tiempo de compilación.
///   </item>
///   <item>
///     <b>EL CONTRATO SE DECLARA EN EL ATRIBUTO:</b> <c>Send</c> indica qué tipos
///     envía el paso al siguiente y <c>Yield</c> qué tipos produce como salida del
///     workflow. Es el equivalente al <c>WorkflowContext[T]</c> / <c>[Never, T]</c>
///     de Python, pero verificado en tiempo de EJECUCIÓN por el motor.
///   </item>
///   <item>
///     <b>SUPERSTEPS:</b> el motor es tipo Pregel. Los mensajes entre ejecutores se
///     entregan al final de cada superstep y no son visibles en el stream; solo se
///     observan los eventos del workflow.
///   </item>
/// </list>
///
/// <para><b>NOTA:</b> este ejemplo NO usa ningún LLM — es cálculo local puro.</para>
/// </summary>
// ⚠️ La clase contenedora debe ser `partial`: el generador de código del patrón
// [MessageHandler] emite las clases anidadas como declaraciones parciales, y sin
// este modificador el compilador falla con CS0260.
internal static partial class Example16_SequentialWorkflow
{
    // =====================================================================
    // MENSAJES QUE VIAJAN POR EL GRAFO
    // =====================================================================
    // En Python estos pasos encadenan TUPLAS que van creciendo
    // (tuple[InvoiceConfig, InvoiceData], tuple[InvoiceData, dict, str]...).
    // En C# se usan records con nombre: el compilador valida cada campo y el
    // código se lee sin tener que recordar el orden de la tupla.

    internal sealed record ConfigCargada(InvoiceConfig Config);
    internal sealed record FacturaSeleccionada(InvoiceConfig Config, InvoiceData Invoice);
    internal sealed record TotalesCalculados(InvoiceData Invoice, InvoiceTotals Totals);
    internal sealed record FacturaRenderizada(InvoiceData Invoice, InvoiceTotals Totals, string Texto);

    // =====================================================================
    // PASO 1 — ENTRADA del grafo
    // =====================================================================
    // Recibe la señal de arranque ("start") y produce el InvoiceConfig que
    // alimenta al resto de la cadena.
    internal sealed partial class CargarConfiguracion(string id) : Executor(id)
    {
        // Send declara el tipo que este paso ENVÍA al siguiente ejecutor.
        [MessageHandler(Send = [typeof(ConfigCargada)])]
        public async ValueTask HandleAsync(string senal, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(1, "CARGAR CONFIGURACION");
            Console.WriteLine("🔧 Cargando configuración...");

            // Los directorios se crean AQUÍ (paso 1) y no al guardar: este mismo
            // paso ya escribe en logs/ con LogAction().
            EnsureDirectories(OutputDir, LogsDir);

            var config = InvoiceConfig.Load();

            Console.WriteLine("\n✅ ¡Configuración cargada correctamente!");
            Console.WriteLine($"   📊 Tasa de impuesto: {Pct(config.TaxRate)}");
            Console.WriteLine($"   💰 Umbral de alto valor: {Money(config.HighValueThreshold)}");
            Console.WriteLine($"   🎁 Descuento por alto valor: {Pct(config.HighValueDiscount)}");
            Console.WriteLine($"   ⭐ Descuento cliente preferente: {Pct(config.PreferredClientDiscount)}");

            LogAction($"Configuración cargada: {config}");
            WaitForUser("PASO 2 - Leer datos de facturas");

            // SendMessageAsync equivale al ctx.send_message() de Python
            await context.SendMessageAsync(new ConfigCargada(config), ct);
        }
    }

    // =====================================================================
    // PASO 2 — lee el CSV y deja que el usuario elija UNA factura
    // =====================================================================
    internal sealed partial class LeerFacturas(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(FacturaSeleccionada)])]
        public async ValueTask HandleAsync(ConfigCargada msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(2, "LEER DATOS Y SELECCIONAR FACTURA");
            Console.WriteLine("📂 Leyendo facturas desde el archivo CSV...");

            List<InvoiceData> todas = ReadInvoicesCsv();
            Console.WriteLine($"\n✅ Se cargaron {todas.Count} facturas desde invoices.csv");

            // Menú interactivo: el usuario elige qué factura procesar
            InvoiceData elegida = ShowMenu(todas);

            Console.WriteLine($"\n✅ Factura seleccionada: {elegida.InvoiceId}");
            Console.WriteLine($"   Cliente: {elegida.ClientName}");
            Console.WriteLine($"   Email: {elegida.ClientEmail}");
            Console.WriteLine($"   Concepto: {elegida.ItemDescription}");
            Console.WriteLine($"   Cantidad: {elegida.Quantity}");
            Console.WriteLine($"   Precio unitario: {Money(elegida.UnitPrice)}");
            Console.WriteLine($"   Subtotal: {Money(elegida.Subtotal)}");
            Console.WriteLine($"   Cliente preferente: {(elegida.IsPreferred ? "⭐ SI" : "❌ NO")}");

            LogAction($"Factura {elegida.InvoiceId} seleccionada para procesar");
            WaitForUser("PASO 3 - Calcular totales");

            // Se envía la config JUNTO a la factura: el paso 3 necesita ambas
            await context.SendMessageAsync(new FacturaSeleccionada(msg.Config, elegida), ct);
        }
    }

    // =====================================================================
    // PASO 3 — aplica las reglas de negocio (descuentos + impuesto)
    // =====================================================================
    // El cálculo real vive en InvoiceUtils.CalculateInvoiceTotals(); este
    // ejecutor solo orquesta y muestra el desglose.
    internal sealed partial class CalcularTotales(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(TotalesCalculados)])]
        public async ValueTask HandleAsync(FacturaSeleccionada msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(3, "CALCULAR TOTALES");

            (InvoiceConfig config, InvoiceData invoice) = (msg.Config, msg.Invoice);

            Console.WriteLine($"🧮 Calculando importes de {invoice.InvoiceId}...");
            Console.WriteLine($"   Subtotal de partida: {Money(invoice.Subtotal)}");

            InvoiceTotals t = CalculateInvoiceTotals(invoice, config);

            Console.WriteLine("\n✅ ¡Cálculo completado!");
            Console.WriteLine($"\n   {"Concepto",-32} {"Importe",15}");
            Console.WriteLine($"   {new string('-', 32)} {new string('-', 15)}");
            Console.WriteLine($"   {"Subtotal",-32} {MoneyGrouped(t.Subtotal),15}");

            // Los porcentajes se leen de la config: escritos a mano mentirían si
            // se cambiara una tasa en appsettings03.json.
            if (t.HighValueDiscount > 0)
                Console.WriteLine($"   {$"Desc. alto valor ({Pct(config.HighValueDiscount)})",-32} {"-" + MoneyGrouped(t.HighValueDiscount),15}");

            if (t.PreferredDiscount > 0)
                Console.WriteLine($"   {$"Desc. preferente ({Pct(config.PreferredClientDiscount)})",-32} {"-" + MoneyGrouped(t.PreferredDiscount),15}");

            if (t.TotalDiscount > 0)
            {
                Console.WriteLine($"   {new string('-', 32)} {new string('-', 15)}");
                Console.WriteLine($"   {"Importe tras descuentos",-32} {MoneyGrouped(t.AmountAfterDiscount),15}");
            }

            Console.WriteLine($"   {$"Impuesto ({Pct(config.TaxRate)})",-32} {MoneyGrouped(t.Tax),15}");
            Console.WriteLine($"   {new string('=', 32)} {new string('=', 15)}");
            Console.WriteLine($"   {"💰 TOTAL A PAGAR",-32} {MoneyGrouped(t.Total),15}");
            Console.WriteLine($"   {new string('=', 32)} {new string('=', 15)}");

            LogAction($"Totales calculados para {invoice.InvoiceId}: {Money(t.Total)}");
            WaitForUser("PASO 4 - Renderizar factura");

            await context.SendMessageAsync(new TotalesCalculados(invoice, t), ct);
        }
    }

    // =====================================================================
    // PASO 4 — convierte los datos en el documento de texto final
    // =====================================================================
    // No escribe nada en disco todavía: solo genera la cadena y la reenvía.
    internal sealed partial class RenderizarFactura(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(FacturaRenderizada)])]
        public async ValueTask HandleAsync(TotalesCalculados msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(4, "RENDERIZAR FACTURA");

            var config = InvoiceConfig.Load();
            Console.WriteLine($"🖨️  Renderizando la factura {msg.Invoice.InvoiceId} como texto...");

            string texto = RenderInvoiceText(msg.Invoice, msg.Totals, config);

            Console.WriteLine($"\n✅ ¡Factura renderizada! ({texto.Length} caracteres)");

            // Vista previa por consola antes de guardar
            Console.WriteLine($"\n{new string('-', 80)}");
            Console.WriteLine("📄 VISTA PREVIA DE LA FACTURA:");
            Console.WriteLine(new string('-', 80));
            Console.WriteLine(texto);
            Console.WriteLine(new string('-', 80));

            LogAction($"Factura {msg.Invoice.InvoiceId} renderizada");
            WaitForUser("PASO 5 - Guardar factura");

            await context.SendMessageAsync(new FacturaRenderizada(msg.Invoice, msg.Totals, texto), ct);
        }
    }

    // =====================================================================
    // PASO 5 — TERMINAL. Guarda el archivo y cierra el workflow.
    // =====================================================================
    // No envía nada a nadie: PRODUCE el resultado del workflow con
    // YieldOutputAsync(). Por eso el atributo declara Yield en vez de Send.
    //
    // ⚠️ Si se omite `Yield` el ejemplo COMPILA pero falla en ejecución con
    // "Cannot output object of type String. Expecting one of []".
    // Es el equivalente a WorkflowContext[Never, str] de Python.
    internal sealed partial class GuardarFactura(string id) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(FacturaRenderizada msg, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            PrintStep(5, "GUARDAR FACTURA");

            Console.WriteLine($"💾 Guardando la factura {msg.Invoice.InvoiceId} en disco...");

            string ruta = SaveInvoiceFile(msg.Invoice.InvoiceId, msg.Texto);

            Console.WriteLine("\n✅ ¡Factura guardada correctamente!");
            Console.WriteLine($"   📁 Ubicación: {ruta}");
            Console.WriteLine($"   📊 Cliente: {msg.Invoice.ClientName}");
            Console.WriteLine($"   💵 Importe: {Money(msg.Totals.Total)}");

            LogAction($"Factura {msg.Invoice.InvoiceId} guardada en {ruta}");

            // YieldOutputAsync marca el fin del workflow y devuelve el resultado
            await context.YieldOutputAsync(
                $"✅ ¡Workflow secuencial completado! Factura {msg.Invoice.InvoiceId} procesada con éxito.", ct);
        }
    }

    // =====================================================================
    // PUNTO DE ENTRADA
    // =====================================================================

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("🧾 GENERADOR DE FACTURAS - WORKFLOW SECUENCIAL INTERACTIVO");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("\n✨ Esta demo muestra un workflow secuencial con pasos INTERACTIVOS:");
        Console.WriteLine("   • Usted elige UNA factura para procesar");
        Console.WriteLine("   • Cada paso del workflow se detiene para que pueda revisarlo");
        Console.WriteLine("   • Pulse ENTER para avanzar al siguiente paso");
        Console.WriteLine("\n📋 Pasos del workflow:");
        Console.WriteLine("   1. Cargar configuración → Muestra impuestos y descuentos");
        Console.WriteLine("   2. Leer y seleccionar factura → Elija del menú");
        Console.WriteLine("   3. Calcular totales → Vea el desglose de importes");
        Console.WriteLine("   4. Renderizar factura → Vista previa del documento");
        Console.WriteLine("   5. Guardar factura → Escribe el archivo de salida");
        Console.WriteLine(new string('=', 80));

        while (true)
        {
            await EjecutarWorkflowAsync();

            Console.WriteLine("\n" + new string('=', 80));
            Console.Write("\n🔄 ¿Procesar otra factura? (s/n): ");
            string? respuesta = Console.ReadLine()?.Trim().ToLowerInvariant();

            // Se aceptan 's' (español) e 'y' (por costumbre) como afirmativas
            if (respuesta is not ("s" or "si" or "y" or "yes"))
            {
                Console.WriteLine("\n👋 ¡Gracias por usar el Generador de Facturas!");
                Console.WriteLine(new string('=', 80));
                break;
            }

            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("🔄 REINICIANDO EL WORKFLOW...");
            Console.WriteLine(new string('=', 80));
        }
    }

    private static async Task EjecutarWorkflowAsync()
    {
        // -----------------------------------------------------------------
        // CONSTRUCCIÓN DEL GRAFO
        // -----------------------------------------------------------------
        // El ejecutor inicial va en el CONSTRUCTOR de WorkflowBuilder (igual que
        // en Python 1.11.0). WithOutputFrom() declara qué ejecutor produce la
        // salida final del workflow.
        //
        // Cada AddEdge(A, B) es una arista dirigida: lo que A envía llega a B.
        // Al ser una cadena lineal esto podría escribirse también con AddChain();
        // se dejan las aristas explícitas porque hacen visible la topología, que
        // es justo lo que enseña el ejemplo.
        var cargar = new CargarConfiguracion("cargar_config");
        var leer = new LeerFacturas("leer_facturas");
        var calcular = new CalcularTotales("calcular_totales");
        var renderizar = new RenderizarFactura("renderizar_factura");
        var guardar = new GuardarFactura("guardar_factura");

        Workflow workflow = new WorkflowBuilder(cargar)
            .AddEdge(cargar, leer)
            .AddEdge(leer, calcular)
            .AddEdge(calcular, renderizar)
            .AddEdge(renderizar, guardar)
            .WithOutputFrom(guardar)
            .WithName("facturacion_secuencial")
            .Build();

        // -----------------------------------------------------------------
        // EJECUCIÓN EN STREAMING
        // -----------------------------------------------------------------
        // Equivale al `workflow.run(msg, stream=True)` de Python. Los eventos se
        // discriminan por TIPO (patrón `is`), no por una cadena `.type`.
        StreamingRun run = await InProcessExecution.RunStreamingAsync(workflow, "start");

        await foreach (WorkflowEvent evt in run.WatchStreamAsync())
        {
            if (evt is WorkflowOutputEvent salida)
            {
                Console.WriteLine("\n" + new string('=', 80));
                Console.WriteLine("🎉 WORKFLOW COMPLETADO");
                Console.WriteLine(new string('=', 80));
                Console.WriteLine(salida.Data);
                Console.WriteLine("\n📁 Revise los siguientes directorios:");
                Console.WriteLine($"   • Salida: {OutputDir}");
                Console.WriteLine($"   • Registros: {LogsDir}");
                Console.WriteLine(new string('=', 80));
            }
            else if (evt is ExecutorFailedEvent fallo)
            {
                Console.WriteLine($"\n❌ Falló un ejecutor: {fallo.Data}");
            }
        }
    }
}
