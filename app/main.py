"""API REST de gestion des stages - FastAPI + SQLite."""
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

DB_PATH = os.getenv("DB_PATH", "stages.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_etudiant TEXT NOT NULL,
                entreprise TEXT NOT NULL,
                intitule TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT NOT NULL
            )
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="API Gestion des Stages",
    description="API REST permettant de gérer les stages des étudiants d'une école d'ingénieurs.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------- Schémas ----------
class StageBase(BaseModel):
    nom_etudiant: str = Field(..., min_length=1, examples=["Alice Martin"])
    entreprise: str = Field(..., min_length=1, examples=["Airbus"])
    intitule: str = Field(..., min_length=1, examples=["Développeur Backend"])
    date_debut: date = Field(..., examples=["2026-02-01"])
    date_fin: date = Field(..., examples=["2026-07-31"])

    @model_validator(mode="after")
    def check_dates(self):
        if self.date_fin < self.date_debut:
            raise ValueError("date_fin doit être postérieure ou égale à date_debut")
        return self


class StageCreate(StageBase):
    pass


class StageUpdate(BaseModel):
    """Mise à jour partielle : tous les champs sont optionnels."""
    nom_etudiant: Optional[str] = Field(None, min_length=1)
    entreprise: Optional[str] = Field(None, min_length=1)
    intitule: Optional[str] = Field(None, min_length=1)
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None


class Stage(StageBase):
    id: int


def row_to_stage(row: sqlite3.Row) -> Stage:
    return Stage(**dict(row))


def fetch_stage(conn: sqlite3.Connection, stage_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM stages WHERE id = ?", (stage_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Stage {stage_id} introuvable")
    return row


# ---------- Endpoints ----------
@app.get("/", tags=["Santé"])
def root():
    return {"message": "API Gestion des Stages", "docs": "/docs"}


@app.get("/health", tags=["Santé"])
def health():
    return {"status": "ok"}


@app.get("/stages", response_model=list[Stage], tags=["Stages"])
def list_stages(entreprise: Optional[str] = None):
    """Liste tous les stages (filtre optionnel par entreprise)."""
    with get_conn() as conn:
        if entreprise:
            rows = conn.execute(
                "SELECT * FROM stages WHERE entreprise LIKE ? ORDER BY id", (f"%{entreprise}%",)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM stages ORDER BY id").fetchall()
    return [row_to_stage(r) for r in rows]


@app.get("/stages/{stage_id}", response_model=Stage, tags=["Stages"])
def get_stage(stage_id: int):
    with get_conn() as conn:
        return row_to_stage(fetch_stage(conn, stage_id))


@app.post("/stages", response_model=Stage, status_code=status.HTTP_201_CREATED, tags=["Stages"])
def create_stage(stage: StageCreate):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO stages (nom_etudiant, entreprise, intitule, date_debut, date_fin) "
            "VALUES (?, ?, ?, ?, ?)",
            (stage.nom_etudiant, stage.entreprise, stage.intitule,
             stage.date_debut.isoformat(), stage.date_fin.isoformat()),
        )
        return Stage(id=cur.lastrowid, **stage.model_dump())


@app.put("/stages/{stage_id}", response_model=Stage, tags=["Stages"])
def update_stage(stage_id: int, update: StageUpdate):
    with get_conn() as conn:
        current = dict(fetch_stage(conn, stage_id))
        current.update(update.model_dump(exclude_unset=True, exclude_none=True))
        # Revalidation complète (notamment la cohérence des dates)
        try:
            merged = Stage(**current)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        conn.execute(
            "UPDATE stages SET nom_etudiant=?, entreprise=?, intitule=?, date_debut=?, date_fin=? "
            "WHERE id=?",
            (merged.nom_etudiant, merged.entreprise, merged.intitule,
             merged.date_debut.isoformat(), merged.date_fin.isoformat(), stage_id),
        )
        return merged


@app.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Stages"])
def delete_stage(stage_id: int):
    with get_conn() as conn:
        fetch_stage(conn, stage_id)
        conn.execute("DELETE FROM stages WHERE id = ?", (stage_id,))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
