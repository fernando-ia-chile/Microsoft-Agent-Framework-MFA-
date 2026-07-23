using System.ComponentModel;
using ModelContextProtocol.Server;

namespace Scenario1.FileOperationsServer;

/// <summary>
/// Las cinco herramientas que este servidor publica por MCP.
/// </summary>
// 🔌 MCP: [McpServerToolType] marca la clase para que el SDK descubra sus
//    herramientas automáticamente al arrancar (WithToolsFromAssembly en Program.cs).
[McpServerToolType]
public static class FileTools
{
    // =========================================================================
    // [5] HERRAMIENTA MCP: leer un archivo
    // =========================================================================
    // 🔌 MCP: las propiedades del atributo son PISTAS DE COMPORTAMIENTO para el
    //    cliente. No cambian lo que hace el método: describen qué efectos tiene,
    //    para que el cliente pueda decidir si pedir confirmación, si reintentar, etc.
    //      ReadOnly    -> no modifica nada
    //      Destructive -> puede destruir datos
    //      Idempotent  -> repetirla no provoca efectos adicionales
    //      OpenWorld   -> toca sistemas externos (internet, etc.)
    //    ⚠️ Aquí OpenWorld = false: este servidor solo trabaja sobre un espacio
    //    local y aislado. En el servidor de clima es true, porque sale a internet.
    [McpServerTool(
        Name = "read_file",
        Title = "Leer archivo",
        ReadOnly = true,
        Idempotent = true,
        OpenWorld = false)]
    [Description("Lee y devuelve el contenido completo de un archivo de texto.")]
    public static async Task<string> ReadFileAsync(
        [Description("Nombre del archivo, relativo al espacio de trabajo")] string filename,
        CancellationToken ct = default)
    {
        var ruta = Workspace.RutaSegura(filename);

        // [5.1] Los errores se lanzan como EXCEPCIÓN. MCP las transporta al cliente
        //       como error de herramienta, y el agente puede explicárselo al usuario.
        //       Devolver el texto "Error: ..." como si fuera contenido válido haría
        //       que el modelo no pudiera distinguir un fallo de un archivo cuyo
        //       contenido empezara por "Error:".
        if (!File.Exists(ruta))
            throw new FileNotFoundException($"El archivo '{filename}' no existe.");

        return await File.ReadAllTextAsync(ruta, ct);
    }

    // =========================================================================
    // [6] HERRAMIENTA MCP: escribir un archivo
    // =========================================================================
    // 🔌 MCP: UseStructuredContent = true activa la salida estructurada; sin él, el
    //    resultado viajaría serializado como texto plano.
    [McpServerTool(
        Name = "write_file",
        Title = "Escribir archivo",
        ReadOnly = false,
        Destructive = false,
        OpenWorld = false,
        UseStructuredContent = true)]
    [Description("Escribe contenido en un archivo del espacio de trabajo. Por defecto sobrescribe; con append=true añade al final.")]
    public static async Task<ResultadoOperacion> WriteFileAsync(
        [Description("Nombre del archivo a escribir")] string filename,
        [Description("Contenido que se va a guardar")] string content,
        [Description("true para añadir al final en vez de sobrescribir")] bool append = false,
        CancellationToken ct = default)
    {
        var ruta = Workspace.RutaSegura(filename);

        // [6.1] Crear los directorios intermedios si no existen.
        Directory.CreateDirectory(Path.GetDirectoryName(ruta)!);

        if (append)
            await File.AppendAllTextAsync(ruta, content, ct);
        else
            await File.WriteAllTextAsync(ruta, content, ct);

        var accion = append ? "añadido a" : "escrito en";

        // [6.2] 🔌 MCP: devolver el record. El cliente recibe además su esquema.
        return new ResultadoOperacion(
            Archivo: filename,
            Exito: true,
            Mensaje: $"Contenido {accion} '{filename}' correctamente ({content.Length} caracteres)",
            Caracteres: content.Length);
    }

