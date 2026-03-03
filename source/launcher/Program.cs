using System;
using System.Threading;
using System.IO;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.IO.Compression;
using System.Collections;
using System.Diagnostics;
using System.Windows.Forms;
using System.Drawing;
using System.Linq;
using Microsoft.Win32;
using System.Security.Cryptography;
using System.Collections.Generic;

namespace qDiffusion
{
    class Worker
    {
        private static readonly object CrashLogLock = new object();

        [DllImport("shell32.dll", SetLastError = true)]
        static extern void SetCurrentProcessExplicitAppUserModelID([MarshalAs(UnmanagedType.LPWStr)] string AppID);

        private const string PythonVersion = "3.14.3";
        private const string PythonArchive = "python-3.14.3-amd64.zip";
        private const string PythonDownloadUrl = "https://www.python.org/ftp/python/3.14.3/python-3.14.3-amd64.zip";
        // Official SHA256 from python.org windows-3.14.3.json (PythonCore 3.14.3 x64)
        private const string PythonSha256 = "ec781bb03f9638d136b24da7c83b4db1652ce767848aa856a30bb87cfdb1abe4";
        private const string PythonMarkerFile = @"python\.qdiff_python_version";
        private const string PipMarkerFile = @".venv\.qdiff_pip_upgraded";
        private const string PySideMarkerFile = @".venv\.qdiff_pyside6_6.10.2_installed";
        private const string RequiredPySideVersion = "6.10.2";
        private const string PythonPackageIndex = "https://pypi.org/simple";

        private Dialog progress;

        public static void AppendCrashLog(string message)
        {
            if (message == null)
            {
                return;
            }

            string logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launcher_crash.log");
            string timestampedMessage = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] {message}{Environment.NewLine}";

            lock (CrashLogLock)
            {
                File.AppendAllText(logPath, timestampedMessage);
            }
        }

        private void LaunchProgress()
        {
            if (progress == null)
            {
                new Thread(delegate ()
                {
                    progress = new Dialog();
                    progress.Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
                    Application.Run(progress);
                }).Start();

                while (progress == null)
                {
                    Thread.Sleep(1); //SPIN!!
                }
            }
        }

