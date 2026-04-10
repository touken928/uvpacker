#include <windows.h>

#include <stdio.h>
#include <string.h>

static const char INIT_SCRIPT[] =
    "import importlib.abc as _abc\n"
    "import importlib.machinery as _machinery\n"
    "import io as _io\n"
    "import json as _json\n"
    "import marshal as _marshal\n"
    "import posixpath as _pp\n"
    "import struct as _struct\n"
    "import sys as _sys\n"
    "import zipfile as _zipfile\n"
    "_MAGIC = b'UVPKLAUN'\n"
    "_FOOTER = _struct.Struct('<8sIII')\n"
    "with open(_SELF, 'rb') as _fp:\n"
    "    _fp.seek(-_FOOTER.size, 2)\n"
    "    _magic, _meta_size, _archive_size, _version = _FOOTER.unpack(_fp.read(_FOOTER.size))\n"
    "    if _magic != _MAGIC or _version != 1:\n"
    "        raise RuntimeError('invalid launcher payload footer')\n"
    "    _fp.seek(-(_FOOTER.size + _meta_size + _archive_size), 2)\n"
    "    _archive_bytes = _fp.read(_archive_size)\n"
    "    _config = _json.loads(_fp.read(_meta_size).decode('utf-8'))\n"
    "_ENTRY_MODULE = _config['module']\n"
    "_ENTRY_FUNC = _config.get('func', 'main')\n"
    "class _MemZip:\n"
    "    def __init__(self, data):\n"
    "        self._zip = _zipfile.ZipFile(_io.BytesIO(data))\n"
    "        self._files = {name for name in self._zip.namelist() if not name.endswith('/')}\n"
    "        self._dirs = {''}\n"
    "        for _name in self._files:\n"
    "            _parts = _name.split('/')\n"
    "            for _i in range(1, len(_parts)):\n"
    "                self._dirs.add('/'.join(_parts[:_i]))\n"
    "    def module_info(self, fullname):\n"
    "        base = fullname.replace('.', '/')\n"
    "        for suffix, is_pkg, fmt in (('/__init__.pyc', True, 'pyc'), ('/__init__.py', True, 'py'), ('.pyc', False, 'pyc'), ('.py', False, 'py')):\n"
    "            member = base + suffix\n"
    "            if member in self._files:\n"
    "                return member, is_pkg, fmt\n"
    "        return None\n"
    "    def is_dir(self, path):\n"
    "        return path.strip('/') in self._dirs\n"
    "    def is_file(self, path):\n"
    "        return path.strip('/') in self._files\n"
    "    def read(self, path):\n"
    "        return self._zip.read(path.strip('/'))\n"
    "    def children(self, path):\n"
    "        prefix = path.strip('/')\n"
    "        prefix = prefix + '/' if prefix else ''\n"
    "        names = set()\n"
    "        for name in self._files:\n"
    "            if not name.startswith(prefix) or name == prefix:\n"
    "                continue\n"
    "            tail = name[len(prefix):]\n"
    "            if tail:\n"
    "                names.add(tail.split('/', 1)[0])\n"
    "        for name in self._dirs:\n"
    "            if not name:\n"
    "                continue\n"
    "            entry = name + '/'\n"
    "            if not entry.startswith(prefix) or entry == prefix:\n"
    "                continue\n"
    "            tail = entry[len(prefix):].strip('/')\n"
    "            if tail:\n"
    "                names.add(tail.split('/', 1)[0])\n"
    "        return sorted(names)\n"
    "_ARCHIVE = _MemZip(_archive_bytes)\n"
    "class _MemTraversable:\n"
    "    def __init__(self, archive, path):\n"
    "        self._archive = archive\n"
    "        self._path = path.strip('/')\n"
    "    @property\n"
    "    def name(self):\n"
    "        return '' if not self._path else self._path.rsplit('/', 1)[-1]\n"
    "    def iterdir(self):\n"
    "        if not self.is_dir():\n"
    "            return iter(())\n"
    "        return iter(_MemTraversable(self._archive, _pp.join(self._path, child) if self._path else child) for child in self._archive.children(self._path))\n"
    "    def is_dir(self):\n"
    "        return self._archive.is_dir(self._path)\n"
    "    def is_file(self):\n"
    "        return self._archive.is_file(self._path)\n"
    "    def joinpath(self, child):\n"
    "        return _MemTraversable(self._archive, _pp.join(self._path, child) if self._path else child)\n"
    "    def open(self, mode='r', *args, **kwargs):\n"
    "        if not self.is_file():\n"
    "            raise FileNotFoundError(self._path)\n"
    "        data = self._archive.read(self._path)\n"
    "        if 'b' in mode:\n"
    "            return _io.BytesIO(data)\n"
    "        encoding = kwargs.get('encoding') or 'utf-8'\n"
    "        errors = kwargs.get('errors') or 'strict'\n"
    "        return _io.TextIOWrapper(_io.BytesIO(data), encoding=encoding, errors=errors)\n"
    "    def read_bytes(self):\n"
    "        return self._archive.read(self._path)\n"
    "    def read_text(self, encoding='utf-8', errors='strict'):\n"
    "        return self.read_bytes().decode(encoding, errors)\n"
    "class _MemLoader(_abc.Loader):\n"
    "    def __init__(self, archive, fullname, member, is_pkg, fmt):\n"
    "        self._archive = archive\n"
    "        self._fullname = fullname\n"
    "        self._member = member\n"
    "        self._is_pkg = is_pkg\n"
    "        self._fmt = fmt\n"
    "    def create_module(self, spec):\n"
    "        return None\n"
    "    def exec_module(self, module):\n"
    "        data = self._archive.read(self._member)\n"
    "        if self._fmt == 'pyc':\n"
    "            code = _marshal.loads(data[16:])\n"
    "        else:\n"
    "            code = compile(data.decode('utf-8'), module.__spec__.origin, 'exec')\n"
    "        module.__file__ = module.__spec__.origin\n"
    "        module.__loader__ = self\n"
    "        module.__package__ = self._fullname if self._is_pkg else self._fullname.rpartition('.')[0]\n"
    "        if self._is_pkg:\n"
    "            module.__path__ = [module.__spec__.origin]\n"
    "        exec(code, module.__dict__)\n"
    "    def get_resource_reader(self, fullname):\n"
    "        return self if fullname == self._fullname and self._is_pkg else None\n"
    "    def files(self):\n"
    "        return _MemTraversable(self._archive, self._fullname.replace('.', '/'))\n"
    "    def open_resource(self, resource):\n"
    "        return self.files().joinpath(resource).open('rb')\n"
    "    def resource_path(self, resource):\n"
    "        raise FileNotFoundError(resource)\n"
    "    def is_resource(self, name):\n"
    "        return self.files().joinpath(name).is_file()\n"
    "    def contents(self):\n"
    "        return [child.name for child in self.files().iterdir()]\n"
    "class _MemFinder(_abc.MetaPathFinder):\n"
    "    def find_spec(self, fullname, path=None, target=None):\n"
    "        info = _ARCHIVE.module_info(fullname)\n"
    "        if info is None:\n"
    "            return None\n"
    "        member, is_pkg, fmt = info\n"
    "        loader = _MemLoader(_ARCHIVE, fullname, member, is_pkg, fmt)\n"
    "        spec = _machinery.ModuleSpec(fullname, loader, origin='mem://' + member, is_package=is_pkg)\n"
    "        if is_pkg:\n"
    "            spec.submodule_search_locations = ['mem://' + fullname.replace('.', '/')]\n"
    "        return spec\n"
    "_sys.meta_path.insert(0, _MemFinder())\n"
    "_mod = __import__(_ENTRY_MODULE, fromlist=[_ENTRY_FUNC])\n"
    "raise SystemExit(getattr(_mod, _ENTRY_FUNC)())\n";

