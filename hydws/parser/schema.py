import uuid
from datetime import datetime

from pydantic import BaseModel


class RealTest(BaseModel):
    value: list[dict] = []


class RealValue(BaseModel):
    value: float = None
    uncertainty: float | None = None
    loweruncertainty: float | None = None
    upperuncertainty: float | None = None
    confidencelevel: float | None = None


class RealDatetime(RealValue):
    value: datetime


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
    topclosed: bool
    bottomclosed: bool
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
    description: str = None
    name: str = None
    location_name: str = None
    institution: str = None
    sections: list[SectionSchema] = []


def list_hydraulics_fields():
    real_fields = list(RealValue.model_fields.keys())
    sample_fields = list(HydraulicSampleSchema.model_fields.keys())
    hydraulic_fields = [
        f'{sf}_{n}' for n in real_fields for sf in sample_fields]
    hydraulic_fields.extend(sample_fields)
    return hydraulic_fields
