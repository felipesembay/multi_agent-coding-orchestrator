"""Authenticated manual/batch import catalog API. No remote prices fetched."""
from fastapi import APIRouter,Query
from pydantic import AwareDatetime

from .accounting.pricing import CatalogInput,PricingError,create_catalog,list_catalogs,quote
from .projects import ProjectError

router=APIRouter()


@router.get('/pricing')
def catalogs():
    return list_catalogs()


@router.post('/pricing',status_code=201)
def create(data:CatalogInput):
    try:return create_catalog(data)
    except PricingError:
        raise ProjectError('Já existe preço para o início de vigência informado.',409) from None


@router.get('/pricing/quote')
def selected(adapter:str=Query(min_length=1,max_length=64),model:str=Query(min_length=1,max_length=256),
             at:AwareDatetime|None=None,currency:str=Query(default='USD',pattern=r'^[A-Z]{3}$')):
    entry=quote(adapter,model,at=at,currency=currency)
    return {'available':entry is not None,'entry':entry}