        private void LaunchError(string error)
        {
            MessageBox.Show(error, "Error occurred", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }

        static void RegisterProtocol(string exe)
        {
            RegistryKey key = Registry.CurrentUser.OpenSubKey(@"Software\Classes\qDiffusion");

            bool replace = false;
            if (key != null)
            {
                replace = true;
                var command = key.OpenSubKey(@"shell\open\command");
                if (command != null)
                {
                    string value = (string)command.GetValue(string.Empty);
                    if (value != null && value.Contains(exe))
                    {
                        replace = false;
                    }
                }
            }

            if (replace)
            {
                Registry.CurrentUser.DeleteSubKeyTree(@"Software\Classes\qDiffusion");
                key = null;
            }

            if (key == null)
            {
                key = Registry.CurrentUser.CreateSubKey(@"Software\Classes\qDiffusion");
                key.SetValue(string.Empty, "URL:qDiffusion");
                key.SetValue("URL Protocol", string.Empty);

                var icon = key.CreateSubKey("DefaultIcon");
                icon.SetValue(string.Empty, "\"" + exe + "\",1");
                icon.Close();

                var command = key.CreateSubKey(@"shell\open\command");
                command.SetValue(string.Empty, "\"" + exe + "\" \"%1\"");
                command.Close();
            }

            key.Close();
        }

        private void HandleDownloadProgress(object sender, DownloadProgressChangedEventArgs args)
        {
            progress?.SetProgress(Math.Min(99, args.ProgressPercentage));
        }

        private bool Download(string url, string filename)
        {
            using (WebClient wc = new WebClient())
            using (var syncEvent = new ManualResetEvent(false))
            {
                wc.DownloadProgressChanged += HandleDownloadProgress;

                Exception downloadError = null;
                wc.DownloadFileCompleted += (sender, args) =>
                {
                    downloadError = args.Error;
                    syncEvent.Set();
                };

                wc.DownloadFileAsync(new Uri(url), filename);
                syncEvent.WaitOne();

                if (downloadError != null)
                {
                    LaunchError(downloadError.Message);
                    return false;
                }
                return true;
            }
        }

        public static string MD5(string input)
        {
            using (System.Security.Cryptography.MD5 md5 = System.Security.Cryptography.MD5.Create())
            {
                byte[] inputBytes = Encoding.ASCII.GetBytes(input);
                byte[] hashBytes = md5.ComputeHash(inputBytes);
                StringBuilder hex = new StringBuilder(hashBytes.Length * 2);
                foreach (byte b in hashBytes)
                {
                    hex.AppendFormat("{0:x2}", b);
                }
                return hex.ToString();
            }
        }

        public static string QuoteArg(string arg)
        {
            if (arg == null)
            {
                return "\"\"";
            }

            if (arg.Length == 0)
            {
                return "\"\"";
            }

            bool needsQuotes = arg.Any(ch => char.IsWhiteSpace(ch) || ch == '"');
            if (!needsQuotes)
            {
                return arg;
            }

            var sb = new StringBuilder();
            sb.Append('"');
            int backslashes = 0;
            foreach (char c in arg)
            {
                if (c == '\\')
                {
                    backslashes++;
                    continue;
                }

                if (c == '"')
                {
                    sb.Append(new string('\\', backslashes * 2 + 1));
                    sb.Append('"');
                    backslashes = 0;
                    continue;
                }

                if (backslashes > 0)
                {
                    sb.Append(new string('\\', backslashes));
                    backslashes = 0;
                }
                sb.Append(c);
            }

            if (backslashes > 0)
            {
                sb.Append(new string('\\', backslashes * 2));
            }
            sb.Append('"');
            return sb.ToString();
        }

        private static string BuildArguments(string[] args)
        {
            if (args.Length <= 1)
            {
                return string.Empty;
            }
            return string.Join(" ", args.Skip(1).Select(QuoteArg).ToArray());
        }

        private static void ApplyEnvironment(ProcessStartInfo startInfo, IDictionary<string, string> environment)
        {
            if (environment == null)
            {
                return;
            }

            startInfo.EnvironmentVariables.Clear();
            foreach (var kvp in environment)
            {
                startInfo.EnvironmentVariables[kvp.Key] = kvp.Value ?? string.Empty;
            }
        }

        public static string Run(IDictionary<string, string> environment, params string[] args)
        {
            string command = args[0];
            string arguments = BuildArguments(args);

            ProcessStartInfo startInfo = new ProcessStartInfo(command, arguments)
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            ApplyEnvironment(startInfo, environment);

            using (Process process = new Process { StartInfo = startInfo })
            {
                var stdout = new StringBuilder();
                var stderr = new StringBuilder();

                process.OutputDataReceived += (s, e) =>
                {
                    if (e.Data != null)
                    {
                        lock (stdout) { stdout.AppendLine(e.Data); }
                    }
                };
                process.ErrorDataReceived += (s, e) =>
                {
                    if (e.Data != null)
                    {
                        lock (stderr) { stderr.AppendLine(e.Data); }
                    }
                };

                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();

                if (process.ExitCode != 0)
                {
                    var error = stderr.ToString();
                    if (string.IsNullOrWhiteSpace(error))
                    {
                        error = stdout.ToString();
                    }
                    throw new Exception(string.IsNullOrWhiteSpace(error)
                        ? "Process failed with exit code " + process.ExitCode
                        : error.Trim());
                }

                var output = stdout.ToString();
                if (string.IsNullOrWhiteSpace(output))
                {
                    output = stderr.ToString();
                }
                return output;
            }
        }

        public static string Run(params string[] args)
        {
            return Run(null, args);
        }

        public static void Launch(IDictionary<string, string> environment, params string[] args)
        {
            string command = args[0];
            string arguments = BuildArguments(args);

            ProcessStartInfo startInfo = new ProcessStartInfo(command, arguments)
            {
                UseShellExecute = false,
                RedirectStandardInput = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };
            ApplyEnvironment(startInfo, environment);

            using (Process process = new Process
            {
                StartInfo = startInfo
            })
            {
                process.OutputDataReceived += (sender, eventArgs) =>
                {
                    if (eventArgs.Data != null)
                    {
                        AppendCrashLog("[python stdout] " + eventArgs.Data);
                    }
                };

                process.ErrorDataReceived += (sender, eventArgs) =>
                {
                    if (eventArgs.Data != null)
                    {
                        AppendCrashLog("[python stderr] " + eventArgs.Data);
                    }
                };

                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                AppendCrashLog("[python exit] ExitCode=" + process.ExitCode);
            }
        }

        public static void Launch(params string[] args)
        {
            Launch(null, args);
        }

        private static void SafeDeleteDirectory(string path)
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, true);
            }
        }

        private static string ComputeSha256(string filename)
        {
            using (var sha = SHA256.Create())
            using (var stream = File.OpenRead(filename))
            {
                var hash = sha.ComputeHash(stream);
                return BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();
            }
        }

        private static string GetExpectedSha256()
        {
            if (!string.IsNullOrWhiteSpace(PythonSha256))
            {
                return PythonSha256.ToLowerInvariant();
            }

            return null;
        }

        private static void ExtractZipSafe(string zipFile, string outputDir)
        {
            string root = Path.GetFullPath(outputDir);
            if (!root.EndsWith(Path.DirectorySeparatorChar.ToString()))
            {
                root += Path.DirectorySeparatorChar;
            }

            using (var archive = ZipFile.OpenRead(zipFile))
            {
                foreach (var entry in archive.Entries)
                {
                    if (string.IsNullOrEmpty(entry.FullName))
                    {
                        continue;
                    }

                    string destination = Path.GetFullPath(Path.Combine(root, entry.FullName));
                    if (!destination.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidOperationException("Archive contained an invalid path: " + entry.FullName);
                    }

                    if (entry.FullName.EndsWith("/", StringComparison.Ordinal) || entry.FullName.EndsWith("\\", StringComparison.Ordinal))
                    {
                        Directory.CreateDirectory(destination);
                        continue;
                    }

                    string parent = Path.GetDirectoryName(destination);
                    if (!Directory.Exists(parent))
                    {
                        Directory.CreateDirectory(parent);
                    }
                    entry.ExtractToFile(destination, true);
                }
            }
        }

        private static string ReadVersionFromOutput(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return string.Empty;
            }
            var parts = text.Trim().Split(' ');
            if (parts.Length < 2)
            {
                return string.Empty;
            }
            return parts[1].Trim();
        }

        private static Dictionary<string, string> BuildPythonChildEnv(string repoRoot, string venvDir, string pythonDir)
        {
            var env = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (DictionaryEntry de in Environment.GetEnvironmentVariables())
            {
                var key = de.Key as string;
                if (string.IsNullOrEmpty(key))
                {
                    continue;
                }

                env[key] = de.Value == null ? string.Empty : de.Value.ToString();
            }

            var toClear = env.Keys.Where(key =>
                    key.StartsWith("PYTHON", StringComparison.OrdinalIgnoreCase)
                    || key.StartsWith("PIP", StringComparison.OrdinalIgnoreCase)
                    || key.StartsWith("CONDA", StringComparison.OrdinalIgnoreCase)
                    || key.StartsWith("QT", StringComparison.OrdinalIgnoreCase)
                    || key.StartsWith("QML", StringComparison.OrdinalIgnoreCase)
                    || key.StartsWith("QSG", StringComparison.OrdinalIgnoreCase)
                    || key.StartsWith("SHIBOKEN", StringComparison.OrdinalIgnoreCase))
                .ToList();

            foreach (var key in toClear)
            {
                env.Remove(key);
            }

            env.Remove("VIRTUAL_ENV");

            var tmpDir = Path.Combine(repoRoot, ".tmp");
            Directory.CreateDirectory(tmpDir);
            var mlCacheDir = Path.Combine(tmpDir, "ml_cache");
            Directory.CreateDirectory(mlCacheDir);

            var hfHome = Path.Combine(mlCacheDir, "hf_home");
            var torchHome = Path.Combine(mlCacheDir, "torch_home");
            var transformersCache = Path.Combine(mlCacheDir, "transformers_cache");
            var diffusersCache = Path.Combine(mlCacheDir, "diffusers_cache");
            Directory.CreateDirectory(hfHome);
            Directory.CreateDirectory(torchHome);
            Directory.CreateDirectory(transformersCache);
            Directory.CreateDirectory(diffusersCache);

            var scriptsPath = Path.Combine(venvDir, "Scripts");
            var existingPath = env.ContainsKey("PATH") ? env["PATH"] : string.Empty;
            env["PATH"] = string.IsNullOrEmpty(existingPath) ? scriptsPath : scriptsPath + ";" + existingPath;

            env["VIRTUAL_ENV"] = venvDir;
            env["PYTHONNOUSERSITE"] = "1";
            env["PYTHONDONTWRITEBYTECODE"] = "1";
            env["PIP_NO_CACHE_DIR"] = "1";
            env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1";
            env["PIP_CONFIG_FILE"] = "NUL";
            env["QML_DISABLE_DISK_CACHE"] = "1";
            env["QT_DISABLE_SHADER_DISK_CACHE"] = "1";
            env["QSG_RHI_DISABLE_SHADER_DISK_CACHE"] = "1";
            env["TEMP"] = tmpDir;
            env["TMP"] = tmpDir;
            env["TMPDIR"] = tmpDir;
            env["HF_HOME"] = hfHome;
            env["TORCH_HOME"] = torchHome;
            env["TRANSFORMERS_CACHE"] = transformersCache;
            env["DIFFUSERS_CACHE"] = diffusersCache;

            return env;
        }

        private static bool VenvConfigOk(string exeDir)
        {
            var cfg = Path.Combine(exeDir, ".venv", "pyvenv.cfg");
            if (!File.Exists(cfg))
            {
                return false;
            }

            try
            {
                foreach (var rawLine in File.ReadAllLines(cfg))
                {
                    var line = rawLine.Trim();
                    if (!line.StartsWith("include-system-site-packages", StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }

                    var idx = line.IndexOf('=');
                    if (idx < 0)
                    {
                        return false;
                    }

                    var value = line.Substring(idx + 1).Trim();
                    return string.Equals(value, "false", StringComparison.OrdinalIgnoreCase);
                }
            }
            catch
            {
                return false;
            }

            return false;
        }

        private void EnsurePythonRuntime(string repoRoot, IDictionary<string, string> pythonEnv)
        {
            var pythonExe = Path.Combine(repoRoot, "python", "python.exe");
            var markerOk = File.Exists(PythonMarkerFile) && File.ReadAllText(PythonMarkerFile).Trim() == PythonVersion;
            var exeOk = File.Exists(pythonExe);
            var versionOk = false;
            if (exeOk)
            {
                try
                {
                    var output = Run(pythonEnv, pythonExe, "--version");
                    versionOk = ReadVersionFromOutput(output) == PythonVersion;
                }
                catch
                {
                    versionOk = false;
                }
            }

            if (markerOk && exeOk && versionOk)
            {
                return;
            }

            SafeDeleteDirectory("python");
            SafeDeleteDirectory(".venv");

            LaunchProgress();
            progress?.SetLabel("Downloading Python");
            progress?.SetProgress(0);

            if (!Download(PythonDownloadUrl, PythonArchive))
            {
                throw new Exception("Python download failed.");
            }

            var expectedHash = GetExpectedSha256();
            if (string.IsNullOrWhiteSpace(expectedHash))
            {
                throw new Exception("Python archive checksum is not configured.");
            }

            var actualHash = ComputeSha256(PythonArchive);
            if (!string.Equals(actualHash, expectedHash, StringComparison.OrdinalIgnoreCase))
            {
                throw new Exception("Python archive checksum mismatch.");
            }

            progress?.SetLabel("Installing Python");
            progress?.SetProgress(99);
            ExtractZipSafe(PythonArchive, "python");
            File.WriteAllText(PythonMarkerFile, PythonVersion + Environment.NewLine);
            File.Delete(PythonArchive);
        }

        private static bool VenvHomeMatchesBundledPython(string exeDir)
        {
            var cfg = Path.Combine(exeDir, ".venv", "pyvenv.cfg");
            if (!File.Exists(cfg))
            {
                return false;
            }

            var expected = Path.GetFullPath(Path.Combine(exeDir, "python")).TrimEnd('\\', '/');
            foreach (var line in File.ReadAllLines(cfg))
            {
                if (!line.StartsWith("home", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                var idx = line.IndexOf('=');
                if (idx < 0)
                {
                    continue;
                }

                var value = line.Substring(idx + 1).Trim().Trim('"').TrimEnd('\\', '/');
                var actual = Path.GetFullPath(value).TrimEnd('\\', '/');
                return string.Equals(actual, expected, StringComparison.OrdinalIgnoreCase);
            }

            return false;
        }

        private void EnsureVenv(string exeDir, string repoRoot, IDictionary<string, string> pythonEnv)
        {
            var venvPython = Path.Combine(repoRoot, ".venv", "Scripts", "python.exe");
            if (File.Exists(venvPython) && VenvHomeMatchesBundledPython(exeDir) && VenvConfigOk(exeDir))
            {
                return;
            }

            SafeDeleteDirectory(".venv");
            LaunchProgress();
            progress?.SetLabel("Creating Environment");
            progress?.SetProgress(99);
            Run(pythonEnv, Path.Combine(repoRoot, "python", "python.exe"), "-m", "venv", Path.Combine(repoRoot, ".venv"));

            if (!VenvConfigOk(exeDir))
            {
                throw new Exception("Invalid venv configuration: include-system-site-packages must be false.");
            }
        }

        private void EnsurePip(string repoRoot, IDictionary<string, string> pythonEnv)
        {
            var venvPython = Path.Combine(repoRoot, ".venv", "Scripts", "python.exe");
            bool pipOk;
            try
            {
                Run(pythonEnv, venvPython, "-I", "-m", "pip", "--version");
                pipOk = true;
            }
            catch
            {
                pipOk = false;
            }

            if (!pipOk)
            {
                Run(pythonEnv, venvPython, "-I", "-m", "ensurepip", "--upgrade");
                Run(pythonEnv, venvPython, "-I", "-m", "pip", "--version");
            }

            if (!File.Exists(PipMarkerFile))
            {
                LaunchProgress();
                progress?.SetLabel("Upgrading pip tooling");
                progress?.SetProgress(0);
                Run(pythonEnv, venvPython, "-I", "-m", "pip", "install", "-U", "pip", "setuptools", "wheel", "--no-cache-dir");
                File.WriteAllText(PipMarkerFile, DateTime.UtcNow.ToString("o") + Environment.NewLine);
            }
        }

        private bool VerifyPySideImport(string python, IDictionary<string, string> pythonEnv)
        {
            try
            {
                Run(pythonEnv, python, "-I", "-c", "import PySide6, shiboken6; from PySide6 import QtQml");
                return true;
            }
            catch
            {
                return false;
            }
        }

        private void EnsurePySideAndWrappers(string repoRoot, IDictionary<string, string> pythonEnv)
        {
            var venvPython = Path.Combine(repoRoot, ".venv", "Scripts", "python.exe");
            var rcc = Path.Combine(repoRoot, ".venv", "Scripts", "pyside6-rcc.exe");

            bool needsInstall = !File.Exists(PySideMarkerFile) || !VerifyPySideImport(venvPython, pythonEnv);
            if (!needsInstall && !File.Exists(rcc))
            {
                needsInstall = true;
            }

            if (needsInstall)
            {
                LaunchProgress();
                progress?.SetLabel("Installing PySide6");
                progress?.SetProgress(0);
                Run(
                    pythonEnv,
                    venvPython,
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--no-cache-dir",
                    "--index-url",
                    PythonPackageIndex,
                    "PySide6==" + RequiredPySideVersion);

                if (!VerifyPySideImport(venvPython, pythonEnv))
                {
                    throw new Exception("PySide6 import verification failed after installation.");
                }

                if (!File.Exists(rcc))
                {
                    throw new Exception("Missing required wrapper: .venv\\Scripts\\pyside6-rcc.exe");
                }

                File.WriteAllText(PySideMarkerFile, DateTime.UtcNow.ToString("o") + Environment.NewLine);
            }
            else if (!File.Exists(rcc))
            {
                throw new Exception("Missing required wrapper: .venv\\Scripts\\pyside6-rcc.exe");
            }
        }

        public void Work(string[] args)
        {
            var exe = Assembly.GetEntryAssembly().Location;
            var exe_dir = Path.GetDirectoryName(exe);
            Directory.SetCurrentDirectory(exe_dir);

            var app_user_model_id = "arenasys.qdiffusion." + MD5(exe);
            SetCurrentProcessExplicitAppUserModelID(app_user_model_id);

            if (args.Length >= 2 && args[0] == "-e")
            {
                LaunchError(args[1]);
                return;
            }

            if (!Directory.Exists("source"))
            {
                LaunchError("Missing sources. Please extract the ZIP archive.");
                return;
            }

            try
            {
                var repoRoot = Path.GetFullPath(exe_dir);
                var venvDir = Path.Combine(repoRoot, ".venv");
                var pythonDir = Path.Combine(repoRoot, "python");
                var pythonEnv = BuildPythonChildEnv(repoRoot, venvDir, pythonDir);

                EnsurePythonRuntime(repoRoot, pythonEnv);
                EnsureVenv(exe_dir, repoRoot, pythonEnv);
                pythonEnv = BuildPythonChildEnv(repoRoot, venvDir, pythonDir);
                EnsurePip(repoRoot, pythonEnv);
                EnsurePySideAndWrappers(repoRoot, pythonEnv);
            }
            catch (Exception ex)
            {
                progress?.DoClose();
                LaunchError(ex.Message);
                return;
            }

            RegisterProtocol(exe);

            Environment.SetEnvironmentVariable("HSA_OVERRIDE_GFX_VERSION", "10.3.0");
            Environment.SetEnvironmentVariable("MIOPEN_LOG_LEVEL", "4");

            progress?.DoClose();
            try
            {
                var repoRoot = Path.GetFullPath(exe_dir);
                var venvDir = Path.Combine(repoRoot, ".venv");
                var pythonDir = Path.Combine(repoRoot, "python");
                var pythonEnv = BuildPythonChildEnv(repoRoot, venvDir, pythonDir);

                string pythonw = Path.Combine(venvDir, "Scripts", "pythonw.exe");
                string python = File.Exists(pythonw) ? pythonw : Path.Combine(venvDir, "Scripts", "python.exe");
                string[] cmd = { python, "-E", "-s", "-B", Path.Combine(repoRoot, "source", "launch.py") };
                Launch(pythonEnv, cmd.Concat(args).ToArray());
            }
            catch (Exception ex)
            {
                LaunchError(ex.Message);
                return;
            }
        }
    }
    internal static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Worker worker = new Worker();
                worker.Work(args);
            }
            catch (Exception ex)
            {
                Worker.AppendCrashLog("[launcher exception] " + ex);
            }
        }
    }
}
