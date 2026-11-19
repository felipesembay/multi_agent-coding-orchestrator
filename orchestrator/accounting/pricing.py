"""Append-only manual/import price versions; estimates never represent billing."""
from datetime import datetime,timezone
from decimal import Decimal
import math
from typing import Annotated,Literal
import uuid

from pydantic import AwareDatetime,BaseModel,Field,TypeAdapter,model_validator

from ..project_store import connection


class PricingError(ValueError):
    pass


Price=Annotated[float,Field(strict=True,ge=0,allow_inf_nan=False)]
PRICE_FIELDS=('input_price','output_price','cache_read_price','cache_write_price','reasoning_price')


def timestamp(value=None):
    try:
        parsed=TypeAdapter(AwareDatetime).validate_python(value if value is not None else datetime.now(timezone.utc))
        return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds')[:-6].replace('T',' ')
    except Exception:
        raise PricingError('Price timestamps must include a timezone') from None


class PriceInput(BaseModel):
    model_config={'extra':'forbid'}
    adapter:str=Field(pattern=r'^[a-z][a-z0-9_-]{0,63}$')
    model:str=Field(min_length=1,max_length=256,pattern=r'\S')
    unit:Literal['per_1m_tokens']='per_1m_tokens'
    currency:str=Field(default='USD',pattern=r'^[A-Z]{3}$')
    input_price:Price|None=None
    output_price:Price|None=None
    cache_read_price:Price|None=None
    cache_write_price:Price|None=None
    reasoning_price:Price|None=None
    effective_from:AwareDatetime
    effective_to:AwareDatetime|None=None

    @model_validator(mode='after')
    def valid_window(self):
        if self.effective_to is not None and self.effective_to<=self.effective_from:
            raise ValueError('Price validity end must be after its start')
        if not any(getattr(self,field) is not None for field in PRICE_FIELDS):
            raise ValueError('At least one component price must be provided')
        return self


class CatalogInput(BaseModel):
    model_config={'extra':'forbid'}
    source:Literal['manual','import']='manual'
    notes:str=Field(default='',max_length=2000)
    entries:list[PriceInput]=Field(min_length=1,max_length=1000)

    @model_validator(mode='after')
    def unique_quotes(self):
        keys=[(e.adapter,e.model,e.currency,timestamp(e.effective_from)) for e in self.entries]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate price validity starts in catalog')
        return self


def create_catalog(data):
    data=CatalogInput.model_validate(data.model_dump() if isinstance(data,CatalogInput) else data)
    key='prices-'+uuid.uuid4().hex
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT INTO price_catalog_versions(id,source,fetched_at,notes) VALUES(?,?,?,?)',
                     (key,data.source,timestamp(),data.notes))
        for entry in data.entries:
            start=timestamp(entry.effective_from)
            if conn.execute('''SELECT 1 FROM price_entries WHERE adapter=? AND model=? AND currency=?
                               AND effective_from=?''',(entry.adapter,entry.model,entry.currency,start)).fetchone():
                raise PricingError('A price already exists for this validity start; append a later version')
            conn.execute('''INSERT INTO price_entries(id,catalog_version_id,adapter,model,unit,currency,
                input_price,output_price,cache_read_price,cache_write_price,reasoning_price,effective_from,effective_to)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',('price-'+uuid.uuid4().hex,key,entry.adapter,entry.model,
                entry.unit,entry.currency,*(getattr(entry,name) for name in PRICE_FIELDS),start,
                timestamp(entry.effective_to) if entry.effective_to is not None else None))
        from ..projects import audit
        audit(conn,'pricing.catalog_created',catalog_version_id=key,source=data.source,entry_count=len(data.entries))
        conn.commit()
        return _catalog(conn,key)


def _catalog(conn,key):
    version=dict(conn.execute('SELECT * FROM price_catalog_versions WHERE id=?',(key,)).fetchone())
    version['entries']=[dict(row) for row in conn.execute('SELECT * FROM price_entries WHERE catalog_version_id=? ORDER BY rowid',(key,))]
    return version


def list_catalogs():
    with connection() as conn:
        return [_catalog(conn,row[0]) for row in conn.execute('SELECT id FROM price_catalog_versions ORDER BY rowid')]


def quote(adapter,model,*,at=None,currency='USD',conn=None):
    instant=timestamp(at)
    if conn is None:
        with connection() as owned:return quote(adapter,model,at=at,currency=currency,conn=owned)
    row=conn.execute('''SELECT * FROM price_entries WHERE adapter=? AND model=? AND currency=? AND effective_from<=?
        ORDER BY effective_from DESC,rowid DESC LIMIT 1''',(adapter,model,currency,instant)).fetchone()
    if row is None or (row['effective_to'] is not None and row['effective_to']<=instant):return None
    return dict(row)


def estimate_for_call(call,*,billing_mode,at,conn):
    usage=call.usage
    if billing_mode not in ('api_metered','subscription_quota') or usage.source not in ('provider_reported','cli_reported'):
        return None,None
    if usage.input_tokens is None or usage.output_tokens is None:return None,None
    # Reported cache/reasoning can overlap input/output depending on the CLI.
    # Until normalized parsers define those semantics, abstain rather than guess.
    if any(getattr(usage,key) not in (None,0) for key in ('cache_read_tokens','cache_write_tokens','reasoning_tokens')):
        return None,None
    entry=quote(call.provider,call.model_reported or call.model,at=at,conn=conn)
    if entry is None:return None,None
    total=Decimal(0)
    for field,count in (('input_price',usage.input_tokens),('output_price',usage.output_tokens)):
        if count==0:continue
        if entry[field] is None:return None,None
        total+=Decimal(str(entry[field]))*count/Decimal(1_000_000)
    result=float(total)
    if not math.isfinite(result) or (total>0 and result==0):return None,None
    return result,entry['id']
