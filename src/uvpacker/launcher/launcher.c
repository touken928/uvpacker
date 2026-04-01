#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif

#include <windows.h>

#include <stdint.h>
#include <stdio.h>

typedef struct Footer {
    char magic[8];
    uint32_t payloadSize;
    uint32_t reserved;
} Footer;

static const char MAGIC[8] = {'U', 'V', 'P', 'K', 'L', 'A', 'U', 'N'};

static int read_payload(const wchar_t *exePath, char **outBuf, uint32_t *outSize) {
    HANDLE hFile = CreateFileW(
        exePath,
        GENERIC_READ,
        FILE_SHARE_READ,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    if (hFile == INVALID_HANDLE_VALUE) {
        return 1;
    }

    LARGE_INTEGER fileSizeLi;
    if (!GetFileSizeEx(hFile, &fileSizeLi)) {
        CloseHandle(hFile);
        return 1;
    }

    if (fileSizeLi.QuadPart < (LONGLONG)sizeof(Footer)) {
        CloseHandle(hFile);
        return 1;
    }

    LARGE_INTEGER pos;
    pos.QuadPart = fileSizeLi.QuadPart - (LONGLONG)sizeof(Footer);
    if (!SetFilePointerEx(hFile, pos, NULL, FILE_BEGIN)) {
        CloseHandle(hFile);
        return 1;
    }

    Footer footer;
    DWORD bytesRead = 0;
    if (!ReadFile(hFile, &footer, (DWORD)sizeof(footer), &bytesRead, NULL) ||
        bytesRead != sizeof(footer)) {
        CloseHandle(hFile);
        return 1;
    }

    if (memcmp(footer.magic, MAGIC, 8) != 0) {
        CloseHandle(hFile);
        return 1;
    }

    if (footer.payloadSize == 0 ||
        footer.payloadSize > (uint32_t)(fileSizeLi.QuadPart - sizeof(Footer))) {
        CloseHandle(hFile);
        return 1;
    }

    pos.QuadPart = fileSizeLi.QuadPart - sizeof(Footer) - footer.payloadSize;
    if (!SetFilePointerEx(hFile, pos, NULL, FILE_BEGIN)) {
        CloseHandle(hFile);
        return 1;
    }

    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, footer.payloadSize + 1);
    if (!buf) {
        CloseHandle(hFile);
        return 1;
    }

    if (!ReadFile(hFile, buf, footer.payloadSize, &bytesRead, NULL) ||
        bytesRead != footer.payloadSize) {
        HeapFree(GetProcessHeap(), 0, buf);
        CloseHandle(hFile);
        return 1;
    }
    buf[footer.payloadSize] = '\0';

    CloseHandle(hFile);
    *outBuf = buf;
    *outSize = footer.payloadSize;
    return 0;
}

static int extract_field(const char *json, const char *key, char *out, size_t outSize) {
    // Minimal JSON extractor: looks for "key":"value"
    const char *p = strstr(json, key);
    if (!p) return 1;

    p = strchr(p, ':');
    if (!p) return 1;
    p++;
    while (*p == ' ' || *p == '\t') p++;
    if (*p != '\"') return 1;
    p++;

    size_t i = 0;
    while (*p && *p != '\"' && i + 1 < outSize) {
        out[i++] = *p++;
    }
    out[i] = '\0';
    if (*p != '\"') return 1;
    return 0;
}

static int run_python(const wchar_t *exePath, const char *payloadJson) {
    wchar_t runtimeDir[MAX_PATH];
    wchar_t pythonDll[MAX_PATH];

    wcsncpy(runtimeDir, exePath, MAX_PATH);
    runtimeDir[MAX_PATH - 1] = L'\0';
    wchar_t *lastSlash = wcsrchr(runtimeDir, L'\\');
    if (lastSlash) {
        *lastSlash = L'\0';
    }
    wcscat(runtimeDir, L"\\runtime");

    SetDllDirectoryW(runtimeDir);
    wcscpy(pythonDll, runtimeDir);
    wcscat(pythonDll, L"\\python3.dll");

    HMODULE hDLL = LoadLibraryW(pythonDll);
    if (!hDLL) {
        return 1;
    }

    int (*Py_Main)(int, wchar_t **) =
        (int (*)(int, wchar_t **))GetProcAddress(hDLL, "Py_Main");
    if (!Py_Main) {
        FreeLibrary(hDLL);
        return 1;
    }

    // Extract module and func from JSON payload.
    char module[256];
    char func[256];
    if (extract_field(payloadJson, "\"module\"", module, sizeof module) != 0) {
        FreeLibrary(hDLL);
        return 1;
    }
    if (extract_field(payloadJson, "\"func\"", func, sizeof func) != 0) {
        lstrcpyA(func, "main");
    }

    // Convert module and func to wide strings.
    wchar_t wModule[256];
    wchar_t wFunc[256];
    MultiByteToWideChar(CP_UTF8, 0, module, -1, wModule, (int)(sizeof wModule / sizeof(wchar_t)));
    MultiByteToWideChar(CP_UTF8, 0, func, -1, wFunc, (int)(sizeof wFunc / sizeof(wchar_t)));

    // Build init script.
    wchar_t initScript[1024];
    swprintf(
        initScript,
        sizeof(initScript) / sizeof(wchar_t),
        L"from %ls import %ls as _f; raise SystemExit(_f())",
        wModule,
        wFunc
    );

    int argc;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv) {
        FreeLibrary(hDLL);
        return 1;
    }

    int pyArgc = argc + 5;
    wchar_t **pyArgv = (wchar_t **)HeapAlloc(
        GetProcessHeap(),
        0,
        sizeof(wchar_t *) * pyArgc
    );
    if (!pyArgv) {
        LocalFree(argv);
        FreeLibrary(hDLL);
        return 1;
    }

    pyArgv[0] = argv[0];
    pyArgv[1] = L"-I";
    pyArgv[2] = L"-s";
    pyArgv[3] = L"-S";
    pyArgv[4] = L"-c";
    pyArgv[5] = initScript;
    for (int i = 1; i < argc; ++i) {
        pyArgv[5 + i] = argv[i];
    }

    int ret = Py_Main(pyArgc, pyArgv);

    HeapFree(GetProcessHeap(), 0, pyArgv);
    LocalFree(argv);
    FreeLibrary(hDLL);
    return ret;
}

int wmain() {
    wchar_t exePath[MAX_PATH];
    if (!GetModuleFileNameW(NULL, exePath, MAX_PATH)) {
        return 1;
    }

    char *payload = NULL;
    uint32_t payloadSize = 0;
    if (read_payload(exePath, &payload, &payloadSize) != 0) {
        return 1;
    }

    int ret = run_python(exePath, payload);
    HeapFree(GetProcessHeap(), 0, payload);
    return ret;
}

