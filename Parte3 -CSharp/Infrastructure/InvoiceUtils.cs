using System.Globalization;
using Microsoft.Extensions.Configuration;

namespace MFA.CSharp.Part3.Infrastructure;

/// <summary>
/// Utilidades compartidas por los seis ejemplos de la Parte 3.
/// Equivalente C# de <c>invoice_utils.py</c>.
///
/// Es I/O + cálculo puro: NO depende de Microsoft.Agents.AI ni de ningún SDK de
/// Azure. La división de responsabilidades es la misma que en Python:
///
///     InvoiceUtils.cs   →  QUÉ se hace (lógica de negocio)
///     ExampleNN_*.cs    →  CÓMO se orquesta (topología del grafo)
/// </summary>
internal static class InvoiceUtils
{
    // Cultura invariante: los importes del CSV usan punto decimal y las facturas
    // deben salir igual en cualquier equipo, tenga la configuración regional que tenga.
    private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    // ---------------------------------------------------------------------
    // DIRECTORIOS
    // ---------------------------------------------------------------------
    // Se resuelven sobre AppContext.BaseDirectory (la carpeta del ejecutable),
    // no sobre el directorio actual: así los ejemplos funcionan igual tanto con
    // `dotnet run` como ejecutando el binario compilado.

    public static string BaseDir => AppContext.BaseDirectory;
    public static string DataDir => Path.Combine(BaseDir, "data");
    public static string OutputDir => Path.Combine(BaseDir, "output");
    public static string LogsDir => Path.Combine(BaseDir, "logs");
    public static string ArchiveDir => Path.Combine(BaseDir, "archive");
    public static string CheckpointsDir => Path.Combine(BaseDir, "checkpoints");
    public static string VisualizationsDir => Path.Combine(BaseDir, "visualizations");
    public static string CsvPath => Path.Combine(DataDir, "invoices.csv");

    /// <summary>Crea los directorios indicados si no existen (idempotente).</summary>
    public static void EnsureDirectories(params string[] dirs)
    {
        foreach (string dir in dirs) Directory.CreateDirectory(dir);
    }

    // ---------------------------------------------------------------------
    // MODELO DE DATOS
    // ---------------------------------------------------------------------

    /// <summary>
    /// Una factura leída del CSV.
    /// <para>
    /// Es un <c>record</c> y no una clase: se compara por valor, es inmutable por
    /// defecto y se puede copiar con <c>with</c>. Equivale al <c>@dataclass</c> de Python.
    /// </para>
    /// </summary>
    public sealed record InvoiceData(
        string InvoiceId,
        string ClientName,
        string ClientEmail,
        bool IsPreferred,
        string ItemDescription,
        int Quantity,
        decimal UnitPrice,
        string Date)
    {
        /// <summary>Subtotal = cantidad × precio unitario (antes de descuentos e impuestos).</summary>
        public decimal Subtotal => Quantity * UnitPrice;
    }

    /// <summary>
    /// Importes calculados de una factura.
    /// <para>
    /// ⚠️ DIFERENCIA CON PYTHON: allí esto es un <c>dict[str, float]</c> sin tipar, y
    /// el acceso es por cadena (<c>totals['tax']</c>). Aquí es un record con
    /// propiedades: el compilador detecta cualquier error de nombre.
    /// </para>
    /// </summary>
    public sealed record InvoiceTotals(
        decimal Subtotal,
        decimal HighValueDiscount,
        decimal PreferredDiscount,
        decimal TotalDiscount,
        decimal AmountAfterDiscount,
        decimal Tax,
        decimal Total);

    /// <summary>
    /// Configuración de negocio, leída de <c>appsettings03.json</c> (sección "Invoice").
    /// Equivale a la clase <c>InvoiceConfig</c> de Python, que lee variables INVOICE_*.
    /// Todos los valores tienen defecto, así que los ejemplos funcionan sin configurar nada.
    /// </summary>
    public sealed class InvoiceConfig
    {
        public decimal TaxRate { get; init; } = 0.10m;
        public decimal HighValueThreshold { get; init; } = 5000.00m;
        public decimal HighValueDiscount { get; init; } = 0.05m;
        public decimal PreferredClientDiscount { get; init; } = 0.03m;
        public string CompanyName { get; init; } = "TechServices Inc.";
        public string CompanyAddress { get; init; } = "123 Business St, Tech City, TC 12345";

