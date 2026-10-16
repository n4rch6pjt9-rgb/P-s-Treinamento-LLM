from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import coleta, rotulacao, treino, avaliacao, curadoria, curadoria_chat

app = FastAPI(
    title="LicitaGym Training Pipeline API",
    description="API para orquestrar o pipeline de treinamento do classificador de licitações",
    version="1.0.0"
)

# CORS para permitir chamadas do React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rotas
app.include_router(coleta.router, prefix="/api", tags=["Coleta"])
app.include_router(rotulacao.router, prefix="/api", tags=["Rotulação"])
app.include_router(treino.router, prefix="/api", tags=["Treinamento"])
app.include_router(avaliacao.router, prefix="/api", tags=["Avaliação"])
app.include_router(curadoria.router)        # endpoints /api/curadoria/*
app.include_router(curadoria.pagina_router) # página /curadoria
app.include_router(curadoria_chat.router)   # /api/curadoria-chat/* (chat e decisões dos portais)

@app.get("/")
async def root():
    return {"message": "LicitaGym Training Pipeline API está rodando!"}
