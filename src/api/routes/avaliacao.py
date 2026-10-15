from fastapi import APIRouter, HTTPException
import subprocess
import sys
from pathlib import Path

router = APIRouter()
TRAINING_DIR = Path(__file__).parent.parent.parent / "training"

@router.post("/avaliar")
async def avaliar_modelo(baseline_regras: bool = False):
    """
    Executa o script de avaliação do modelo.
    """
    try:
        cmd = [sys.executable, str(TRAINING_DIR / "avaliar.py")]
        if baseline_regras:
            cmd.append("--baseline-regras")
            cmd.append("coletor")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(TRAINING_DIR),
            timeout=300
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Erro na avaliação: {result.stderr}")
        
        return {
            "status": "sucesso",
            "output": result.stdout
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
