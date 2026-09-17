from pathlib import Path
import shutil
import subprocess
import sys
import traceback

OLD_FOUNDER = 'def _founder_for_company(db: Session, company_id: int):\n    _sync_founders(db)\n    row = db.execute(\n        text(\n            "SELECT company_id, slot, assigned_at "\n            "FROM founder_program WHERE company_id=:company_id"\n        ),\n        {"company_id": company_id},\n    ).mappings().first()\n    return dict(row) if row else None\n'
NEW_FOUNDER = 'def _founder_for_company(db: Session, company_id: int):\n    for row in _sync_founders(db):\n        if int(row["company_id"]) == int(company_id):\n            return dict(row)\n    return None\n'
OLD_ROW = '    if row:\n        return dict(row)\n\n    status = "waived" if founder else "pending"\n'
NEW_ROW = '    if row:\n        current = dict(row)\n        if founder and str(current.get("status") or "") != "paid":\n            db.execute(\n                text(\n                    "UPDATE setup_fee_ledger SET amount=0,status=\'waived\' "\n                    "WHERE company_id=:company_id"\n                ),\n                {"company_id": company_id},\n            )\n            db.commit()\n            current["amount"] = 0.0\n            current["status"] = "waived"\n        return current\n\n    status = "waived" if founder else "pending"\n'

class PatchError(RuntimeError):
    pass

def find_project():
    here = Path.cwd()
    candidates = [here / "CDM_Desmontes_ERP_SaaS_Online_V4", here]
    for base in candidates:
        if (base / "backend/app/routers/platform_v14.py").exists():
            return base
    raise PatchError("Projeto não encontrado. Rode este arquivo dentro de C:\\CDM_DEPLOY.")

def run(cmd, cwd=None):
    print(">", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def main():
    base = find_project()
    router = base / "backend/app/routers/platform_v14.py"
    original = router.read_text(encoding="utf-8")

    try:
        text = original

        if OLD_FOUNDER not in text:
            raise PatchError("Não encontrei a função _founder_for_company esperada.")
        text = text.replace(OLD_FOUNDER, NEW_FOUNDER, 1)

        if OLD_ROW not in text:
            raise PatchError("Não encontrei o bloco de taxa de implantação esperado.")
        text = text.replace(OLD_ROW, NEW_ROW, 1)

        text = text.replace('"version": "14.1"', '"version": "14.2"', 1)
        router.write_text(text, encoding="utf-8")

        backup = base / "_backup_v14_1"
        if backup.exists():
            shutil.rmtree(backup)

        root = base.parent
        for name in ["CORRIGIR_CDM_V14_1.py", "APLICAR_CDM_V14.py"]:
            p = root / name
            if p.exists():
                p.unlink()

        print("\nValidando backend...")
        run([sys.executable, "-m", "py_compile", str(router)], cwd=base)

        git = shutil.which("git")
        if git:
            print("\nValidando diff...")
            run([git, "diff", "--check"], cwd=root)

        npm = shutil.which("npm")
        if npm and (base / "frontend/node_modules").exists():
            print("\nValidando frontend...")
            run([npm, "run", "build"], cwd=base / "frontend")

        print("\n==============================================")
        print("CDM V14.2 APLICADA E VALIDADA.")
        print("==============================================")
        print("Correção: fundadores agora valem também para cobrança/checkout.")
        print("Arquivos temporários da V14.1 também foram removidos.")
        print("\nAgora rode:")
        print("git add -A")
        print('git commit -m "V14.2 corrige cobranca dos fundadores"')
        print("git push")

    except Exception as exc:
        router.write_text(original, encoding="utf-8")
        print("\nERRO:", exc)
        print("O backend foi restaurado.")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
