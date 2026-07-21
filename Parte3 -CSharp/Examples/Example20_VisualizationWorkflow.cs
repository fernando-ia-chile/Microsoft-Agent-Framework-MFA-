using Microsoft.Agents.AI.Workflows;
using MFA.CSharp.Part3.Infrastructure;
using static MFA.CSharp.Part3.Infrastructure.InvoiceUtils;

namespace MFA.CSharp.Part3.Examples;

/// <summary>
/// 20 · VISUALIZACIÓN de workflows.
/// Equivalente C# de <c>new_20_visualization_workflow.py</c>.
///
/// <para><b>Objetivo pedagógico:</b> los ejemplos 16-19 CONSTRUYEN y EJECUTAN grafos.
/// Este los <b>dibuja y los analiza</b>. Sirve para documentar, revisar y explicar un
/// workflow sin llegar a ejecutarlo.</para>
///
/// <code>
/// SECUENCIAL   A ─► B ─► C ─► D
/// PARALELO     A ─┬─► B ─┬─► D ─► E
///                 └─► C ─┘
/// RAMIFICADO   A ─┬─(caso 1)─► B ─┐
///                 ├─(caso 2)─► C ─┼─► E
///                 └─(defecto)─► D ─┘
/// </code>
///
/// <para><b>Conceptos clave:</b></para>
/// <list type="number">
///   <item><c>WorkflowVisualizer</c> dibuja el grafo YA CONSTRUIDO:
///   <c>ToMermaidString()</c> (Markdown, GitHub, mermaid.live) y
///   <c>ToDotString()</c> (Graphviz). Ambos son métodos ESTÁTICOS.</item>
///   <item>INTROSPECCIÓN: el objeto <c>Workflow</c> se puede interrogar sin
///   ejecutarlo — identificador, ejecutor inicial y puertos de entrada/salida.</item>
///   <item>AQUÍ NO SE EJECUTA NADA: los workflows se construyen solo para dibujarlos.
///   Por eso los ejecutores son mínimos, meros marcadores de posición: lo que importa
///   es la FORMA del grafo, no lo que hace cada paso.</item>
/// </list>
///
/// <para><b>NOTA:</b> este ejemplo NO usa ningún LLM y tampoco escribe facturas.</para>
/// </summary>
internal static partial class Example20_VisualizationWorkflow
{
    // =====================================================================
    // EJECUTORES (SOLO MARCADORES DE POSICIÓN)
    // =====================================================================
    // ⚠️ Estos ejecutores NUNCA se ejecutan: los workflows se construyen
    // únicamente para dibujarlos. Se mantienen mínimos a propósito — lo que se
    // visualiza es la TOPOLOGÍA, no la lógica de negocio (esa vive en
    // InvoiceUtils.cs y se demuestra en los ejemplos 16-19).

    internal sealed record LoteFacturas(IReadOnlyList<InvoiceData> Facturas);

    // --- Patrón 1: cadena secuencial ---

