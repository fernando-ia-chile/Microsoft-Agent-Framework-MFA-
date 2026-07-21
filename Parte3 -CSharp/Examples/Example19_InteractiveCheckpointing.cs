using System.Text.Json;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Agents.AI.Workflows.Checkpointing;
using MFA.CSharp.Part3.Infrastructure;
using static MFA.CSharp.Part3.Infrastructure.InvoiceUtils;

namespace MFA.CSharp.Part3.Examples;

/// <summary>
/// 19 · HUMAN-IN-THE-LOOP + CHECKPOINTING.
/// Equivalente C# de <c>new_19_interactive_checkpointing.py</c>.
///
/// <para><b>Objetivo pedagógico:</b> el workflow <b>se detiene de verdad</b>, pide
/// una decisión a una persona y continúa con lo que esa persona responda. Además
/// guarda checkpoints en disco.</para>
///
/// <code>
/// Preparación ─► [puerto impuesto] ─► AplicarImpuesto
///                      ⏸ PAUSA
///             ─► [puerto descuento] ─► AplicarDescuento ─► Finalizar
///                      ⏸ PAUSA
/// </code>
///
/// <para>🔴 <b>DIFERENCIA ARQUITECTÓNICA IMPORTANTE CON PYTHON</b></para>
/// <para>
/// En Python el HITL vive DENTRO del ejecutor: se llama a <c>ctx.request_info()</c>
/// y la respuesta llega a un <c>@response_handler</c> de ESE MISMO ejecutor.
/// </para>
/// <para>
/// En .NET el mecanismo es un <b><c>RequestPort</c>: un NODO MÁS del grafo</b>. Se
/// cablea con aristas normales — un ejecutor envía la petición <i>al puerto</i>, y
/// el puerto entrega la respuesta <i>al siguiente ejecutor</i>:
/// </para>
/// <code>
/// .AddEdge(preparador, puertoImpuesto)    // pregunta
/// .AddEdge(puertoImpuesto, aplicaImpuesto) // respuesta
/// </code>
/// <para>
/// Y la respuesta se envía con <c>run.SendResponseAsync(...)</c> <b>sin salir del
/// stream</b>: no hay que reanudar el workflow con otra llamada, como sí ocurre en
/// Python con <c>run(responses=...)</c>.
/// </para>
///
/// <para>⚠️ <b>LA RESPUESTA DEL USUARIO IMPORTA DE VERDAD:</b> si rechaza el
/// impuesto, NO se suma al total; si rechaza el descuento, NO se resta. Pruebe con
/// respuestas distintas y compare el total final.</para>
///
/// <para><b>NOTA:</b> este ejemplo NO usa ningún LLM — es cálculo local puro.</para>
/// </summary>
internal static partial class Example19_InteractiveCheckpointing
{
    // =====================================================================
    // TIPOS DE PETICIÓN Y ESTADO
    // =====================================================================

    /// <summary>Petición que viaja al humano para confirmar el impuesto.</summary>
    internal sealed record PeticionImpuesto(string InvoiceId, string Pregunta,
                                            decimal ValorActual, string Opciones);

    /// <summary>Petición que viaja al humano para confirmar el descuento.</summary>
    internal sealed record PeticionDescuento(string InvoiceId, string Pregunta,
                                             decimal ValorActual, string Opciones);

    /// <summary>
    /// Estado de la factura mientras recorre el workflow.
    /// Viaja de ejecutor en ejecutor acumulando las decisiones del humano. Todos
    /// los importes salen de la factura REAL seleccionada: no hay valores fijos.
    /// </summary>
    internal sealed record EstadoFactura(
        string InvoiceId,
        string ClientName,
        decimal Subtotal,
        decimal TaxRate,
        decimal TaxAmount,
        decimal DiscountAmount,
        bool TaxConfirmed = false,
        bool DiscountConfirmed = false);

    // =====================================================================
    // PUERTOS DE PETICIÓN (los "nodos de pausa" del grafo)
    // =====================================================================
    // RequestPort.Create<TPeticion, TRespuesta>(id) declara el canal: qué se
    // pregunta y qué tipo de respuesta se espera. Es el equivalente al segundo
    // argumento de ctx.request_info(datos, TipoRespuesta) en Python.
    private static readonly RequestPort PuertoImpuesto =
        RequestPort.Create<PeticionImpuesto, bool>("puerto_impuesto");

    private static readonly RequestPort PuertoDescuento =
        RequestPort.Create<PeticionDescuento, bool>("puerto_descuento");

