from fastapi import APIRouter, HTTPException
import subprocess
import sys
from pathlib import Path

router = APIRouter()
TRAINING_DIR = Path(__file__).parent.parent.parent / "training"

@router.post("/rotular")
async def rotular_com_gemini():
    """
    Executa o script de pré-rotulação com Gemini.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(TRAINING_DIR / "rotular_gemini.py")],
            capture_output=True,
            text=True,
            cwd=str(TRAINING_DIR),
            timeout=600
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Erro na rotulação: {result.stderr}")
        
        return {
            "status": "sucesso",
            "output": result.stdout
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
