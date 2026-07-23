from __future__ import annotations
import csv, hashlib, io, secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from models import ImportAudit, Instrument, Position, PositionLot, StopRule
from services.position_domain import create_position, activate_rule

SCHEMA = ("schema_version", "code", "name", "asset_type", "quantity", "unit_cost", "stop_method", "stop_value")
FORMULA = ("=", "+", "-", "@")
_previews = {}

def _safe(value): return "'" + value if isinstance(value, str) and value.startswith(FORMULA) else value

def preview_csv(content: bytes, *, max_bytes=1048576, max_rows=1000):
    if len(content) > max_bytes: raise ValueError("import_too_large")
    try: rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except UnicodeDecodeError as exc: raise ValueError("import_encoding_invalid") from exc
    if len(rows) > max_rows: raise ValueError("import_too_many_rows")
    results=[]
    for n,row in enumerate(rows,2):
        errors=[]
        if tuple(row) != SCHEMA: errors.append("csv_schema_invalid")
        try:
            if row.get("schema_version") != "1": raise ValueError
            if row.get("asset_type") not in {"stock","fund"}: raise ValueError
            if Decimal(row.get("quantity", "0")) <= 0 or Decimal(row.get("unit_cost", "0")) <= 0: raise ValueError
        except Exception: errors.append("csv_value_invalid")
        results.append({"row":n,"data":row,"errors":errors})
    token=secrets.token_urlsafe(24); digest=hashlib.sha256(content).hexdigest()
    _previews[token]={"digest":digest,"rows":results,"expires":datetime.now(timezone.utc)+timedelta(minutes=10)}
    return {"token":token,"sha256":digest,"rows":results,"valid":sum(not r["errors"] for r in results)}

def commit_preview(db: Session, token: str):
    item=_previews.pop(token,None)
    if not item or item["expires"] < datetime.now(timezone.utc): raise ValueError("preview_token_expired")
    if any(r["errors"] for r in item["rows"]): raise ValueError("preview_has_invalid_rows")
    audit=ImportAudit(token_hash=hashlib.sha256(token.encode()).hexdigest(),source_sha256=item["digest"],status="committed",row_count=len(item["rows"]),valid_count=len(item["rows"]),committed_at=datetime.now(timezone.utc)); db.add(audit)
    created=[]
    for result in item["rows"]:
        row=result["data"]; position=create_position(db,code=row["code"],asset_type=row["asset_type"],name=row["name"],quantity=row["quantity"],unit_cost=row["unit_cost"]); activate_rule(db,position,method=row["stop_method"],value=row["stop_value"],reason="csv_import"); created.append(position)
    db.commit(); return created

def export_positions(db: Session) -> str:
    out=io.StringIO(); writer=csv.DictWriter(out,fieldnames=SCHEMA); writer.writeheader()
    for position in db.query(Position).all():
        instrument=db.get(Instrument,position.instrument_id); lot=db.query(PositionLot).filter(PositionLot.position_id==position.id).first(); rule=db.query(StopRule).filter(StopRule.position_id==position.id,StopRule.is_active.is_(True)).first()
        writer.writerow({"schema_version":"1","code":instrument.code,"name":_safe(instrument.name),"asset_type":instrument.asset_type,"quantity":str(position.remaining_quantity),"unit_cost":str(lot.unit_cost),"stop_method":rule.method if rule else "fixed","stop_value":str(rule.value) if rule else "0"})
    return out.getvalue()