    /// <summary>Punto de ENTRADA del patrón secuencial: carga las facturas del CSV.</summary>
    internal sealed partial class CargarFacturas(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(string s, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(new LoteFacturas(ReadInvoicesCsv()), ct);
    }

    /// <summary>Paso intermedio: calcula los totales de cada factura.</summary>
    internal sealed partial class CalcularTotalesLote(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Paso intermedio: convierte cada factura en texto.</summary>
    internal sealed partial class RenderizarLote(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Paso TERMINAL: escribe los archivos y cierra el workflow.</summary>
    internal sealed partial class GuardarLote(string id) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.YieldOutputAsync("¡Todas las facturas guardadas!", ct);
    }

    // --- Patrón 2: fan-out / fan-in ---

    /// <summary>Punto de FAN-OUT: reparte el trabajo a las ramas paralelas.</summary>
    internal sealed partial class DispatcherViz(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(string s, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(new LoteFacturas(ReadInvoicesCsv()), ct);
    }

    /// <summary>Rama paralela 1: cálculo de importes.</summary>
    internal sealed partial class RamaTotales(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Rama paralela 2: preparación de datos del cliente.</summary>
    internal sealed partial class RamaCliente(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Punto de FAN-IN: reúne las ramas paralelas.</summary>
    internal sealed partial class FusionadorViz(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Paso TERMINAL del patrón paralelo.</summary>
    internal sealed partial class RenderizadorViz(string id) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.YieldOutputAsync("¡Renderizado completo!", ct);
    }

    // --- Patrón 3: ramificación condicional ---

    /// <summary>Punto de DECISIÓN: de aquí salen las aristas condicionales.</summary>
    internal sealed partial class AnalizadorViz(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(string s, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(new LoteFacturas(ReadInvoicesCsv()), ct);
    }

    /// <summary>Rama condicional: facturas de alto valor.</summary>
    internal sealed partial class RamaAltoValor(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Rama condicional: clientes preferentes.</summary>
    internal sealed partial class RamaPreferente(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Rama por DEFECTO: todo lo que no encaja en las anteriores.</summary>
    internal sealed partial class RamaEstandar(string id) : Executor(id)
    {
        [MessageHandler(Send = [typeof(LoteFacturas)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.SendMessageAsync(m, ct);
    }

    /// <summary>Punto de CONVERGENCIA y TERMINAL: las tres ramas acaban aquí.</summary>
    internal sealed partial class FinalizadorViz(string id) : Executor(id)
    {
        [MessageHandler(Yield = [typeof(string)])]
        public async ValueTask HandleAsync(LoteFacturas m, IWorkflowContext c, CancellationToken ct = default)
            => await c.YieldOutputAsync("¡Procesamiento completo!", ct);
    }

    // =====================================================================
    // CONSTRUCTORES DE LOS TRES GRAFOS
    // =====================================================================

    /// <summary>Construye la CADENA LINEAL: cada paso alimenta al siguiente.</summary>
    private static Workflow ConstruirSecuencial()
    {
        var cargar = new CargarFacturas("cargador");
        var calcular = new CalcularTotalesLote("calculadora");
        var renderizar = new RenderizarLote("renderizador");
        var guardar = new GuardarLote("guardador");

        return new WorkflowBuilder(cargar)
            .AddEdge(cargar, calcular)
            .AddEdge(calcular, renderizar)
            .AddEdge(renderizar, guardar)
            .WithOutputFrom(guardar)
            .WithName("secuencial")
            .Build();
    }

    /// <summary>
    /// Construye el patrón FAN-OUT / FAN-IN.
    /// <para>
    /// Se usan <c>AddFanOutEdge</c> y <c>AddFanInBarrierEdge</c> (en vez de
    /// <c>AddEdge</c> sueltos) porque expresan la intención real: difundir a varias
    /// ramas y ESPERAR a todas. Además el diagrama generado refleja esa barrera.
    /// </para>
    /// </summary>
    private static Workflow ConstruirParalelo()
    {
        var dispatcher = new DispatcherViz("dispatcher");
        var totales = new RamaTotales("calculadora_totales");
        var cliente = new RamaCliente("preparador_cliente");
        var fusionador = new FusionadorViz("fusionador");
        var renderizador = new RenderizadorViz("renderizador");

        return new WorkflowBuilder(dispatcher)
            .AddFanOutEdge(dispatcher, [totales, cliente])
            .AddFanInBarrierEdge([totales, cliente], fusionador)
            .AddEdge(fusionador, renderizador)
            .WithOutputFrom(renderizador)
            .WithName("paralelo")
            .Build();
    }

    /// <summary>Construye el patrón SWITCH con convergencia.</summary>
    private static Workflow ConstruirRamificado()
    {
        var analizador = new AnalizadorViz("analizador");
        var altoValor = new RamaAltoValor("manejador_alto_valor");
        var preferente = new RamaPreferente("manejador_preferente");
        var estandar = new RamaEstandar("manejador_estandar");
        var finalizador = new FinalizadorViz("finalizador");

        // Las condiciones reciben el MENSAJE y devuelven bool. Se declaran como
        // funciones locales para dejar clara su firma.
        var config = InvoiceConfig.Load();
        bool EsAltoValor(LoteFacturas? lote)
            => lote?.Facturas.Any(f => f.Subtotal >= config.HighValueThreshold) ?? false;
        bool EsPreferente(LoteFacturas? lote)
            => lote?.Facturas.Any(f => f.IsPreferred) ?? false;

        return new WorkflowBuilder(analizador)
            .AddSwitch(analizador, sw => sw
                .AddCase<LoteFacturas>(EsAltoValor, [altoValor])
                .AddCase<LoteFacturas>(EsPreferente, [preferente])
                .WithDefault([estandar]))
            .AddEdge(altoValor, finalizador)
            .AddEdge(preferente, finalizador)
            .AddEdge(estandar, finalizador)
            .WithOutputFrom(finalizador)
            .WithName("ramificado")
            .Build();
    }

    // =====================================================================
    // CATÁLOGO DE PATRONES
    // =====================================================================
    // Una sola tabla con constructor, título y uso. Tenerlo en un único sitio
    // evita que el menú, el análisis y el resumen final se contradigan.
    private sealed record Patron(string Clave, Func<Workflow> Constructor, string Titulo, string Uso);

    private static readonly Patron[] Patrones =
    [
        new("sequential", ConstruirSecuencial, "Workflow Secuencial",
            "Ideal para procesos paso a paso donde cada etapa depende de la anterior"),
        new("parallel", ConstruirParalelo, "Workflow Paralelo",
            "Ideal para tareas independientes que pueden ejecutarse a la vez"),
        new("branching", ConstruirRamificado, "Workflow Ramificado",
            "Ideal para enrutar según los datos o las reglas de negocio"),
    ];

    // =====================================================================
    // VISUALIZACIÓN
    // =====================================================================

    /// <summary>Genera y guarda los diagramas del workflow en Mermaid y DOT.</summary>
    private static void VisualizarWorkflow(Workflow workflow, string titulo, string clave)
    {
        Console.WriteLine($"\n{new string('=', 80)}");
        Console.WriteLine($"VISUALIZACION: {titulo}");
        Console.WriteLine($"{new string('=', 80)}\n");

        Directory.CreateDirectory(VisualizationsDir);

        // --- Formato Mermaid: se renderiza en Markdown, GitHub o mermaid.live
        Console.WriteLine("Diagrama Mermaid:");
        Console.WriteLine(new string('-', 80));
        string mermaid = WorkflowVisualizer.ToMermaidString(workflow);
        Console.WriteLine(mermaid);
        Console.WriteLine(new string('-', 80));

        string rutaMermaid = Path.Combine(VisualizationsDir, $"{clave}_workflow.mmd");
        File.WriteAllText(rutaMermaid, mermaid, System.Text.Encoding.UTF8);
        Console.WriteLine($"\nMermaid guardado en: {rutaMermaid}");

        // --- Formato DOT (Graphviz)
        // Genera TEXTO: no necesita tener Graphviz instalado. Graphviz solo haría
        // falta para convertir el .dot en imagen (dot -Tpng ...).
        string dot = WorkflowVisualizer.ToDotString(workflow);
        string rutaDot = Path.Combine(VisualizationsDir, $"{clave}_workflow.dot");
        File.WriteAllText(rutaDot, dot, System.Text.Encoding.UTF8);
        Console.WriteLine($"DOT guardado en:     {rutaDot}");

        Console.WriteLine("\n" + new string('=', 80));
    }

    /// <summary>
    /// Analiza el grafo INTERROGANDO al objeto Workflow, sin ejecutarlo.
    /// <para>
    /// .NET expone métodos de reflexión sobre el grafo — <c>ReflectExecutors()</c>,
    /// <c>ReflectEdges()</c>, <c>ReflectPorts()</c> — más las propiedades
    /// <c>Name</c> y <c>StartExecutorId</c>. Equivalen a <c>get_executors_list()</c>
    /// y <c>get_start_executor()</c> de Python.
    /// </para>
    /// <para>
    /// La ventaja frente a una descripción escrita a mano es que esto NO puede
    /// desincronizarse: si mañana cambia el grafo, el análisis cambia solo.
    /// </para>
    /// </summary>
    private static void AnalizarWorkflow(Workflow workflow, string titulo)
    {
        Console.WriteLine($"\nAnálisis: {titulo}");
        Console.WriteLine(new string('-', 80));

        // Se usa var: los tipos concretos (EdgeInfo, RequestPortInfo) viven en
        // subespacios internos del paquete y no aportan nada al ejemplo.
        var ejecutores = workflow.ReflectExecutors();
        var aristas = workflow.ReflectEdges();
        var puertos = workflow.ReflectPorts();

        Console.WriteLine($"Nombre del workflow: {workflow.Name}");
        Console.WriteLine($"Ejecutor inicial:    {workflow.StartExecutorId}");

        // Un ejecutor es "punto de salida" si no tiene aristas salientes
        Console.WriteLine($"\nEjecutores en el workflow ({ejecutores.Count}):");
        int i = 1;
        foreach (string id in ejecutores.Keys.OrderBy(k => k, StringComparer.Ordinal))
        {
            bool tieneSalientes = aristas.TryGetValue(id, out var salientes) && salientes.Count > 0;
            string papel = id == workflow.StartExecutorId ? "punto de entrada"
                         : tieneSalientes ? "intermedio"
                         : "punto de salida";
            Console.WriteLine($"  {i++}. {id,-24} ({papel})");
        }

        int totalAristas = aristas.Values.Sum(s => s.Count);
        Console.WriteLine($"\nGrupos de aristas: {aristas.Count} · aristas totales: {totalAristas}");
        foreach (var (origen, destinos) in aristas.OrderBy(k => k.Key, StringComparer.Ordinal))
            Console.WriteLine($"  {origen} --> {destinos.Count} conexión(es)");

        // Los puertos son los canales de petición/respuesta (human-in-the-loop).
        // Aquí siempre serán 0: ningún patrón de este ejemplo los usa (ver ejemplo 19).
        Console.WriteLine($"\nPuertos de petición (HITL): {puertos.Count}");

        Console.WriteLine(new string('-', 80));
    }

    // =====================================================================
    // MENÚ
    // =====================================================================

    /// <summary>
    /// Muestra el menú de patrones y devuelve los elegidos.
    /// Acepta una opción suelta ("2"), varias separadas por comas ("1,3") o la
    /// opción 4 para verlas todas.
    /// </summary>
    private static List<Patron> MostrarMenu()
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("OPCIONES DE VISUALIZACION DE WORKFLOWS");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("Seleccione qué patrones quiere visualizar:\n");
        Console.WriteLine("1. Workflow SECUENCIAL");
        Console.WriteLine("   • Procesamiento lineal (A -> B -> C -> D)");
        Console.WriteLine("   • Ideal para operaciones paso a paso\n");
        Console.WriteLine("2. Workflow PARALELO");
        Console.WriteLine("   • Procesamiento concurrente con fan-out/fan-in");
        Console.WriteLine("   • Ideal para tareas independientes simultáneas\n");
        Console.WriteLine("3. Workflow RAMIFICADO");
        Console.WriteLine("   • Enrutado condicional con switch");
        Console.WriteLine("   • Caminos distintos según las condiciones\n");
        Console.WriteLine("4. TODOS los workflows (demo completa)\n");

        while (true)
        {
            Console.Write("Indique su selección (1-4, o separadas por comas como '1,3'): ");
            string entrada = Console.ReadLine()?.Trim() ?? "";

            if (entrada == "4") return [.. Patrones];

            var seleccion = new List<Patron>();
            bool valido = true;

            foreach (string parte in entrada.Split(',', StringSplitOptions.RemoveEmptyEntries))
            {
                Patron? p = parte.Trim() switch
                {
                    "1" => Patrones[0],
                    "2" => Patrones[1],
                    "3" => Patrones[2],
                    _ => null,
                };

                if (p is null)
                {
                    Console.WriteLine($"Opción no válida: '{parte.Trim()}'. Introduzca 1, 2, 3 o 4.");
                    valido = false;
                    break;
                }

                // Se evitan duplicados si el usuario escribe "1,1"
                if (!seleccion.Contains(p)) seleccion.Add(p);
            }

            if (valido && seleccion.Count > 0) return seleccion;
            if (valido) Console.WriteLine("Seleccione al menos un patrón.");
        }
    }

    // =====================================================================
    // PUNTO DE ENTRADA
    // =====================================================================

    public static Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("GENERADOR DE FACTURAS - VISUALIZACION DE WORKFLOWS");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("\nEsta demo dibuja los distintos patrones de workflow:");
        Console.WriteLine("  • Secuencial  - Procesamiento lineal");
        Console.WriteLine("  • Paralelo    - Procesamiento concurrente con fan-out/fan-in");
        Console.WriteLine("  • Ramificado  - Enrutado condicional con switch");
        Console.WriteLine("\nFormatos de salida:");
        Console.WriteLine("  • Mermaid (.mmd) - para Markdown, GitHub y mermaid.live");
        Console.WriteLine("  • DOT (.dot)     - para Graphviz");
        Console.WriteLine("\nNOTA: aquí los workflows NO se ejecutan, solo se dibujan y analizan.");
        Console.WriteLine(new string('=', 80));

        EnsureDirectories(VisualizationsDir);

        List<Patron> seleccionados = MostrarMenu();

        Console.WriteLine($"\nPatrones seleccionados: {string.Join(", ", seleccionados.Select(p => p.Titulo))}");
        WaitForUser("iniciar la visualización");

        for (int i = 0; i < seleccionados.Count; i++)
        {
            Patron p = seleccionados[i];
            Console.WriteLine($"\n\n{new string('#', 80)}");
            Console.WriteLine($"#  {p.Titulo.ToUpperInvariant()}  ({i + 1} de {seleccionados.Count})");
            Console.WriteLine(new string('#', 80));

            Workflow workflow = p.Constructor();
            VisualizarWorkflow(workflow, p.Titulo, p.Clave);
            AnalizarWorkflow(workflow, p.Titulo);

            WaitForUser("continuar a la siguiente visualización");
        }

        // -----------------------------------------------------------------
        // RESUMEN FINAL
        // -----------------------------------------------------------------
        Console.WriteLine("\n\n" + new string('=', 80));
        Console.WriteLine("VISUALIZACION COMPLETADA");
        Console.WriteLine(new string('=', 80));
        Console.WriteLine($"\nDirectorio de salida: {VisualizationsDir}");
        Console.WriteLine("\nArchivos generados:");
        foreach (Patron p in seleccionados)
        {
            Console.WriteLine($"  • {p.Clave}_workflow.mmd (Mermaid)");
            Console.WriteLine($"  • {p.Clave}_workflow.dot (DOT/Graphviz)");
        }

        Console.WriteLine("\nCómo usarlos:");
        Console.WriteLine("  • Pegue el contenido de un .mmd en https://mermaid.live");
        Console.WriteLine("  • Los .mmd se renderizan solos dentro de un bloque ```mermaid en Markdown");
        Console.WriteLine("  • Para convertir un .dot en imagen: dot -Tpng archivo.dot -o archivo.png");

        Console.WriteLine("\nResumen de los patrones visualizados:");
        foreach (Patron p in seleccionados) Console.WriteLine($"  {p.Titulo}: {p.Uso}");

        Console.WriteLine("\n" + new string('=', 80));
        Console.WriteLine("¡Todos los patrones seleccionados se visualizaron correctamente!");
        Console.WriteLine(new string('=', 80));

        return Task.CompletedTask;
    }
}