    // =========================================================================
    // [7] HERRAMIENTA MCP: listar archivos
    // =========================================================================
    [McpServerTool(
        Name = "list_files",
        Title = "Listar archivos",
        ReadOnly = true,
        Idempotent = true,
        OpenWorld = false,
        UseStructuredContent = true)]
    [Description("Lista los archivos de un directorio del espacio de trabajo, con filtro opcional.")]
    public static Task<ListadoArchivos> ListFilesAsync(
        [Description("Directorio a listar, relativo al espacio de trabajo")] string directory = ".",
        [Description("Patrón glob, p. ej. '*.txt'")] string pattern = "*",
        CancellationToken ct = default)
    {
        var ruta = Workspace.RutaSegura(directory);

        if (!Directory.Exists(ruta))
            throw new DirectoryNotFoundException($"El directorio '{directory}' no existe.");

        // [7.1] Recorrer las coincidencias y armar una entrada por cada una.
        var entradas = new List<ArchivoListado>();

        foreach (var elemento in Directory.EnumerateFileSystemEntries(ruta, pattern).OrderBy(x => x))
        {
            var esDirectorio = Directory.Exists(elemento);
            var info = new FileInfo(elemento);

            entradas.Add(new ArchivoListado(
                Nombre: Workspace.RutaRelativa(elemento),
                Tipo: esDirectorio ? "DIRECTORIO" : "ARCHIVO",
                TamanoBytes: esDirectorio ? 0 : info.Length,
                Modificado: info.LastWriteTime.ToString(Workspace.FormatoFecha)));
        }

        // [7.2] `Total` viaja explícito en la respuesta. Con una salida en texto plano
        //       habría que contar las líneas para saber cuántos elementos hay.
        return Task.FromResult(new ListadoArchivos(directory, pattern, entradas.Count, entradas));
    }

    // =========================================================================
    // [8] HERRAMIENTA MCP: borrar un archivo
    // =========================================================================
    // 🔌 MCP: Destructive = true avisa al cliente de que esta herramienta DESTRUYE
    //    datos. Es la pista que permite exigir aprobación humana antes de ejecutarla.
    [McpServerTool(
        Name = "delete_file",
        Title = "Borrar archivo",
        ReadOnly = false,
        Destructive = true,
        Idempotent = false,
        OpenWorld = false,
        UseStructuredContent = true)]
    [Description("Borra un archivo del espacio de trabajo. La operación no se puede deshacer.")]
    public static Task<ResultadoOperacion> DeleteFileAsync(
        [Description("Nombre del archivo a borrar")] string filename,
        CancellationToken ct = default)
    {
        var ruta = Workspace.RutaSegura(filename);

        if (Directory.Exists(ruta))
            throw new InvalidOperationException($"'{filename}' es un directorio, no un archivo.");

        if (!File.Exists(ruta))
            throw new FileNotFoundException($"El archivo '{filename}' no existe.");

        File.Delete(ruta);

        return Task.FromResult(new ResultadoOperacion(
            Archivo: filename,
            Exito: true,
            Mensaje: $"Archivo '{filename}' borrado correctamente"));
    }

    // =========================================================================
    // [9] HERRAMIENTA MCP: información de un archivo
    // =========================================================================
    [McpServerTool(
        Name = "file_info",
        Title = "Información de archivo",
        ReadOnly = true,
        Idempotent = true,
        OpenWorld = false,
        UseStructuredContent = true)]
    [Description("Devuelve el tamaño y las fechas de creación, modificación y acceso de un archivo.")]
    public static Task<InfoArchivo> FileInfoAsync(
        [Description("Nombre del archivo a consultar")] string filename,
        CancellationToken ct = default)
    {
        var ruta = Workspace.RutaSegura(filename);

        var esDirectorio = Directory.Exists(ruta);
        if (!esDirectorio && !File.Exists(ruta))
            throw new FileNotFoundException($"'{filename}' no existe.");

        var info = new FileInfo(ruta);

        return Task.FromResult(new InfoArchivo(
            Nombre: filename,
            Tipo: esDirectorio ? "DIRECTORIO" : "ARCHIVO",
            TamanoBytes: esDirectorio ? 0 : info.Length,
            Creado: info.CreationTime.ToString(Workspace.FormatoFecha),
            Modificado: info.LastWriteTime.ToString(Workspace.FormatoFecha),
            Accedido: info.LastAccessTime.ToString(Workspace.FormatoFecha),
            RutaAbsoluta: ruta));
    }
}