static wchar_t *utf8_to_wide(const char *text) {
    int needed = MultiByteToWideChar(CP_UTF8, 0, text, -1, NULL, 0);
    if (needed <= 0) {
        return NULL;
    }
    wchar_t *out = (wchar_t *)HeapAlloc(GetProcessHeap(), 0, sizeof(wchar_t) * (size_t)needed);
    if (!out) {
        return NULL;
    }
    if (!MultiByteToWideChar(CP_UTF8, 0, text, -1, out, needed)) {
        HeapFree(GetProcessHeap(), 0, out);
        return NULL;
    }
    return out;
}

static size_t append_wide_text(wchar_t *dest, size_t capacity, size_t pos, const wchar_t *text) {
    while (*text != L'\0' && pos + 1 < capacity) {
        dest[pos++] = *text++;
    }
    return pos;
}

static size_t append_python_escaped_wchar(wchar_t *dest, size_t capacity, size_t pos, wchar_t ch) {
    if (pos + 1 >= capacity) {
        return pos;
    }

    if (ch == L'\\' || ch == L'\'') {
        if (pos + 2 >= capacity) {
            return pos;
        }
        dest[pos++] = L'\\';
        dest[pos++] = ch;
        return pos;
    }
    if (ch == L'\n') {
        if (pos + 2 >= capacity) {
            return pos;
        }
        dest[pos++] = L'\\';
        dest[pos++] = L'n';
        return pos;
    }
    if (ch == L'\r') {
        if (pos + 2 >= capacity) {
            return pos;
        }
        dest[pos++] = L'\\';
        dest[pos++] = L'r';
        return pos;
    }
    if (ch == L'\t') {
        if (pos + 2 >= capacity) {
            return pos;
        }
        dest[pos++] = L'\\';
        dest[pos++] = L't';
        return pos;
    }
    if (ch >= 0x20 && ch <= 0x7E) {
        dest[pos++] = ch;
        return pos;
    }

    if ((unsigned int)ch <= 0xFFFF) {
        if (pos + 6 >= capacity) {
            return pos;
        }
        swprintf(dest + pos, capacity - pos, L"\\u%04X", (unsigned int)ch);
        return pos + 6;
    }

    if (pos + 10 >= capacity) {
        return pos;
    }
    swprintf(dest + pos, capacity - pos, L"\\U%08X", (unsigned int)ch);
    return pos + 10;
}

