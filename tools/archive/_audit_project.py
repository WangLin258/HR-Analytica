import ast, sys, os, importlib
sys.stdout.reconfigure(encoding="utf-8")
BASE=r"C:\Users\ASUS\Desktop\work\project-001-人力与财务数据分析报告助手"
sys.path.insert(0, BASE)

print("=== 1. Python syntax ===")
py_files=[]
for root, dirs, files in os.walk(BASE):
    if ".venv" in root or "__pycache__" in root or ".pytest_cache" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.join(root, f))
for p in sorted(py_files):
    try:
        ast.parse(open(p, encoding="utf-8").read())
    except SyntaxError as e:
        print("SYNTAX ERROR", p, e.lineno, e.msg)
print(f"Syntax OK for {len(py_files)} python files")

print("\n=== 2. Module imports ===")
for mod in ["config", "analysis_engine", "ui_components", "api"]:
    try:
        importlib.import_module(mod)
        print("OK", mod)
    except Exception as e:
        print("IMPORT ERROR", mod, type(e).__name__, e)

print("\n=== 3. Temp scripts in root ===")
temps=[f for f in os.listdir(BASE) if f.startswith("_") and f.endswith(".py")]
print("Temp scripts:", temps if temps else "none")

print("\n=== 4. DB path ===")
import config
print("DB_PATH:", config.DB_PATH, "exists:", os.path.exists(config.DB_PATH))
import analysis_engine as ae
try:
    ae.init_db()
    print("init_db OK")
except Exception as e:
    print("init_db ERROR", e)

print("\n=== 5. Potential runtime checks ===")
checks = {
    "freq=ME present": 'freq="ME"' in open(os.path.join(BASE,"analysis_engine.py"),encoding="utf-8").read(),
    "st.rerun count": open(os.path.join(BASE,"ui_components.py"),encoding="utf-8").read().count("st.rerun"),
    "kaleido installed": importlib.util.find_spec("kaleido") is not None,
}
for k,v in checks.items():
    print(k, "->", v)

print("\n=== 6. Test files ===")
tests_dir=os.path.join(BASE,"tests")
print([f for f in os.listdir(tests_dir) if f.endswith(".py")])

sys.stdout.flush()