        /// <summary>Carga la configuración; si falta el archivo o la sección, usa los valores por defecto.</summary>
        public static InvoiceConfig Load()
        {
            try
            {
                IConfiguration config = AppConfig.Load();
                IConfigurationSection s = config.GetSection("Invoice");
                if (!s.Exists()) return new InvoiceConfig();

                var def = new InvoiceConfig();
                return new InvoiceConfig
                {
                    TaxRate = ParseDecimal(s["TaxRate"], def.TaxRate),
                    HighValueThreshold = ParseDecimal(s["HighValueThreshold"], def.HighValueThreshold),
                    HighValueDiscount = ParseDecimal(s["HighValueDiscount"], def.HighValueDiscount),
                    PreferredClientDiscount = ParseDecimal(s["PreferredDiscount"], def.PreferredClientDiscount),
                    CompanyName = s["CompanyName"] ?? def.CompanyName,
                    CompanyAddress = s["CompanyAddress"] ?? def.CompanyAddress,
                };
            }
            catch (FileNotFoundException)
            {
                // Sin appsettings03.json las demos 16-20 deben seguir funcionando
                return new InvoiceConfig();
            }
        }

        private static decimal ParseDecimal(string? raw, decimal fallback)
            => decimal.TryParse(raw, NumberStyles.Any, Inv, out decimal v) ? v : fallback;

        public override string ToString()
            => $"InvoiceConfig(impuesto={Pct(TaxRate)}, umbral={Money(HighValueThreshold)}, " +
               $"descAltoValor={Pct(HighValueDiscount)}, descPreferente={Pct(PreferredClientDiscount)})";
    }

    // ---------------------------------------------------------------------
    // FORMATO
    // ---------------------------------------------------------------------

    /// <summary>Formatea una tasa (0.10) como porcentaje legible ("10%", "7.5%").</summary>
    public static string Pct(decimal rate)
    {
        decimal valor = rate * 100m;
        // Quita ceros a la derecha: 10,00 -> "10"  |  7,50 -> "7.5"
        return valor.ToString("0.##", Inv) + "%";
    }

    /// <summary>Formatea un importe como "$1234.56" con punto decimal siempre.</summary>
    public static string Money(decimal amount) => "$" + amount.ToString("0.00", Inv);

    /// <summary>Igual que <see cref="Money"/> pero con separador de miles: "$1,234.56".</summary>
    public static string MoneyGrouped(decimal amount) => "$" + amount.ToString("#,##0.00", Inv);

    // ---------------------------------------------------------------------
    // LECTURA DEL CSV
    // ---------------------------------------------------------------------

    /// <summary>
    /// Lee las facturas del CSV.
    /// <para>
    /// Se aplica Trim() a cada campo para tolerar espacios accidentales, que de
    /// otro modo romperían el parseo numérico o el flag de cliente preferente.
    /// </para>
    /// </summary>
    public static List<InvoiceData> ReadInvoicesCsv(string? csvPath = null)
    {
        csvPath ??= CsvPath;
        if (!File.Exists(csvPath))
        {
            throw new FileNotFoundException(
                $"No se encontró '{csvPath}'. Verifica que el .csproj copie data/invoices.csv a la salida.");
        }

        var invoices = new List<InvoiceData>();
        string[] lines = File.ReadAllLines(csvPath);
        if (lines.Length < 2) return invoices;

        // Cabecera → índice de columna, para no depender del orden del archivo
        string[] header = lines[0].Split(',').Select(h => h.Trim()).ToArray();
        int Idx(string name) => Array.IndexOf(header, name);

        int iId = Idx("invoice_id"), iName = Idx("client_name"), iEmail = Idx("client_email");
        int iPref = Idx("is_preferred"), iDesc = Idx("item_description");
        int iQty = Idx("quantity"), iPrice = Idx("unit_price"), iDate = Idx("date");

        foreach (string line in lines.Skip(1))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            string[] f = line.Split(',');
            if (f.Length < header.Length) continue;

            invoices.Add(new InvoiceData(
                InvoiceId: f[iId].Trim(),
                ClientName: f[iName].Trim(),
                ClientEmail: f[iEmail].Trim(),
                IsPreferred: string.Equals(f[iPref].Trim(), "true", StringComparison.OrdinalIgnoreCase),
                ItemDescription: f[iDesc].Trim(),
                Quantity: int.Parse(f[iQty].Trim(), Inv),
                UnitPrice: decimal.Parse(f[iPrice].Trim(), NumberStyles.Any, Inv),
                Date: f[iDate].Trim()));
        }

