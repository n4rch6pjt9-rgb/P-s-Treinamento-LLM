from fastapi import APIRouter, HTTPException
import subprocess
import sys
from pathlib import Path

router = APIRouter()
TRAINING_DIR = Path(__file__).parent.parent.parent / "training"

@router.post("/treinar")
async def treinar_modelo():
    """
    Executa o notebook de treinamento (sft_tunix.ipynb).
    """
    try:
        notebook_path = TRAINING_DIR / "sft_tunix.ipynb"
        
        if not notebook_path.exists():
            raise HTTPException(status_code=404, detail="Notebook de treinamento não encontrado")
        
        result_convert = subprocess.run(
            ["jupyter", "nbconvert", "--to", "script", str(notebook_path)],
            capture_output=True,
            text=True,
            cwd=str(TRAINING_DIR)
        )
        
        if result_convert.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Erro ao converter notebook: {result_convert.stderr}")
        
        script_path = TRAINING_DIR / "sft_tunix.py"
        result_run = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            cwd=str(TRAINING_DIR),
            timeout=3600
        )
        
        if result_run.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Erro no treinamento: {result_run.stderr}")
        
        return {
            "status": "sucesso",
            "output": result_run.stdout
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
