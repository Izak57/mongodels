from pydantic import BaseModel, Field



class Structure(BaseModel):
    pass


MongoId = Field(alias="_id")