        return invoices;
    }

    // ---------------------------------------------------------------------
    // CÁLCULO
    // ---------------------------------------------------------------------

    /// <summary>
    /// Calcula descuentos, impuesto y total de una factura.
    /// <para>
    /// Orden de aplicación (importa): los descuentos se restan del subtotal y el
    /// impuesto se calcula sobre el importe YA descontado, no sobre el subtotal.
    /// Los dos descuentos son ACUMULABLES.
    /// </para>
    /// </summary>
    public static InvoiceTotals CalculateInvoiceTotals(InvoiceData invoice, InvoiceConfig config)
    {
        decimal subtotal = invoice.Subtotal;

        // Descuento por alto valor: se aplica si el subtotal ALCANZA el umbral (>=)
        decimal highValueDiscount = subtotal >= config.HighValueThreshold
            ? subtotal * config.HighValueDiscount
            : 0m;

        // Descuento por cliente preferente: independiente del monto
        decimal preferredDiscount = invoice.IsPreferred
            ? subtotal * config.PreferredClientDiscount
            : 0m;

        decimal totalDiscount = highValueDiscount + preferredDiscount;
        decimal amountAfterDiscount = subtotal - totalDiscount;

        // El impuesto grava el importe ya descontado
        decimal tax = amountAfterDiscount * config.TaxRate;
        decimal total = amountAfterDiscount + tax;

        return new InvoiceTotals(
            Subtotal: subtotal,
            HighValueDiscount: highValueDiscount,
            PreferredDiscount: preferredDiscount,
            TotalDiscount: totalDiscount,
            AmountAfterDiscount: amountAfterDiscount,
            Tax: tax,
            Total: total);
    }

    // ---------------------------------------------------------------------
    // RENDERIZADO Y PERSISTENCIA
    // ---------------------------------------------------------------------

    /// <summary>Renderiza la factura como texto plano de 80 columnas.</summary>
    public static string RenderInvoiceText(InvoiceData invoice, InvoiceTotals t, InvoiceConfig config)
    {
        var sb = new System.Text.StringBuilder();
        string linea = new('=', 80);
        string guion = new('-', 80);

        sb.AppendLine(linea);
        sb.AppendLine(Center(config.CompanyName, 80));
        sb.AppendLine(Center(config.CompanyAddress, 80));
        sb.AppendLine(linea);
        sb.AppendLine();
        sb.AppendLine($"FACTURA: {invoice.InvoiceId}");
        sb.AppendLine($"Fecha: {invoice.Date}");
        sb.AppendLine();
        sb.AppendLine("Facturar a:");
        sb.AppendLine($"  {invoice.ClientName}");
        sb.AppendLine($"  {invoice.ClientEmail}");
        if (invoice.IsPreferred) sb.AppendLine("  * CLIENTE PREFERENTE");
        sb.AppendLine();
        sb.AppendLine(guion);
        sb.AppendLine($"{"DESCRIPCION",-40} {"CANT.",-10} {"PRECIO",-15} {"IMPORTE",15}");
        sb.AppendLine(guion);
        sb.AppendLine($"{invoice.ItemDescription,-40} {invoice.Quantity,-10} " +
                      $"{Money(invoice.UnitPrice),-15} {Money(t.Subtotal),15}");
        sb.AppendLine();
        sb.AppendLine($"{"Subtotal:",-58} {Money(t.Subtotal),20}");

        // Los porcentajes se DERIVAN de la config: escritos a mano mentirían si se
        // cambiara una tasa en appsettings03.json.
        if (t.HighValueDiscount > 0)
            sb.AppendLine($"{$"Descuento por alto valor ({Pct(config.HighValueDiscount)}):",-58} {"-" + Money(t.HighValueDiscount),20}");

        if (t.PreferredDiscount > 0)
            sb.AppendLine($"{$"Descuento cliente preferente ({Pct(config.PreferredClientDiscount)}):",-58} {"-" + Money(t.PreferredDiscount),20}");

        if (t.TotalDiscount > 0)
            sb.AppendLine($"{"Importe tras descuentos:",-58} {Money(t.AmountAfterDiscount),20}");

        sb.AppendLine($"{$"Impuesto ({Pct(config.TaxRate)}):",-58} {Money(t.Tax),20}");
        sb.AppendLine(guion);
        sb.AppendLine($"{"TOTAL A PAGAR:",-58} {Money(t.Total),20}");
        sb.AppendLine(linea);
        sb.AppendLine();
        sb.AppendLine("¡Gracias por su confianza!");
        sb.AppendLine();

        return sb.ToString();
    }

    /// <summary>Guarda la factura en el directorio de salida y devuelve la ruta escrita.</summary>
    public static string SaveInvoiceFile(string invoiceId, string content, string? outputDir = null)
    {
        outputDir ??= OutputDir;
        Directory.CreateDirectory(outputDir);
        string filePath = Path.Combine(outputDir, $"{invoiceId}.txt");
        File.WriteAllText(filePath, content, System.Text.Encoding.UTF8);
        return filePath;
    }

    /// <summary>
    /// Archiva la factura anterior, si existe, añadiéndole una marca de tiempo.
    /// Devuelve true si se archivó algo.
    /// </summary>
    public static bool ArchiveOldInvoice(string invoiceId, string? outputDir = null, string? archiveDir = null)
    {
        outputDir ??= OutputDir;
        archiveDir ??= ArchiveDir;

        string source = Path.Combine(outputDir, $"{invoiceId}.txt");
        if (!File.Exists(source)) return false;

        Directory.CreateDirectory(archiveDir);   // el destino debe existir o Move falla
        string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
        File.Move(source, Path.Combine(archiveDir, $"{invoiceId}_{stamp}.txt"));
        return true;
    }

    /// <summary>Añade una línea con marca de tiempo al log del workflow.</summary>
    public static void LogAction(string message, string? logDir = null, string logFile = "invoice_workflow.log")
    {
        logDir ??= LogsDir;
        Directory.CreateDirectory(logDir);
        string stamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", Inv);
        File.AppendAllText(Path.Combine(logDir, logFile), $"[{stamp}] {message}{Environment.NewLine}",
                           System.Text.Encoding.UTF8);
    }

    // ---------------------------------------------------------------------
    // SALIDA POR CONSOLA
    // ---------------------------------------------------------------------

    /// <summary>Imprime la cabecera de un paso del workflow.</summary>
    public static void PrintStep(int stepNumber, string stepName, string details = "")
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 80));
        Console.WriteLine($"PASO {stepNumber}: {stepName}");
        Console.WriteLine(new string('=', 80));
        if (!string.IsNullOrWhiteSpace(details)) Console.WriteLine(details);
    }

    /// <summary>Imprime un resumen compacto de la factura.</summary>
    public static void PrintInvoiceSummary(InvoiceData invoice, InvoiceTotals t)
    {
        Console.WriteLine();
        Console.WriteLine($"📄 Factura: {invoice.InvoiceId}");
        Console.WriteLine($"   Cliente: {invoice.ClientName} {(invoice.IsPreferred ? "⭐" : "")}");
        Console.WriteLine($"   Concepto: {invoice.ItemDescription}");
        Console.WriteLine($"   Cantidad: {invoice.Quantity} x {Money(invoice.UnitPrice)}");
        Console.WriteLine($"   Subtotal: {Money(t.Subtotal)}");
        if (t.TotalDiscount > 0) Console.WriteLine($"   Descuento: -{Money(t.TotalDiscount)}");
        Console.WriteLine($"   Impuesto: {Money(t.Tax)}");
        Console.WriteLine($"   💰 TOTAL: {Money(t.Total)}");
    }

    // ---------------------------------------------------------------------
    // INTERACCIÓN
    // ---------------------------------------------------------------------

    /// <summary>
    /// Muestra el menú de facturas y devuelve la elegida.
    /// Repite hasta recibir un número válido: la demo no debe caerse por un typo.
    /// </summary>
    public static InvoiceData ShowMenu(IReadOnlyList<InvoiceData> invoices, bool marcarExistentes = false)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 80));
        Console.WriteLine("FACTURAS DISPONIBLES");
        Console.WriteLine(new string('=', 80));

        for (int i = 0; i < invoices.Count; i++)
        {
            InvoiceData inv = invoices[i];
            string insignia = inv.IsPreferred ? "PREFERENTE" : "ESTANDAR  ";
            string yaExiste = marcarExistentes && File.Exists(Path.Combine(OutputDir, $"{inv.InvoiceId}.txt"))
                ? "  [YA EXISTE -> se archivará]"
                : "";
            Console.WriteLine($"{i + 1,2}. {insignia} {inv.InvoiceId} - {inv.ClientName}{yaExiste}");
            Console.WriteLine($"    Importe: {Money(inv.Subtotal)} | Fecha: {inv.Date}");
        }

        while (true)
        {
            Console.Write($"\nSeleccione una factura (1-{invoices.Count}): ");
            string? raw = Console.ReadLine()?.Trim();
            if (int.TryParse(raw, out int idx) && idx >= 1 && idx <= invoices.Count)
                return invoices[idx - 1];
            Console.WriteLine($"Introduzca un número entre 1 y {invoices.Count}");
        }
    }

    /// <summary>
    /// Pausa hasta que el usuario pulse ENTER.
    /// Es lo que hace visible el avance PASO A PASO del workflow.
    /// </summary>
    public static void WaitForUser(string mensaje)
    {
        Console.WriteLine();
        Console.WriteLine(new string('-', 80));
        Console.Write($"Pulse ENTER para {mensaje} -> ");
        Console.ReadLine();
        Console.WriteLine(new string('-', 80));
        Console.WriteLine();
    }

    /// <summary>Centra un texto en un ancho dado (equivale a str.center() de Python).</summary>
    private static string Center(string text, int width)
    {
        if (text.Length >= width) return text;
        int left = (width - text.Length) / 2;
        return new string(' ', left) + text;
    }
}
