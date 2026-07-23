namespace Scenario1.FileOperationsServer;

/// <summary>
/// Espacio de trabajo aislado y guardián de seguridad de las rutas.
/// </summary>
internal static class Workspace
{
    // =========================================================================
    // [2] ESPACIO DE TRABAJO
    // =========================================================================
    // 🔒 Seg.: directorio base de todas las operaciones. El espacio de trabajo queda
    //    aislado del resto del disco.
    // ⚠️ Se ancla a la raíz de la solución, NO al directorio de trabajo actual: al
    //    lanzarse como subproceso MCP el "directorio actual" depende de quién lo
    //    lance, y los archivos acabarían en sitios distintos según el caso.
    public static readonly string BaseDir = ResolverEspacioDeTrabajo();

    private static string ResolverEspacioDeTrabajo()
    {
        // [2.1] Subir desde el ejecutable hasta encontrar la raíz de la solución.
        //       Ojo: el SDK de .NET 10 genera el formato nuevo `.slnx`, no `.sln`.
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null &&
               dir.GetFiles("*.sln").Length == 0 &&
               dir.GetFiles("*.slnx").Length == 0)
        {
            dir = dir.Parent;
        }

        var raiz = dir?.FullName ?? AppContext.BaseDirectory;
        var espacio = Path.Combine(raiz, "agent_workspace");
        Directory.CreateDirectory(espacio);
        return espacio;
    }

    // =========================================================================
    // [4] GUARDIÁN DE SEGURIDAD — se ejecuta al principio de CADA herramienta
    // =========================================================================
    /// <summary>Devuelve una ruta segura dentro del espacio de trabajo.</summary>
    /// <exception cref="UnauthorizedAccessException">Si la ruta se sale del espacio.</exception>
    public static string RutaSegura(string nombreArchivo)
    {
        var solicitada = Path.GetFullPath(Path.Combine(BaseDir, nombreArchivo));
        var raiz = Path.GetFullPath(BaseDir);

        // [4.1] 🔒 Seg.: comprobación anti-escape (evita rutas del tipo "../../secreto").
        //       ⚠️ Comparar con StartsWith() sobre las cadenas sería comparación de
        //       TEXTO, no de rutas: un directorio hermano llamado
        //       "agent_workspace_evil" pasaría el filtro. Por eso se compara
        //       añadiendo el separador final, que delimita el componente de ruta.
        var raizConSeparador = raiz.EndsWith(Path.DirectorySeparatorChar)
            ? raiz
            : raiz + Path.DirectorySeparatorChar;

        if (!solicitada.StartsWith(raizConSeparador, StringComparison.OrdinalIgnoreCase)
            && !string.Equals(solicitada, raiz, StringComparison.OrdinalIgnoreCase))
        {
            throw new UnauthorizedAccessException(
                $"Acceso denegado: la ruta '{nombreArchivo}' está fuera del espacio permitido");
        }

        return solicitada;
    }

    /// <summary>Ruta relativa al espacio de trabajo, para mostrarla al usuario.</summary>
    public static string RutaRelativa(string rutaAbsoluta) =>
        Path.GetRelativePath(BaseDir, rutaAbsoluta);

    public const string FormatoFecha = "yyyy-MM-dd HH:mm:ss";
}
