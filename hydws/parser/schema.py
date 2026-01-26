import uuid
from datetime import datetime

from pydantic import BaseModel


class RealValue(BaseModel):
    value: float = None
    uncertainty: float | None = None
    loweruncertainty: float | None = None
    upperuncertainty: float | None = None
    confidencelevel: float | None = None


class RealDatetime(RealValue):
    value: datetime


class CreationInfoSchema(BaseModel):
    author: str | None = None
    agencyid: str | None = None
    creationtime: datetime | None = None
    version: str | None = None
    copyrightowner: str | None = None
    license: str | None = None


class HydraulicSampleSchema(BaseModel):
    datetime: RealDatetime
    bottomtemperature: RealValue = None
    bottomflow: RealValue = None
    bottompressure: RealValue = None
    toptemperature: RealValue = None
    topflow: RealValue = None
    toppressure: RealValue = None
    fluiddensity: RealValue = None
    fluidviscosity: RealValue = None
    fluidph: RealValue = None
    fluidcomposition: str = None


class SectionSchema(BaseModel):
    publicid: uuid.UUID
    starttime: datetime = None
    endtime: datetime = None
    toplongitude: RealValue
    toplatitude: RealValue
    topaltitude: RealValue
    bottomlongitude: RealValue
    bottomlatitude: RealValue
    bottomaltitude: RealValue
    topmeasureddepth: RealValue = None
    bottommeasureddepth: RealValue = None
    holediameter: RealValue = None
    casingdiameter: RealValue = None
    topclosed: bool | None = None
    bottomclosed: bool | None = None
    sectiontype: str | None = None
    casingtype: str | None = None
    description: str | None = None
    name: str = None
    hydraulics: list[HydraulicSampleSchema] = []


class BoreholeSchema(BaseModel):
    publicid: uuid.UUID
    longitude: RealValue
    latitude: RealValue
    altitude: RealValue
    bedrockaltitude: RealValue = {}
    measureddepth: RealValue = None
    description: str | None = None
    name: str = None
    location: str | None = None
    institution: str | None = None
    creationinfo: CreationInfoSchema | None = None
    sections: list[SectionSchema] = []


def list_hydraulics_fields():
    real_fields = list(RealValue.model_fields.keys())
    sample_fields = list(HydraulicSampleSchema.model_fields.keys())
    hydraulic_fields = [
        f'{sf}_{n}' for n in real_fields for sf in sample_fields]
    hydraulic_fields.extend(sample_fields)
    return hydraulic_fields