    // Estado compartido entre ejecutores. Hace falta porque, a diferencia de
    // Python, el ejecutor que RECIBE la respuesta no es el mismo que la pidió:
    // el puerto entrega solo el bool, sin el contexto de la factura.
    private static EstadoFactura? s_estado;

    // =====================================================================
    // PASO 1 — ENTRADA del grafo
    // =====================================================================
    // Convierte la factura elegida en el EstadoFactura que recorrerá el workflow.
    // Aún no pregunta nada al humano.
    internal sealed partial class PreparacionFactura(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(PeticionImpuesto)])]
        public async ValueTask HandleAsync(InvoiceData invoice, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("PASO 1: PREPARAR FACTURA");
            Console.WriteLine(new string('=', 80));

            var config = InvoiceConfig.Load();
            InvoiceTotals t = CalculateInvoiceTotals(invoice, config);

            // Los dos descuentos posibles se suman en uno solo para la confirmación
            decimal descuento = t.HighValueDiscount + t.PreferredDiscount;

            var estado = new EstadoFactura(
                InvoiceId: invoice.InvoiceId,
                ClientName: invoice.ClientName,
                Subtotal: invoice.Subtotal,
                TaxRate: config.TaxRate,
                TaxAmount: t.Tax,
                DiscountAmount: descuento);

            s_estado = estado;

            Console.WriteLine($"Factura seleccionada: {estado.InvoiceId}");
            Console.WriteLine($"   Cliente: {estado.ClientName}");
            Console.WriteLine($"   Importe: {Money(estado.Subtotal)}");
            Console.WriteLine($"   Tasa de impuesto: {Pct(estado.TaxRate)}");
            Console.WriteLine($"   Impuesto calculado: {Money(estado.TaxAmount)}");
            Console.WriteLine($"   Descuento aplicable: {Money(estado.DiscountAmount)}");

            // QueueStateUpdateAsync guarda datos del ejecutor DENTRO del checkpoint.
            // Equivale al ctx.set_state(clave, valor) de Python, pero aquí SÍ es
            // asíncrono (en Python es síncrono).
            await context.QueueStateUpdateAsync("paso", "preparacion", cancellationToken: ct);
            await context.QueueStateUpdateAsync("invoice_id", estado.InvoiceId, cancellationToken: ct);

            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("PASO 2: CONFIRMAR IMPUESTO");
            Console.WriteLine(new string('=', 80));
            Console.WriteLine($"Factura: {estado.InvoiceId}");
            Console.WriteLine($"   Subtotal: {Money(estado.Subtotal)}");
            Console.WriteLine($"   Impuesto calculado: {Money(estado.TaxAmount)}");
            Console.WriteLine("\n>> El workflow se DETIENE aquí hasta recibir su respuesta...");

            // Enviar al PUERTO es lo que detiene el workflow y emite un RequestInfoEvent
            await context.SendMessageAsync(new PeticionImpuesto(
                estado.InvoiceId,
                $"¿Confirma el cálculo del impuesto de {estado.InvoiceId}?",
                estado.TaxAmount,
                "Escriba 's' para confirmar o 'n' para omitirlo"), ct);
        }
    }

    // =====================================================================
    // PASO 3 — recibe la decisión del humano sobre el impuesto
    // =====================================================================
    // ⚠️ Este ejecutor recibe un `bool`: es lo que el puerto entrega. El contexto
    // de la factura se recupera del estado compartido, no del mensaje.
    internal sealed partial class AplicarImpuesto(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(PeticionDescuento)], Yield = [typeof(string)])]
        public async ValueTask HandleAsync(bool respuesta, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("PASO 3: APLICAR DECISION SOBRE EL IMPUESTO");
            Console.WriteLine(new string('=', 80));

            EstadoFactura estado = s_estado
                ?? throw new InvalidOperationException("No hay estado de factura preparado.");

            // La respuesta MANDA: si se rechaza, el impuesto se pone a cero
            if (respuesta)
            {
                Console.WriteLine($"Impuesto CONFIRMADO: {Money(estado.TaxAmount)}");
                estado = estado with { TaxConfirmed = true };
            }
            else
            {
                Console.WriteLine("Impuesto OMITIDO (no se sumará al total)");
                estado = estado with { TaxConfirmed = false, TaxAmount = 0m };
            }

            s_estado = estado;

            await context.QueueStateUpdateAsync("paso", "impuesto_procesado", cancellationToken: ct);
            await context.QueueStateUpdateAsync("impuesto_confirmado", respuesta, cancellationToken: ct);

            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("PASO 4: CONFIRMAR DESCUENTO");
            Console.WriteLine(new string('=', 80));

            // Atajo: sin descuento no hay nada que preguntar. El workflow NO se
            // detiene y se salta directamente a la finalización.
            if (estado.DiscountAmount <= 0)
            {
                Console.WriteLine($"La factura {estado.InvoiceId} no tiene descuento aplicable.");
                Console.WriteLine("No se solicita confirmación: se continúa directamente.");
                await FinalizarAsync(estado with { DiscountConfirmed = false }, context, ct);
                return;
            }

            Console.WriteLine($"Factura: {estado.InvoiceId}");
            Console.WriteLine($"   Descuento total: {Money(estado.DiscountAmount)}");
            Console.WriteLine("\n>> El workflow se DETIENE aquí hasta recibir su respuesta...");

            await context.SendMessageAsync(new PeticionDescuento(
                estado.InvoiceId,
                $"¿Aplica el descuento a {estado.InvoiceId}?",
                estado.DiscountAmount,
                "Escriba 's' para aplicarlo o 'n' para omitirlo"), ct);
        }

        /// <summary>Ruta corta cuando no hay descuento que confirmar.</summary>
        private static async ValueTask FinalizarAsync(EstadoFactura estado, IWorkflowContext context,
                                                      CancellationToken ct)
        {
            s_estado = estado;
            await context.YieldOutputAsync(GenerarInforme(estado), ct);
        }
    }

    // =====================================================================
    // PASO 5 — recibe la decisión sobre el descuento y TERMINA el workflow
    // =====================================================================
    internal sealed partial class AplicarDescuento(string id) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(bool respuesta, IWorkflowContext context,
                                           CancellationToken ct = default)
        {
            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("PASO 5: APLICAR DECISION SOBRE EL DESCUENTO");
            Console.WriteLine(new string('=', 80));

            EstadoFactura estado = s_estado
                ?? throw new InvalidOperationException("No hay estado de factura preparado.");

            if (respuesta)
            {
                Console.WriteLine($"Descuento APLICADO: {Money(estado.DiscountAmount)}");
                estado = estado with { DiscountConfirmed = true };
            }
            else
            {
                Console.WriteLine("Descuento OMITIDO (no se restará del total)");
                estado = estado with { DiscountConfirmed = false, DiscountAmount = 0m };
            }

            s_estado = estado;

            await context.QueueStateUpdateAsync("paso", "descuento_procesado", cancellationToken: ct);
            await context.QueueStateUpdateAsync("descuento_confirmado", respuesta, cancellationToken: ct);

            await context.YieldOutputAsync(GenerarInforme(estado), ct);
        }
    }

    // =====================================================================
    // FINALIZACIÓN
    // =====================================================================

    /// <summary>
    /// Calcula el total según lo que decidió el humano, escribe el archivo y
    /// devuelve el resumen que se emite como salida del workflow.
    /// </summary>
    private static string GenerarInforme(EstadoFactura estado)
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("PASO 6: FINALIZAR FACTURA");
        Console.WriteLine(new string('=', 80));

        // AQUÍ SE VE EL EFECTO DEL HUMANO: cada importe se suma o resta solo si
        // fue confirmado.
        decimal total = estado.Subtotal;
        if (estado.TaxConfirmed) total += estado.TaxAmount;
        if (estado.DiscountConfirmed) total -= estado.DiscountAmount;

        Console.WriteLine($"Factura: {estado.InvoiceId}");
        Console.WriteLine($"   Cliente: {estado.ClientName}");
        Console.WriteLine($"   Subtotal: {Money(estado.Subtotal)}");
        Console.WriteLine($"   Impuesto: {(estado.TaxConfirmed ? Money(estado.TaxAmount) : "OMITIDO")}");
        Console.WriteLine($"   Descuento: {(estado.DiscountConfirmed ? "-" + Money(estado.DiscountAmount) : "OMITIDO")}");
        Console.WriteLine($"   TOTAL FINAL: {Money(total)}");

        EnsureDirectories(OutputDir, LogsDir);
        string ruta = Path.Combine(OutputDir, $"{estado.InvoiceId}_final.txt");

        // El documento deja constancia de QUÉ decidió el humano, no solo del total
        string[] lineas =
        [
            $"FACTURA: {estado.InvoiceId}",
            $"Cliente: {estado.ClientName}",
            $"Subtotal: {Money(estado.Subtotal)}",
            $"Impuesto: {(estado.TaxConfirmed ? Money(estado.TaxAmount) : "OMITIDO por el usuario")}",
            $"Descuento: {(estado.DiscountConfirmed ? "-" + Money(estado.DiscountAmount) : "OMITIDO por el usuario")}",
            $"TOTAL FINAL: {Money(total)}",
            "Estado: Completada con confirmaciones del usuario",
        ];
        File.WriteAllLines(ruta, lineas, System.Text.Encoding.UTF8);

        Console.WriteLine($"Archivo generado: {ruta}");

        LogAction($"Factura {estado.InvoiceId} finalizada por {Money(total)} " +
                  $"(impuesto={(estado.TaxConfirmed ? "si" : "no")}, " +
                  $"descuento={(estado.DiscountConfirmed ? "si" : "no")})");

        return $"¡Factura {estado.InvoiceId} completada con las confirmaciones del usuario! " +
               $"Total final: {Money(total)}";
    }

    // =====================================================================
    // INTERACCIÓN CON EL HUMANO
    // =====================================================================

    /// <summary>
    /// Muestra la petición del workflow por consola y devuelve la decisión.
    /// Devuelve <c>bool</c> porque es el tipo declarado en
    /// <c>RequestPort.Create&lt;TPeticion, bool&gt;</c>.
    /// </summary>
    private static bool PreguntarAlHumano(string pregunta, decimal valorActual, string opciones)
    {
        Console.WriteLine("\n" + new string('-', 80));
        Console.WriteLine("SE REQUIERE SU CONFIRMACION");
        Console.WriteLine(new string('-', 80));
        Console.WriteLine($"   {pregunta}");
        Console.WriteLine($"   Valor actual: {Money(valorActual)}");
        Console.WriteLine($"   {opciones}");

        while (true)
        {
            Console.Write("   Su respuesta (s/n): ");
            string r = Console.ReadLine()?.Trim().ToLowerInvariant() ?? "";
            if (r is "s" or "si" or "sí" or "y" or "yes") return true;
            if (r is "n" or "no") return false;
            Console.WriteLine("   Responda 's' o 'n'.");
        }
    }

    // =====================================================================
    // PUNTO DE ENTRADA
    // =====================================================================

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("WORKFLOW INTERACTIVO DE APROBACION DE FACTURAS");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("Esta demo combina:");
        Console.WriteLine("  - Interacción humana REAL (el workflow se detiene de verdad)");
        Console.WriteLine("  - Checkpointing automático en disco");
        Console.WriteLine("  - Correlación petición/respuesta mediante RequestPort tipados");
        Console.WriteLine(new string('=', 80));

        EnsureDirectories(OutputDir, LogsDir, CheckpointsDir);

        List<InvoiceData> todas = ReadInvoicesCsv();
        Console.WriteLine($"\nSe cargaron {todas.Count} facturas");
        InvoiceData elegida = ShowMenu(todas);

        LogAction($"Factura {elegida.InvoiceId} seleccionada para aprobación interactiva");

        var preparador = new PreparacionFactura("preparador");
        var aplicaImpuesto = new AplicarImpuesto("aplicar_impuesto");
        var aplicaDescuento = new AplicarDescuento("aplicar_descuento");

        // -----------------------------------------------------------------
        // CONSTRUCCIÓN DEL GRAFO CON PUERTOS DE PETICIÓN
        // -----------------------------------------------------------------
        // Fíjese en que los PUERTOS son nodos como cualquier otro: se conectan
        // con AddEdge. Una arista HACIA el puerto es "preguntar"; una arista
        // DESDE el puerto es "recibir la respuesta".
        Workflow workflow = new WorkflowBuilder(preparador)
            .AddEdge(preparador, PuertoImpuesto)          // pregunta por el impuesto
            .AddEdge(PuertoImpuesto, aplicaImpuesto)      // llega la respuesta
            .AddEdge(aplicaImpuesto, PuertoDescuento)     // pregunta por el descuento
            .AddEdge(PuertoDescuento, aplicaDescuento)    // llega la respuesta
            .WithOutputFrom(aplicaImpuesto, aplicaDescuento)  // ambos pueden terminar
            .WithName("facturacion_interactiva")
            .Build();

        Console.WriteLine("\nEstructura del workflow:");
        Console.WriteLine("   Preparar -> [puerto impuesto] -> Aplicar -> [puerto descuento] -> Aplicar/Finalizar");
        Console.WriteLine("   Se guardan checkpoints automáticamente en cada superstep");

        // -----------------------------------------------------------------
        // CHECKPOINTING EN DISCO
        // -----------------------------------------------------------------
        // FileSystemJsonCheckpointStore guarda el estado como JSON; el
        // CheckpointManager es quien lo orquesta. Equivale a
        // FileCheckpointStorage + checkpoint_storage= de Python.
        //
        // ✅ VENTAJA FRENTE A PYTHON: aquí se serializa con System.Text.Json, no
        // con pickle, así que NO hay lista blanca de tipos que declarar ni el
        // riesgo de que los checkpoints se escriban pero no se puedan leer.
        var store = new FileSystemJsonCheckpointStore(new DirectoryInfo(CheckpointsDir));
        CheckpointManager checkpointManager = CheckpointManager.CreateJson(store);

        StreamingRun run = await InProcessExecution.RunStreamingAsync(
            workflow, elegida, checkpointManager);

        int pausas = 0;
        string? salida = null;

        // -----------------------------------------------------------------
        // CICLO PAUSA → RESPUESTA → CONTINUACIÓN
        // -----------------------------------------------------------------
        // 🔴 DIFERENCIA CON PYTHON: aquí NO hay que reanudar con una segunda
        // llamada. Se responde con run.SendResponseAsync(...) SIN salir del
        // mismo `await foreach`, y el motor continúa solo.
        await foreach (WorkflowEvent evt in run.WatchStreamAsync())
        {
            if (evt is RequestInfoEvent peticion)
            {
                pausas++;
                bool respuesta;

                // Se identifica QUÉ se está preguntando por el tipo de la carga
                if (peticion.Request.TryGetDataAs(out PeticionImpuesto? pi) && pi is not null)
                {
                    respuesta = PreguntarAlHumano(pi.Pregunta, pi.ValorActual, pi.Opciones);
                }
                else if (peticion.Request.TryGetDataAs(out PeticionDescuento? pd) && pd is not null)
                {
                    respuesta = PreguntarAlHumano(pd.Pregunta, pd.ValorActual, pd.Opciones);
                }
                else
                {
                    Console.WriteLine("⚠️  Petición de tipo desconocido: se responde 'no'.");
                    respuesta = false;
                }

                Console.WriteLine("\n>> Enviando su respuesta al workflow...");
                await run.SendResponseAsync(peticion.Request.CreateResponse(respuesta));
            }
            else if (evt is WorkflowOutputEvent o)
            {
                salida = o.Data?.ToString();
            }
            else if (evt is ExecutorFailedEvent fallo)
            {
                Console.WriteLine($"\n❌ Falló un ejecutor: {fallo.Data}");
            }
        }

        if (salida is not null)
        {
            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("WORKFLOW COMPLETADO");
            Console.WriteLine(new string('=', 80));
            Console.WriteLine(salida);
            Console.WriteLine($"Pausas atendidas: {pausas}");
            Console.WriteLine(new string('=', 80));
        }

        // -----------------------------------------------------------------
        // RESUMEN DE CHECKPOINTS
        // -----------------------------------------------------------------
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("RESUMEN DE CHECKPOINTS");
        Console.WriteLine(new string('=', 80));

        try
        {
            IEnumerable<CheckpointInfo> checkpoints = await store.RetrieveIndexAsync(run.SessionId);
            var lista = checkpoints.ToList();

            if (lista.Count > 0)
            {
                Console.WriteLine($"Se crearon {lista.Count} checkpoints durante la ejecución");
                Console.WriteLine($"Guardados en: {CheckpointsDir}");
                foreach ((CheckpointInfo cp, int i) in lista.TakeLast(3).Select((c, i) => (c, i)))
                    Console.WriteLine($"   [{i}] {cp.CheckpointId}");
            }
            else
            {
                Console.WriteLine("No se encontraron checkpoints");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"No se pudieron listar los checkpoints: {ex.Message}");
        }

        Console.WriteLine("\nConceptos demostrados:");
        Console.WriteLine("   - Interacción humana real con RequestPort como nodo del grafo");
        Console.WriteLine("   - Respuesta enviada con run.SendResponseAsync(), sin reanudar");
        Console.WriteLine("   - Checkpointing automático en JSON (sin pickle ni lista blanca)");
        Console.WriteLine(new string('=', 80));
    }
}
