import pandas as pd
import os
from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session


# right now using heroku to host and don't want to deal with their pricing/limits
# so database url falls back to ephemeral sqlite for demo purposes
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///cytometry.db")
engine = create_engine(DATABASE_URL, echo=False)

Base = declarative_base()

class Sample(Base):
    __tablename__ = "samples"
    sample_id = Column(String, primary_key=True)
    project    = Column(String, index=True)
    subject    = Column(String, index=True)
    condition  = Column(String, index=True)
    age        = Column(Integer)
    sex        = Column(String)
    treatment  = Column(String, index=True)
    response   = Column(Boolean)
    sample_type= Column(String)
    time_from_treatment_start = Column(Integer)

    counts = relationship("CellCount", back_populates="sample")


class CellCount(Base):
    __tablename__ = "cell_counts"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    sample_id   = Column(String, ForeignKey("samples.sample_id"))
    population  = Column(String, index=True)
    count       = Column(Integer)

    sample      = relationship("Sample", back_populates="counts")


def init_db(uri="sqlite:///cytometry.db"):
    engine = create_engine(uri, echo=False)
    Base.metadata.create_all(engine)
    return engine

def load_csv(engine, csv_path="data/cell-count.csv"):
    df = pd.read_csv(csv_path)
    with Session(engine) as session:
        for _, row in df.iterrows():
            s = Sample(
                sample_id=row["sample"],
                project=row["project"],
                subject=row["subject"],
                condition=row["condition"],
                age=int(row["age"]),
                sex=row["sex"],
                treatment=row["treatment"],
                response=(str(row["response"]).lower() == "yes"),
                sample_type=row["sample_type"],
                time_from_treatment_start=int(row["time_from_treatment_start"])
            )
            session.add(s)

            for pop in ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]:
                session.add(CellCount(
                    sample_id=row["sample"],
                    population=pop,
                    count=int(row[pop])
                ))

        session.commit()
