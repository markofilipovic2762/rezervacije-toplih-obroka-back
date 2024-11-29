from pydantic import BaseModel

class Narudzba(BaseModel):
    ime: str
    mbr: int
    jelo: str
    dan: str
    vreme: str

class EmailMenze(BaseModel):
    email: str