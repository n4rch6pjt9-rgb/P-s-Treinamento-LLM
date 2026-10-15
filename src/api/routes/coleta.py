from fastapi import APIRouter, HTTPException, BackgroundTasks
import subprocess
import sys
import os
from pathlib import Path

router = APIRouter()
# Ajuste de caminho: src/api/routes -> src/api -> src -> P-s-Treinamento-LLM -> training
TRAINING_DIR = Path(__file__).resolve().parents[3] / "training"

def _rodar_rotulagem_em_background():
    """Função pesada que roda em segundo plano sem travar a resposta HTTP."""
    cmd = [
        sys.executable, 
        str(TRAINING_DIR / "rotular_gemini.py"),
        "--modelo", "gemini-3.8-flash"  # Força o modelo correto que descobrimos
    ]
    
    # Roda o script. O output (logs de progresso) aparecerá no terminal do Uvicorn.
    subprocess.run(cmd, cwd=str(TRAINING_DIR))

@router.post("/rotular")
async def rotular_com_gemini(background_tasks: BackgroundTasks):
    """
    Dispara o script de pré-rotulação com Gemini em segundo plano.
    Retorna imediatamente para não dar timeout na requisição HTTP.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        raise HTTPException(
            status_code=500, 
            detail="A variável GOOGLE_API_KEY não está exportada no terminal do Uvicorn."
        )

    # Adiciona a tarefa pesada para rodar em background
    background_tasks.add_task(_rodar_rotulagem_em_background)
    
    return {
        "status": "disparado_com_sucesso",
        "mensagem": "A rotulagem de 73k itens foi iniciada em segundo plano. Acompanhe o progresso no terminal do Uvicorn."
    }

@router.get("/coletar/status")
async def status_coleta():
    """
    Verifica se o arquivo candidatos.jsonl existe e quantos itens tem.
    """
    candidatos_file = TRAINING_DIR / "data" / "candidatos.jsonl"
    
    if not candidatos_file.exists():
        return {"status": "arquivo_nao_encontrado", "itens": 0}
    
    with open(candidatos_file, 'r', encoding='utf-8') as f:
        itens = sum(1 for _ in f)
    
    return {"status": "ok", "itens": itens, "arquivo": str(candidatos_file)}