static wchar_t *build_init_script(const wchar_t *exePath) {
    size_t exeLen = wcslen(exePath);
    size_t baseLen = strlen(INIT_SCRIPT);
    size_t capacity = (baseLen * 2) + (exeLen * 12) + 64;
    wchar_t *script = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(wchar_t) * capacity);
    if (!script) {
        return NULL;
    }

    size_t pos = 0;
    pos = append_wide_text(script, capacity, pos, L"_SELF = '");
    for (size_t i = 0; i < exeLen && pos + 1 < capacity; ++i) {
        pos = append_python_escaped_wchar(script, capacity, pos, exePath[i]);
    }
    pos = append_wide_text(script, capacity, pos, L"'\n");

    wchar_t *rest = utf8_to_wide(INIT_SCRIPT);
    if (!rest) {
        HeapFree(GetProcessHeap(), 0, script);
        return NULL;
    }
    pos = append_wide_text(script, capacity, pos, rest);
    script[pos] = L'\0';
    HeapFree(GetProcessHeap(), 0, rest);
    return script;
}

static int run_python(const wchar_t *exePath) {
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

    wchar_t *initScript = build_init_script(exePath);
    if (!initScript) {
        FreeLibrary(hDLL);
        return 1;
    }

    int argc;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv) {
        HeapFree(GetProcessHeap(), 0, initScript);
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
        HeapFree(GetProcessHeap(), 0, initScript);
        FreeLibrary(hDLL);
        return 1;
    }

    pyArgv[0] = (wchar_t *)exePath;
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
    HeapFree(GetProcessHeap(), 0, initScript);
    FreeLibrary(hDLL);
    return ret;
}

static int run_launcher(void) {
    wchar_t exePath[MAX_PATH];
    if (!GetModuleFileNameW(NULL, exePath, MAX_PATH)) {
        return 1;
    }

    return run_python(exePath);
}

#ifdef UVPK_GUI
int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR lpCmdLine, int nCmdShow) {
    (void)hInstance;
    (void)hPrevInstance;
    (void)lpCmdLine;
    (void)nCmdShow;
    return run_launcher();
}
#else
int wmain(int argc, wchar_t **argv) {
    (void)argc;
    (void)argv;
    return run_launcher();
}
#endif
